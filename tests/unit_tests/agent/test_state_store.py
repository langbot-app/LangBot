"""Tests for runner scoped state store."""
from __future__ import annotations

from langbot.pkg.agent.runner.state_store import (
    RunnerScopedStateStore,
    get_state_store,
    reset_state_store,
    VALID_STATE_SCOPES,
    LEGACY_KEY_MAPPING,
)
from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor
from langbot.pkg.agent.runner.host_models import AgentBinding, BindingScope, StatePolicy


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


class FakeSession:
    """Fake session for testing."""
    def __init__(self):
        self.launcher_type = type('LauncherType', (), {'value': 'telegram'})()
        self.launcher_id = 'group_123'
        self.using_conversation = None


class FakeConversation:
    """Fake conversation for testing."""
    def __init__(self, uuid: str = 'conv_abc', create_time: int | None = None):
        self.uuid = uuid
        self.create_time = create_time


class FakeQuery:
    """Fake query for testing."""
    def __init__(
        self,
        bot_uuid: str = 'bot_001',
        pipeline_uuid: str = 'pipeline_002',
        sender_id: str = 'user_123',
        session: FakeSession | None = None,
    ):
        self.bot_uuid = bot_uuid
        self.pipeline_uuid = pipeline_uuid
        self.sender_id = sender_id
        self.session = session or FakeSession()


class FakeLogger:
    """Fake logger for testing."""
    def __init__(self):
        self.debugs = []
        self.warnings = []

    def debug(self, msg):
        self.debugs.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)


class FakeBinding:
    """Fake binding for testing event-first state."""
    def __init__(
        self,
        binding_id: str = 'binding_001',
        state_policy: StatePolicy | None = None,
    ):
        self.binding_id = binding_id
        self.scope = BindingScope(scope_type='pipeline', scope_id='pipeline_001')
        self.state_policy = state_policy or StatePolicy()


class TestStateStoreBuildSnapshot:
    """Tests for build_snapshot."""

    def test_build_snapshot_returns_four_scopes(self):
        """Snapshot should have all four scope keys."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()

        snapshot = store.build_snapshot(query, descriptor)

        assert 'conversation' in snapshot
        assert 'actor' in snapshot
        assert 'subject' in snapshot
        assert 'runner' in snapshot
        assert snapshot['conversation'] == {}
        assert snapshot['actor'] == {}
        assert snapshot['subject'] == {}
        assert snapshot['runner'] == {}

    def test_build_snapshot_seeds_conversation_id(self):
        """Snapshot should seed external.conversation_id from existing conversation."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        conversation = FakeConversation(uuid='conv_existing')
        session = FakeSession()
        session.using_conversation = conversation
        query = FakeQuery(session=session)

        snapshot = store.build_snapshot(query, descriptor)

        assert snapshot['conversation']['external.conversation_id'] == 'conv_existing'

    def test_build_snapshot_returns_stored_values(self):
        """Snapshot should return previously stored values."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        # Store some values
        store.apply_update(query, descriptor, 'conversation', 'external.conversation_id', 'conv_001', logger)
        store.apply_update(query, descriptor, 'actor', 'preferred_language', 'zh', logger)
        store.apply_update(query, descriptor, 'subject', 'group_topic', 'tech', logger)
        store.apply_update(query, descriptor, 'runner', 'cache_version', 'v1', logger)

        # Build snapshot
        snapshot = store.build_snapshot(query, descriptor)

        assert snapshot['conversation']['external.conversation_id'] == 'conv_001'
        assert snapshot['actor']['preferred_language'] == 'zh'
        assert snapshot['subject']['group_topic'] == 'tech'
        assert snapshot['runner']['cache_version'] == 'v1'

    def test_build_snapshot_isolation_by_runner_id(self):
        """Different runner IDs should have isolated state."""
        store = RunnerScopedStateStore()
        descriptor1 = make_descriptor('plugin:test/runner-a/default')
        descriptor2 = make_descriptor('plugin:test/runner-b/default')
        query = FakeQuery()
        logger = FakeLogger()

        # Store for runner-a
        store.apply_update(query, descriptor1, 'conversation', 'external.conversation_id', 'conv_a', logger)

        # Build snapshot for runner-b
        snapshot_b = store.build_snapshot(query, descriptor2)

        # runner-b should not see runner-a's state
        assert snapshot_b['conversation'] == {}


class TestStateStoreApplyUpdate:
    """Tests for apply_update."""

    def test_apply_update_conversation_scope(self):
        """Apply update to conversation scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(
            query, descriptor, 'conversation', 'external.conversation_id', 'conv_new', logger
        )

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_actor_scope(self):
        """Apply update to actor scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(query, descriptor, 'actor', 'preferred_language', 'en', logger)

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_subject_scope(self):
        """Apply update to subject scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(query, descriptor, 'subject', 'group_topic', 'general', logger)

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_runner_scope(self):
        """Apply update to runner scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(query, descriptor, 'runner', 'cache_version', 'v2', logger)

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_invalid_scope(self):
        """Invalid scope should return False and log warning."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(query, descriptor, 'invalid_scope', 'key', 'value', logger)

        assert result is False
        assert len(logger.warnings) == 1
        assert 'invalid scope' in logger.warnings[0]

    def test_apply_update_legacy_key_mapping(self):
        """Legacy key conversation_id should be mapped to external.conversation_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        result = store.apply_update(query, descriptor, 'conversation', 'conversation_id', 'conv_old', logger)

        assert result is True
        assert 'mapped to' in logger.debugs[0]

        # Check mapped key is stored
        snapshot = store.build_snapshot(query, descriptor)
        assert snapshot['conversation']['external.conversation_id'] == 'conv_old'

    def test_apply_update_syncs_conversation_uuid(self):
        """external.conversation_id update should sync to query.session.using_conversation.uuid."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        conversation = FakeConversation(uuid='conv_old')
        session = FakeSession()
        session.using_conversation = conversation
        query = FakeQuery(session=session)
        logger = FakeLogger()

        result = store.apply_update(
            query, descriptor, 'conversation', 'external.conversation_id', 'conv_new', logger
        )

        assert result is True
        assert conversation.uuid == 'conv_new'  # Synced
        assert 'Synced' in logger.debugs[-1]


