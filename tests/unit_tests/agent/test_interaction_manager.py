"""Blocking interaction and callback authorization tests."""

import asyncio
import time
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionDeliveryCapabilities,
    InteractionHandle,
    InteractionRequest,
)
from langbot.pkg.agent.runner.interaction_manager import InteractionManager
from langbot.pkg.agent.runner.interaction_store import (
    InteractionAlreadySubmittedError,
    InteractionExpiredError,
    InteractionNotFoundError,
    InteractionScopeError,
    InteractionStore,
)
from langbot.pkg.entity.persistence.base import Base


def _session():
    return {
        'run_id': 'run-1',
        'runner_id': 'plugin:test/Runner/default',
        'runtime_context': {'deadline_at': time.time() + 300},
        'authorization': {
            'binding_id': 'binding-1',
            'processor_type': 'agent',
            'processor_id': 'agent-1',
            'bot_id': 'bot-1',
            'workspace_id': 'workspace-1',
            'thread_id': None,
            'interactions_enabled': True,
            'interactions_authorized': True,
            'platform_context': {
                'actor': {'actor_id': 'user-1'},
                'delivery': {'reply_target': {'target_type': 'group', 'target_id': 'chat-1'}},
            },
        },
    }


def _request(**changes):
    return {
        'interaction_id': 'approval',
        'title': 'Approve?',
        'actions': [{'id': 'yes', 'label': 'Yes'}, {'id': 'no', 'label': 'No'}],
        **changes,
    }


class Adapter:
    def __init__(self, native=True):
        self.native = native
        self.sent = asyncio.Event()
        self.token = None
        self.updates = []
        self.messages = []

    def get_supported_apis(self):
        return ['send_interaction', 'update_interaction', 'send_message'] if self.native else ['send_message']

    def get_interaction_capabilities(self):
        return InteractionDeliveryCapabilities(
            field_types=['text', 'select'] if self.native else [],
            action_styles=['default', 'primary'] if self.native else [],
            max_fields=8 if self.native else None,
            max_actions=6 if self.native else None,
            supports_updates=self.native,
        )

    async def send_interaction(self, target_type, target_id, request, callback_token, reply_to=None):
        self.token = callback_token
        self.sent.set()
        return InteractionHandle(message_id='card-1')

    async def update_interaction(self, handle, state, submission=None):
        self.updates.append(state)
        return handle

    async def send_message(self, target_type, target_id, message):
        self.messages.append(str(message))
        self.sent.set()


@pytest.fixture
async def store(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "interactions.db"}')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield InteractionStore(engine)
    await engine.dispose()


