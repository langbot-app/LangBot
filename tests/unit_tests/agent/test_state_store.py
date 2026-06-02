"""Tests for persistent AgentRunner state store."""
from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.host_models import BindingScope, StatePolicy
from langbot.pkg.agent.runner.persistent_state_store import PersistentStateStore
from langbot.pkg.agent.runner.state_scope import (
    STATE_KEY_ALIASES,
    VALID_STATE_SCOPES,
    build_state_context,
    build_state_scope_key,
    get_binding_identity,
    normalize_state_key,
)


def make_descriptor(runner_id: str = 'plugin:test/my-runner/default') -> AgentRunnerDescriptor:
    """Create a test descriptor."""
    return AgentRunnerDescriptor(
        id=runner_id,
        source='plugin',
        label={'en_US': 'Test Runner'},
        plugin_author='test',
        plugin_name='my-runner',
        runner_name='default',
        protocol_version='1',
        capabilities={'streaming': True},
    )


class FakeActorContext:
    """Fake actor context for event testing."""
    def __init__(self, actor_type: str = 'user', actor_id: str = 'user_123', actor_name: str = 'Test User'):
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.actor_name = actor_name


class FakeSubjectContext:
    """Fake subject context for event testing."""
    def __init__(self, subject_type: str = 'message', subject_id: str = 'msg_001', data: dict | None = None):
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.data = data or {}


class FakeEventEnvelope:
    """Fake event envelope for testing event-first state."""
    def __init__(
        self,
        event_id: str = 'evt_001',
        event_type: str = 'message.received',
        conversation_id: str | None = 'conv_001',
        actor: FakeActorContext | None = None,
        subject: FakeSubjectContext | None = None,
        bot_id: str = 'bot_001',
        workspace_id: str = 'ws_001',
        thread_id: str | None = None,
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.event_time = 1700000000
        self.source = 'platform'
        self.bot_id = bot_id
        self.workspace_id = workspace_id
        self.conversation_id = conversation_id
        self.thread_id = thread_id
        self.actor = actor or FakeActorContext()
        self.subject = subject
        self.raw_ref = None


class FakeBinding:
    """Fake binding for testing state."""
    def __init__(
        self,
        binding_id: str = 'binding_001',
        state_policy: StatePolicy | None = None,
        scope_type: str = 'agent',
        scope_id: str = 'agent_001',
    ):
        self.binding_id = binding_id
        self.scope = BindingScope(scope_type=scope_type, scope_id=scope_id)
        self.state_policy = state_policy or StatePolicy()


class TestStateScopeHelpers:
    """Tests for shared state scope helpers."""

    def test_valid_state_scopes(self):
        assert VALID_STATE_SCOPES == ('conversation', 'actor', 'subject', 'runner')

    def test_state_key_aliases(self):
        assert STATE_KEY_ALIASES == {'conversation_id': 'external.conversation_id'}
        assert normalize_state_key('conversation_id') == 'external.conversation_id'
        assert normalize_state_key('external.session_id') == 'external.session_id'

    def test_binding_identity_uses_binding_id_first(self):
        binding = FakeBinding(binding_id='binding_a')
        assert get_binding_identity(binding) == 'binding_a'

    def test_binding_identity_falls_back_to_scope(self):
        binding = FakeBinding(binding_id='', scope_type='workspace', scope_id='ws_001')
        assert get_binding_identity(binding) == 'workspace:ws_001'

    def test_scope_key_building(self):
        descriptor = make_descriptor()
        binding = FakeBinding(binding_id='binding_a')
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            actor=FakeActorContext(actor_id='user_001'),
            subject=FakeSubjectContext(subject_id='msg_001'),
            thread_id='thread_001',
        )

        assert build_state_scope_key('conversation', event, binding, descriptor) == (
            'conversation:plugin:test/my-runner/default:binding_a:conv_001:thread_001'
        )
        assert build_state_scope_key('actor', event, binding, descriptor) == (
            'actor:plugin:test/my-runner/default:binding_a:user:user_001'
        )
        assert build_state_scope_key('subject', event, binding, descriptor) == (
            'subject:plugin:test/my-runner/default:binding_a:message:msg_001'
        )
        assert build_state_scope_key('runner', event, binding, descriptor) == (
            'runner:plugin:test/my-runner/default:binding_a'
        )

    def test_scope_key_missing_identity_returns_none(self):
        descriptor = make_descriptor()
        binding = FakeBinding()
        event = FakeEventEnvelope(conversation_id=None, actor=None, subject=None)

        assert build_state_scope_key('conversation', event, binding, descriptor) is None
        assert build_state_scope_key('subject', event, binding, descriptor) is None
        assert build_state_scope_key('runner', event, binding, descriptor) is not None

    def test_build_state_context(self):
        descriptor = make_descriptor()
        binding = FakeBinding(binding_id='binding_a')
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            actor=FakeActorContext(actor_id='user_001'),
            subject=FakeSubjectContext(subject_id='msg_001'),
        )

        context = build_state_context(event, binding, descriptor)

        assert context['binding_identity'] == 'binding_a'
        assert context['conversation_id'] == 'conv_001'
        assert context['actor_id'] == 'user_001'
        assert set(context['scope_keys']) == {'conversation', 'actor', 'subject', 'runner'}