class TestStateStoreScopeIdentity:
    """Tests for scope identity isolation."""

    def test_conversation_scope_includes_runner_id(self):
        """Conversation scope key should include runner_id."""
        store = RunnerScopedStateStore()
        descriptor_a = make_descriptor('plugin:test/runner-a/default')
        descriptor_b = make_descriptor('plugin:test/runner-b/default')
        query = FakeQuery()
        logger = FakeLogger()

        # Store for runner-a
        store.apply_update(query, descriptor_a, 'conversation', 'key', 'value_a', logger)

        # runner-b should not see runner-a's conversation state
        snapshot_b = store.build_snapshot(query, descriptor_b)
        assert snapshot_b['conversation'] == {}

        # runner-a should see its own state
        snapshot_a = store.build_snapshot(query, descriptor_a)
        assert snapshot_a['conversation']['key'] == 'value_a'

    def test_actor_scope_includes_sender_id(self):
        """Actor scope should be isolated per sender_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        query_user1 = FakeQuery(sender_id='user_001')
        query_user2 = FakeQuery(sender_id='user_002')
        logger = FakeLogger()

        # Store for user_001
        store.apply_update(query_user1, descriptor, 'actor', 'preferred_language', 'en', logger)

        # user_002 should not see user_001's actor state
        snapshot_user2 = store.build_snapshot(query_user2, descriptor)
        assert snapshot_user2['actor'] == {}

        # user_001 should see its own state
        snapshot_user1 = store.build_snapshot(query_user1, descriptor)
        assert snapshot_user1['actor']['preferred_language'] == 'en'

    def test_subject_scope_includes_launcher(self):
        """Subject scope should be isolated per launcher_type + launcher_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        session1 = FakeSession()
        session1.launcher_type = type('LauncherType', (), {'value': 'telegram'})()
        session1.launcher_id = 'group_001'
        session2 = FakeSession()
        session2.launcher_type = type('LauncherType', (), {'value': 'telegram'})()
        session2.launcher_id = 'group_002'
        query1 = FakeQuery(session=session1)
        query2 = FakeQuery(session=session2)
        logger = FakeLogger()

        # Store for group_001
        store.apply_update(query1, descriptor, 'subject', 'group_topic', 'tech', logger)

        # group_002 should not see group_001's subject state
        snapshot2 = store.build_snapshot(query2, descriptor)
        assert snapshot2['subject'] == {}

        # group_001 should see its own state
        snapshot1 = store.build_snapshot(query1, descriptor)
        assert snapshot1['subject']['group_topic'] == 'tech'

    def test_conversation_scope_not_dependent_on_external_uuid(self):
        """Conversation scope identity should NOT use external conversation uuid.

        Using external uuid as scope key would cause state loss when
        runner updates external.conversation_id:
        - First run: state saved under key with old uuid
        - Runner returns new external.conversation_id, synced to conversation.uuid
        - Next run: scope key uses new uuid, previous state inaccessible

        This test verifies scope key stability when conversation.uuid changes.
        """
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        # Use stable create_time as conversation identity
        conversation = FakeConversation(uuid='conv_initial', create_time=12345)
        session = FakeSession()
        session.using_conversation = conversation
        query = FakeQuery(session=session)
        logger = FakeLogger()

        # Store some conversation state (e.g., memory.summary, external.thread_id)
        store.apply_update(
            query, descriptor, 'conversation', 'memory.summary', 'Summary content', logger
        )
        store.apply_update(
            query, descriptor, 'conversation', 'external.thread_id', 'thread_abc', logger
        )

        # Simulate runner returning new external.conversation_id
        store.apply_update(
            query, descriptor, 'conversation', 'external.conversation_id', 'conv_new_from_runner', logger
        )

        # conversation.uuid is synced to new value
        assert conversation.uuid == 'conv_new_from_runner'

        # Build new snapshot - previous state should still be accessible
        # because scope key is based on stable identity (create_time), not external uuid
        snapshot = store.build_snapshot(query, descriptor)

        # All previously stored state should still be present
        assert snapshot['conversation']['memory.summary'] == 'Summary content'
        assert snapshot['conversation']['external.thread_id'] == 'thread_abc'
        assert snapshot['conversation']['external.conversation_id'] == 'conv_new_from_runner'

    def test_conversation_scope_with_create_time_stability(self):
        """Conversation scope key should use create_time for stability.

        When create_time is available, it should be used as stable identity.
        Different conversations with same launcher but different create_time
        should have different scope keys.
        """
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()

        # Two conversations with same launcher but different create_time
        conversation1 = FakeConversation(uuid='conv_1', create_time=10000)
        conversation2 = FakeConversation(uuid='conv_2', create_time=20000)
        session1 = FakeSession()
        session1.using_conversation = conversation1
        session2 = FakeSession()
        session2.using_conversation = conversation2

        query1 = FakeQuery(session=session1)
        query2 = FakeQuery(session=session2)
        logger = FakeLogger()

        # Store for conversation1
        store.apply_update(query1, descriptor, 'conversation', 'key', 'value1', logger)

        # conversation2 should not see conversation1's state (different create_time)
        # Note: snapshot2 may have seeded external.conversation_id from conversation2.uuid
        snapshot2 = store.build_snapshot(query2, descriptor)
        assert 'key' not in snapshot2['conversation']  # No state from conversation1

        # conversation1 should see its own state
        snapshot1 = store.build_snapshot(query1, descriptor)
        assert snapshot1['conversation']['key'] == 'value1'

    def test_conversation_scope_without_create_time_uses_launcher_identity(self):
        """Conversation scope without create_time should use launcher identity.

        When create_time is not available, scope key should be based on
        launcher (person/group) identity, assuming one active conversation
        per launcher context.
        """
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()

        # Conversation without create_time
        conversation = FakeConversation(uuid='conv_1', create_time=None)
        session = FakeSession()
        session.using_conversation = conversation
        query = FakeQuery(session=session)
        logger = FakeLogger()

        # Store some state
        store.apply_update(query, descriptor, 'conversation', 'key', 'value', logger)

        # State should be accessible
        snapshot = store.build_snapshot(query, descriptor)
        assert snapshot['conversation']['key'] == 'value'

        # Update external.conversation_id
        store.apply_update(
            query, descriptor, 'conversation', 'external.conversation_id', 'conv_2', logger
        )

        # State should still be accessible (scope key unchanged)
        snapshot = store.build_snapshot(query, descriptor)
        assert snapshot['conversation']['key'] == 'value'
        assert snapshot['conversation']['external.conversation_id'] == 'conv_2'