async def _start(manager, adapter, *, request=None):
    task = asyncio.create_task(
        manager.request_interaction(
            session=_session(),
            adapter=adapter,
            request_payload=request or _request(),
            timeout=2,
            on_unsupported='error',
            responders='actor',
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    return task


def _callback(token, **overrides):
    return {
        **dict(
            callback_token=token,
            submission={'action_ref': 0},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        ),
        **overrides,
    }


@pytest.mark.asyncio
async def test_callback_is_single_use_and_stays_in_same_run(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = await _start(manager, adapter)
    record = await manager.consume_callback(**_callback(adapter.token, submission={'action_ref': 0, 'action_id': 'no'}))
    assert record['run_id'] == 'run-1'
    assert manager.wake_waiter(record, 'user-1')
    assert (await task)['submission']['action_id'] == 'yes'
    assert adapter.updates == ['submitted']
    with pytest.raises(InteractionAlreadySubmittedError):
        await manager.consume_callback(**_callback(adapter.token))


@pytest.mark.asyncio
async def test_forged_token_actor_and_conversation_do_not_consume(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = await _start(manager, adapter)
    with pytest.raises(InteractionNotFoundError):
        await manager.consume_callback(**_callback('forged'))
    for override in ({'actor_id': 'attacker'}, {'conversation_id': 'group-other'}, {'bot_id': 'bot-other'}):
        with pytest.raises(InteractionScopeError):
            await manager.consume_callback(**_callback(adapter.token, **override))
    assert (await store.get_request('run-1', 'approval'))['status'] == 'pending'
    record = await manager.consume_callback(**_callback(adapter.token))
    assert manager.wake_waiter(record, 'user-1')
    await task


@pytest.mark.asyncio
async def test_responder_list_rejects_other_actor_before_consuming(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = asyncio.create_task(
        manager.request_interaction(
            session=_session(),
            adapter=adapter,
            request_payload=_request(),
            timeout=2,
            on_unsupported='error',
            responders=['user-1'],
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    with pytest.raises(ValueError, match='allowed responder'):
        await manager.consume_callback(**_callback(adapter.token, actor_id='attacker'))
    assert (await store.get_request('run-1', 'approval'))['status'] == 'pending'
    record = await manager.consume_callback(**_callback(adapter.token))
    assert manager.wake_waiter(record, 'user-1')
    await task


@pytest.mark.asyncio
async def test_restart_cancels_pending_and_old_callback_expires(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = await _start(manager, adapter)
    assert await store.cancel_orphaned_pending(set()) == 1
    assert (await store.get_request('run-1', 'approval'))['status'] == 'cancelled'
    with pytest.raises(InteractionExpiredError):
        await manager.consume_callback(**_callback(adapter.token))
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_timeout_updates_card(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = await manager.request_interaction(
        session=_session(),
        adapter=adapter,
        request_payload=_request(),
        timeout=0.01,
        on_unsupported='error',
        responders='actor',
    )
    assert result['status'] == 'timeout'
    assert adapter.updates == ['expired']


@pytest.mark.asyncio
@pytest.mark.parametrize('policy', ['degrade', 'error'])
async def test_multi_field_form_never_splits_into_text_questions(store, policy):
    adapter = Adapter(native=False)
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = await manager.request_interaction(
        session=_session(),
        adapter=adapter,
        request_payload=_request(
            actions=[],
            fields=[
                {'id': 'first', 'label': 'First', 'type': 'text'},
                {'id': 'second', 'label': 'Second', 'type': 'text'},
            ],
        ),
        timeout=1,
        on_unsupported=policy,
        responders='actor',
    )
    assert result['unsupported']
    assert adapter.messages == []


@pytest.mark.asyncio
async def test_visual_degradation_keeps_native_form(store):
    adapter = Adapter()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = await _start(
        manager,
        adapter,
        request=_request(
            actions=[],
            fields=[
                {'id': 'name', 'label': 'Name', 'type': 'text', 'placeholder': 'Your name', 'default': 'Alex'},
            ],
        ),
    )
    record = await store.get_request('run-1', 'approval')
    assert record['request']['fields'][0]['placeholder'] is None
    assert record['request']['fields'][0]['default'] is None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize('policy', ['error', 'degrade'])
def test_structural_policy_and_visual_degradation_are_independent(policy):
    capabilities = InteractionDeliveryCapabilities(
        field_types=['text'],
        action_styles=['default'],
        max_fields=8,
        max_actions=2,
        text_fallback=True,
        supports_markdown=False,
    )
    structural = InteractionRequest.model_validate(
        _request(
            actions=[],
            fields=[{'id': 'count', 'label': 'Count', 'type': 'number'}],
        )
    )
    _, _, use_text, issues = InteractionManager._normalize_request(structural, capabilities, policy)
    if policy == 'error':
        assert use_text is False
        assert issues == [{'path': 'fields[0].type', 'reason': 'unsupported_field_type'}]
    else:
        assert use_text is True
        assert issues == []

    visual = InteractionRequest.model_validate(
        _request(
            description='**Approve**',
            actions=[{'id': 'yes', 'label': 'Yes', 'style': 'primary'}],
        )
    )
    normalized, degraded, use_text, issues = InteractionManager._normalize_request(visual, capabilities, policy)
    assert not use_text and not issues
    assert normalized.actions[0].style == 'default'
    assert {(item['path'], item['reason']) for item in degraded} == {
        ('actions[0].style', 'unsupported_style'),
        ('description', 'unsupported_markdown'),
    }