class TestPersistentStateStore:
    """Tests for persistent database-backed state store."""

    @pytest.fixture
    async def db_engine(self):
        """Create a temporary async SQLite database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', echo=False)

        from langbot.pkg.entity.persistence.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()
        os.unlink(db_path)

    @pytest.fixture
    async def persistent_store(self, db_engine):
        """Create a persistent state store for testing."""
        store = PersistentStateStore(db_engine)
        yield store
        await store.clear_all()

    @pytest.mark.asyncio
    async def test_build_snapshot_empty(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['conversation'] == {'external.conversation_id': 'conv_001'}
        assert snapshot['actor'] == {}
        assert snapshot['subject'] == {}
        assert snapshot['runner'] == {}

    @pytest.mark.asyncio
    async def test_state_set_and_get(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        success, error = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'test_key', {'nested': 'value'}, None
        )
        assert success is True
        assert error is None

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['test_key'] == {'nested': 'value'}

    @pytest.mark.asyncio
    async def test_state_api_methods_normalize_public_key_aliases(self, persistent_store):
        scope_key = 'conversation:runner:binding:conv_001'

        success, error = await persistent_store.state_set(
            scope_key=scope_key,
            state_key='conversation_id',
            value='conv_001',
            runner_id='plugin:test/my-runner/default',
            binding_identity='binding_001',
            scope='conversation',
        )

        assert success is True
        assert error is None
        assert await persistent_store.state_get(scope_key, 'external.conversation_id') == 'conv_001'
        assert await persistent_store.state_get(scope_key, 'conversation_id') == 'conv_001'

        keys, _ = await persistent_store.state_list(scope_key, prefix='conversation_id')
        assert keys == ['external.conversation_id']

        assert await persistent_store.state_delete(scope_key, 'conversation_id') is True
        assert await persistent_store.state_get(scope_key, 'external.conversation_id') is None

    @pytest.mark.asyncio
    async def test_binding_isolation(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding_a = FakeBinding(binding_id='binding_a')
        binding_b = FakeBinding(binding_id='binding_b')

        await persistent_store.apply_update_from_event(
            event, binding_a, descriptor, 'conversation', 'key', 'value_a', None
        )

        snapshot_b = await persistent_store.build_snapshot_from_event(event, binding_b, descriptor)
        assert snapshot_b['conversation'] == {'external.conversation_id': 'conv_001'}

        snapshot_a = await persistent_store.build_snapshot_from_event(event, binding_a, descriptor)
        assert snapshot_a['conversation']['key'] == 'value_a'

    @pytest.mark.asyncio
    async def test_policy_disable_state(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding(state_policy=StatePolicy(enable_state=False))

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot == {'conversation': {}, 'actor': {}, 'subject': {}, 'runner': {}}

        success, error = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value', None
        )
        assert success is False
        assert 'disabled' in error.lower()

    @pytest.mark.asyncio
    async def test_policy_scope_restriction(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            actor=FakeActorContext(actor_id='user_001'),
        )
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation']))

        success_conv, _ = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value_conv', None
        )
        assert success_conv is True

        success_actor, error_actor = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'actor', 'key', 'value_actor', None
        )
        assert success_actor is False
        assert 'not enabled' in error_actor.lower()

    @pytest.mark.asyncio
    async def test_value_json_size_limit(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        large_value = 'x' * (300 * 1024)

        success, error = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', large_value, None
        )
        assert success is False
        assert 'exceeds limit' in error.lower()

    @pytest.mark.asyncio
    async def test_value_not_json_serializable(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        success, error = await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', {'key': {1, 2, 3}}, None
        )
        assert success is False
        assert 'json' in error.lower()

    @pytest.mark.asyncio
    async def test_state_list(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'external.id', '123', None
        )
        await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'external.name', 'test', None
        )
        await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'memory.key', 'value', None
        )

        scope_key = build_state_scope_key('conversation', event, binding, descriptor)

        keys, has_more = await persistent_store.state_list(scope_key)
        assert len(keys) == 3
        assert has_more is False

        keys_ext, _ = await persistent_store.state_list(scope_key, prefix='external.')
        assert len(keys_ext) == 2
        assert 'external.id' in keys_ext
        assert 'external.name' in keys_ext

    @pytest.mark.asyncio
    async def test_state_delete(self, persistent_store):
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()

        await persistent_store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value', None
        )
        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['key'] == 'value'

        scope_key = build_state_scope_key('conversation', event, binding, descriptor)
        deleted = await persistent_store.state_delete(scope_key, 'key')
        assert deleted is True

        snapshot = await persistent_store.build_snapshot_from_event(event, binding, descriptor)
        assert 'key' not in snapshot['conversation']

        deleted_again = await persistent_store.state_delete(scope_key, 'key')
        assert deleted_again is False