class TestStateStoreGlobalSingleton:
    """Tests for global singleton functions."""

    def test_get_state_store_returns_singleton(self):
        """get_state_store should return the same instance."""
        reset_state_store()
        store1 = get_state_store()
        store2 = get_state_store()

        assert store1 is store2

    def test_reset_state_store_clears_singleton(self):
        """reset_state_store should clear the singleton."""
        store1 = get_state_store()
        reset_state_store()
        store2 = get_state_store()

        assert store1 is not store2

    def test_reset_state_store_clears_data(self):
        """reset_state_store should clear stored data."""
        store = get_state_store()
        descriptor = make_descriptor()
        query = FakeQuery()
        logger = FakeLogger()

        # Store some data
        store.apply_update(query, descriptor, 'conversation', 'key', 'value', logger)
        snapshot = store.build_snapshot(query, descriptor)
        assert snapshot['conversation']['key'] == 'value'

        # Reset
        reset_state_store()
        store = get_state_store()

        # Data should be gone
        snapshot = store.build_snapshot(query, descriptor)
        assert snapshot['conversation'] == {}


class TestConstants:
    """Tests for module constants."""

    def test_valid_state_scopes(self):
        """VALID_STATE_SCOPES should have four scopes."""
        assert VALID_STATE_SCOPES == ('conversation', 'actor', 'subject', 'runner')

    def test_legacy_key_mapping(self):
        """LEGACY_KEY_MAPPING should map conversation_id."""
        assert LEGACY_KEY_MAPPING == {'conversation_id': 'external.conversation_id'}


# ========== Event-first Protocol v1 tests ==========


class FakeActorContext:
    """Fake actor context for event testing."""
    def __init__(self, actor_type: str = 'user', actor_id: str = 'user_123', actor_name: str = 'Test User'):
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.actor_name = actor_name


class FakeSubjectContext:
    """Fake subject context for event testing."""
    def __init__(self, subject_type: str = 'message', subject_id: str = 'msg_001', data: dict = None):
        self.subject_type = subject_type
        self.subject_id = subject_id
        self.data = data or {}


class FakeAgentInput:
    """Fake agent input for event testing."""
    def __init__(self, text: str = 'Hello'):
        self.text = text
        self.contents = []
        self.message_chain = None
        self.attachments = []


class FakeDeliveryContext:
    """Fake delivery context for event testing."""
    def __init__(self):
        self.surface = 'platform'
        self.reply_target = None
        self.supports_streaming = True
        self.supports_edit = False
        self.supports_reaction = False
        self.max_message_size = None
        self.platform_capabilities = {}


class FakeEventEnvelope:
    """Fake event envelope for testing event-first state."""
    def __init__(
        self,
        event_id: str = 'evt_001',
        event_type: str = 'message.received',
        conversation_id: str = 'conv_001',
        actor: FakeActorContext | None = None,
        subject: FakeSubjectContext | None = None,
        bot_id: str = 'bot_001',
        workspace_id: str = 'ws_001',
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.event_time = 1700000000
        self.source = 'platform'
        self.bot_id = bot_id
        self.workspace_id = workspace_id
        self.conversation_id = conversation_id
        self.thread_id = None
        self.actor = actor or FakeActorContext()
        self.subject = subject
        self.input = FakeAgentInput()
        self.delivery = FakeDeliveryContext()
        self.raw_ref = None


class TestStateStoreEventFirstBuildSnapshot:
    """Tests for build_snapshot_from_event."""

    def test_build_snapshot_returns_four_scopes(self):
        """Snapshot from event should have all four scope keys."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope()
        binding = FakeBinding()

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert 'conversation' in snapshot
        assert 'actor' in snapshot
        assert 'subject' in snapshot
        assert 'runner' in snapshot

    def test_build_snapshot_seeds_conversation_id(self):
        """Snapshot should seed external.conversation_id from event.conversation_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_test')
        binding = FakeBinding()

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['conversation']['external.conversation_id'] == 'conv_test'

    def test_build_snapshot_without_conversation_id(self):
        """Snapshot without conversation_id should have empty conversation scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id=None)
        binding = FakeBinding()

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['conversation'] == {}

    def test_build_snapshot_without_actor(self):
        """Snapshot without actor should have empty actor scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(actor=None)
        binding = FakeBinding()

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['actor'] == {}

    def test_build_snapshot_without_subject(self):
        """Snapshot without subject should have empty subject scope."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(subject=None)
        binding = FakeBinding()

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['subject'] == {}

    def test_build_snapshot_returns_stored_values(self):
        """Snapshot should return previously stored values via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001', actor=FakeActorContext(actor_id='user_001'))
        # Use binding with all scopes enabled
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        # Store values using event-first methods
        store.apply_update_from_event(event, binding, descriptor, 'conversation', 'memory.summary', 'Summary', logger)
        store.apply_update_from_event(event, binding, descriptor, 'actor', 'preferred_language', 'en', logger)
        store.apply_update_from_event(event, binding, descriptor, 'runner', 'cache_version', 'v1', logger)

        # Build snapshot
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)

        assert snapshot['conversation']['memory.summary'] == 'Summary'
        assert snapshot['actor']['preferred_language'] == 'en'
        assert snapshot['runner']['cache_version'] == 'v1'

    def test_build_snapshot_isolation_by_runner_id(self):
        """Different runner IDs should have isolated state in event-first mode."""
        store = RunnerScopedStateStore()
        descriptor1 = make_descriptor('plugin:test/runner-a/default')
        descriptor2 = make_descriptor('plugin:test/runner-b/default')
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()
        logger = FakeLogger()

        # Store for runner-a
        store.apply_update_from_event(event, binding, descriptor1, 'conversation', 'key', 'value_a', logger)

        # Build snapshot for runner-b
        snapshot_b = store.build_snapshot_from_event(event, binding, descriptor2)

        # runner-b should not see runner-a's state (only external.conversation_id seeded)
        assert snapshot_b['conversation'] == {'external.conversation_id': 'conv_001'}


class TestStateStoreEventFirstApplyUpdate:
    """Tests for apply_update_from_event."""

    def test_apply_update_conversation_scope(self):
        """Apply update to conversation scope via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'memory.summary', 'Summary', logger
        )

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_actor_scope(self):
        """Apply update to actor scope via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(actor=FakeActorContext(actor_id='user_001'))
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'actor', 'preferred_language', 'en', logger
        )

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_subject_scope(self):
        """Apply update to subject scope via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(subject=FakeSubjectContext(subject_id='msg_001'))
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'subject', 'group_topic', 'general', logger
        )

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_runner_scope(self):
        """Apply update to runner scope via event (always works)."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope()  # No special identity needed
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'runner', 'cache_version', 'v2', logger
        )

        assert result is True
        assert len(logger.warnings) == 0

    def test_apply_update_invalid_scope(self):
        """Invalid scope should return False and log warning."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope()
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'invalid_scope', 'key', 'value', logger
        )

        assert result is False
        assert len(logger.warnings) == 1
        assert 'invalid scope' in logger.warnings[0]

    def test_apply_update_conversation_missing_conversation_id(self):
        """Conversation scope without conversation_id should return False."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id=None)
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value', logger
        )

        assert result is False
        assert len(logger.warnings) == 1
        assert 'missing identity' in logger.warnings[0]

    def test_apply_update_actor_missing_actor_id(self):
        """Actor scope without actor_id should return False."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(actor=FakeActorContext(actor_id=None))
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'actor', 'key', 'value', logger
        )

        assert result is False
        assert len(logger.warnings) == 1
        assert 'missing identity' in logger.warnings[0]

    def test_apply_update_subject_missing_subject_id(self):
        """Subject scope without subject_id should return False."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(subject=FakeSubjectContext(subject_id=None))
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'subject', 'key', 'value', logger
        )

        assert result is False
        assert len(logger.warnings) == 1
        assert 'missing identity' in logger.warnings[0]

    def test_apply_update_legacy_key_mapping(self):
        """Legacy key conversation_id should be mapped to external.conversation_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'conversation_id', 'conv_old', logger
        )

        assert result is True
        assert 'mapped to' in logger.debugs[0]

        # Check mapped key is stored
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['external.conversation_id'] == 'conv_old'


class TestStateStoreEventFirstScopeIsolation:
    """Tests for scope isolation in event-first mode."""

    def test_conversation_scope_isolated_by_conversation_id(self):
        """Conversation scope should be isolated by conversation_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        binding = FakeBinding()
        event1 = FakeEventEnvelope(conversation_id='conv_001')
        event2 = FakeEventEnvelope(conversation_id='conv_002')
        logger = FakeLogger()

        # Store for conv_001
        store.apply_update_from_event(event1, binding, descriptor, 'conversation', 'key', 'value1', logger)

        # conv_002 should not see conv_001's state
        snapshot2 = store.build_snapshot_from_event(event2, binding, descriptor)
        assert snapshot2['conversation'] == {'external.conversation_id': 'conv_002'}

        # conv_001 should see its own state
        snapshot1 = store.build_snapshot_from_event(event1, binding, descriptor)
        assert snapshot1['conversation']['key'] == 'value1'

    def test_actor_scope_isolated_by_actor_id(self):
        """Actor scope should be isolated by actor_type + actor_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        binding = FakeBinding()
        event1 = FakeEventEnvelope(actor=FakeActorContext(actor_type='user', actor_id='user_001'))
        event2 = FakeEventEnvelope(actor=FakeActorContext(actor_type='user', actor_id='user_002'))
        logger = FakeLogger()

        # Store for user_001
        store.apply_update_from_event(event1, binding, descriptor, 'actor', 'preferred_language', 'en', logger)

        # user_002 should not see user_001's state
        snapshot2 = store.build_snapshot_from_event(event2, binding, descriptor)
        assert snapshot2['actor'] == {}

        # user_001 should see its own state
        snapshot1 = store.build_snapshot_from_event(event1, binding, descriptor)
        assert snapshot1['actor']['preferred_language'] == 'en'

    def test_subject_scope_isolated_by_subject_id(self):
        """Subject scope should be isolated by subject_type + subject_id."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        event1 = FakeEventEnvelope(subject=FakeSubjectContext(subject_type='message', subject_id='msg_001'))
        event2 = FakeEventEnvelope(subject=FakeSubjectContext(subject_type='message', subject_id='msg_002'))
        logger = FakeLogger()

        # Store for msg_001
        store.apply_update_from_event(event1, binding, descriptor, 'subject', 'key', 'value1', logger)

        # msg_002 should not see msg_001's state
        snapshot2 = store.build_snapshot_from_event(event2, binding, descriptor)
        assert snapshot2['subject'] == {}

        # msg_001 should see its own state
        snapshot1 = store.build_snapshot_from_event(event1, binding, descriptor)
        assert snapshot1['subject']['key'] == 'value1'

    def test_runner_scope_shared_within_runner(self):
        """Runner scope should be shared within same runner across all events."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        event1 = FakeEventEnvelope(conversation_id='conv_001')
        event2 = FakeEventEnvelope(conversation_id='conv_002')
        logger = FakeLogger()

        # Store for event1's runner scope
        store.apply_update_from_event(event1, binding, descriptor, 'runner', 'cache_version', 'v1', logger)

        # event2 should see the same runner state
        snapshot2 = store.build_snapshot_from_event(event2, binding, descriptor)
        assert snapshot2['runner']['cache_version'] == 'v1'


class TestStateStoreEventFirstRoundTrip:
    """Tests for state round trip: store -> read via event-first."""

    def test_state_round_trip_conversation(self):
        """State stored via event should be readable via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding = FakeBinding()
        logger = FakeLogger()

        # Store
        store.apply_update_from_event(event, binding, descriptor, 'conversation', 'memory.summary', 'Summary', logger)

        # Read
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['memory.summary'] == 'Summary'

    def test_state_round_trip_actor(self):
        """Actor state stored via event should be readable via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(actor=FakeActorContext(actor_id='user_001'))
        binding = FakeBinding()
        logger = FakeLogger()

        # Store
        store.apply_update_from_event(event, binding, descriptor, 'actor', 'preferred_language', 'zh', logger)

        # Read
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['actor']['preferred_language'] == 'zh'

    def test_state_round_trip_subject(self):
        """Subject state stored via event should be readable via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(subject=FakeSubjectContext(subject_id='msg_001'))
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        # Store
        store.apply_update_from_event(event, binding, descriptor, 'subject', 'group_topic', 'tech', logger)

        # Read
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['subject']['group_topic'] == 'tech'

    def test_state_round_trip_runner(self):
        """Runner state stored via event should be readable via event."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope()
        binding = FakeBinding(state_policy=StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner']))
        logger = FakeLogger()

        # Store
        store.apply_update_from_event(event, binding, descriptor, 'runner', 'cache_version', 'v2', logger)

        # Read
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['runner']['cache_version'] == 'v2'


class TestStateStoreBindingIsolation:
    """Tests for binding isolation in event-first state."""

    def test_conversation_state_isolated_by_binding_id(self):
        """Same runner, same conversation_id, different binding_id: conversation state isolated."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()  # Same runner
        event = FakeEventEnvelope(conversation_id='conv_001')
        binding_a = FakeBinding(binding_id='binding_a')
        binding_b = FakeBinding(binding_id='binding_b')
        logger = FakeLogger()

        # Store for binding_a
        store.apply_update_from_event(event, binding_a, descriptor, 'conversation', 'key', 'value_a', logger)

        # binding_b should not see binding_a's state
        snapshot_b = store.build_snapshot_from_event(event, binding_b, descriptor)
        assert snapshot_b['conversation'] == {'external.conversation_id': 'conv_001'}

        # binding_a should see its own state
        snapshot_a = store.build_snapshot_from_event(event, binding_a, descriptor)
        assert snapshot_a['conversation']['key'] == 'value_a'

    def test_runner_state_isolated_by_binding_id(self):
        """Same runner, different binding_id: runner state isolated."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()  # Same runner
        event = FakeEventEnvelope()
        policy = StatePolicy(state_scopes=['conversation', 'actor', 'subject', 'runner'])
        binding_a = FakeBinding(binding_id='binding_a', state_policy=policy)
        binding_b = FakeBinding(binding_id='binding_b', state_policy=policy)
        logger = FakeLogger()

        # Store for binding_a
        store.apply_update_from_event(event, binding_a, descriptor, 'runner', 'cache_version', 'v1', logger)

        # binding_b should not see binding_a's runner state
        snapshot_b = store.build_snapshot_from_event(event, binding_b, descriptor)
        assert snapshot_b['runner'] == {}

        # binding_a should see its own state
        snapshot_a = store.build_snapshot_from_event(event, binding_a, descriptor)
        assert snapshot_a['runner']['cache_version'] == 'v1'

    def test_actor_state_isolated_by_binding_id(self):
        """Same runner, same actor_id, different binding_id: actor state isolated."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(actor=FakeActorContext(actor_id='user_001'))
        binding_a = FakeBinding(binding_id='binding_a')
        binding_b = FakeBinding(binding_id='binding_b')
        logger = FakeLogger()

        # Store for binding_a
        store.apply_update_from_event(event, binding_a, descriptor, 'actor', 'preferred_language', 'en', logger)

        # binding_b should not see binding_a's state
        snapshot_b = store.build_snapshot_from_event(event, binding_b, descriptor)
        assert snapshot_b['actor'] == {}

        # binding_a should see its own state
        snapshot_a = store.build_snapshot_from_event(event, binding_a, descriptor)
        assert snapshot_a['actor']['preferred_language'] == 'en'


class TestStateStorePolicyEnforcement:
    """Tests for state policy enforcement."""

    def test_enable_state_false_returns_empty_snapshot(self):
        """enable_state=False should return all empty scopes."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        policy = StatePolicy(enable_state=False)
        binding = FakeBinding(state_policy=policy)
        logger = FakeLogger()

        # Even if state exists, snapshot should be empty
        store.apply_update_from_event(
            event, FakeBinding(), descriptor, 'conversation', 'key', 'value', logger
        )

        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation'] == {}
        assert snapshot['actor'] == {}
        assert snapshot['subject'] == {}
        assert snapshot['runner'] == {}

    def test_enable_state_false_rejects_update(self):
        """enable_state=False should reject state updates."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(conversation_id='conv_001')
        policy = StatePolicy(enable_state=False)
        binding = FakeBinding(state_policy=policy)
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value', logger
        )

        assert result is False
        assert len(logger.warnings) == 1
        assert 'disabled' in logger.warnings[0]

    def test_state_scopes_restricts_enabled_scopes(self):
        """state_scopes should restrict which scopes are enabled."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            actor=FakeActorContext(actor_id='user_001'),
        )
        # Only allow conversation scope
        policy = StatePolicy(state_scopes=['conversation'])
        binding = FakeBinding(state_policy=policy)
        logger = FakeLogger()

        # Conversation update should work
        result_conv = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value_conv', logger
        )
        assert result_conv is True

        # Actor update should be rejected
        result_actor = store.apply_update_from_event(
            event, binding, descriptor, 'actor', 'key', 'value_actor', logger
        )
        assert result_actor is False
        assert any('not enabled' in w for w in logger.warnings)

    def test_state_scopes_restricts_snapshot(self):
        """state_scopes should restrict which scopes appear in snapshot."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            actor=FakeActorContext(actor_id='user_001'),
        )
        # Only allow conversation scope
        policy = StatePolicy(state_scopes=['conversation'])
        binding = FakeBinding(state_policy=policy)
        logger = FakeLogger()

        # Store values for all scopes using a binding with all scopes enabled
        full_binding = FakeBinding()
        store.apply_update_from_event(event, full_binding, descriptor, 'conversation', 'conv_key', 'conv_val', logger)
        store.apply_update_from_event(event, full_binding, descriptor, 'actor', 'actor_key', 'actor_val', logger)

        # Snapshot with restricted binding should only have conversation
        snapshot = store.build_snapshot_from_event(event, binding, descriptor)
        assert snapshot['conversation']['conv_key'] == 'conv_val'
        assert snapshot['actor'] == {}  # Not enabled by policy

    def test_default_state_scopes_conversation_and_actor(self):
        """Default state_scopes should be conversation and actor only."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope(
            conversation_id='conv_001',
            subject=FakeSubjectContext(subject_id='msg_001'),
        )
        binding = FakeBinding()  # Uses default policy
        logger = FakeLogger()

        # Conversation should work (in default scopes)
        result_conv = store.apply_update_from_event(
            event, binding, descriptor, 'conversation', 'key', 'value', logger
        )
        assert result_conv is True

        # Subject should be rejected (not in default scopes)
        result_subject = store.apply_update_from_event(
            event, binding, descriptor, 'subject', 'key', 'value', logger
        )
        assert result_subject is False

    def test_runner_scope_restricted_by_policy(self):
        """Runner scope should be restricted by state_scopes."""
        store = RunnerScopedStateStore()
        descriptor = make_descriptor()
        event = FakeEventEnvelope()
        # Only allow conversation scope
        policy = StatePolicy(state_scopes=['conversation'])
        binding = FakeBinding(state_policy=policy)
        logger = FakeLogger()

        result = store.apply_update_from_event(
            event, binding, descriptor, 'runner', 'key', 'value', logger
        )

        assert result is False
        assert any('not enabled' in w for w in logger.warnings)