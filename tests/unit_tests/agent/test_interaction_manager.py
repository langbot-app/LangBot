"""Tests for structured interaction authorization and delivery."""

from __future__ import annotations

from types import SimpleNamespace
import time

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.event import ActorContext
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.agent_runner.interaction import (
    InteractionDeliveryCapabilities,
    InteractionSubmission,
)

from langbot.pkg.agent.runner.errors import RunnerProtocolError
from langbot.pkg.agent.runner.host_models import (
    AgentBinding,
    AgentEventEnvelope,
    BindingScope,
    DeliveryPolicy,
)
from langbot.pkg.agent.runner.interaction_manager import InteractionManager
from langbot.pkg.agent.runner.interaction_store import InteractionStore
from langbot.pkg.entity.persistence.base import Base


class FakeAdapter:
    def __init__(self, *, supports_interactions: bool, fail_updates: bool = False):
        self.supports_interactions = supports_interactions
        self.fail_updates = fail_updates
        self.actions: list[tuple[str, dict]] = []
        self.messages: list[tuple[str, str, object]] = []

    def get_supported_apis(self):
        return ['interaction.request', 'interaction.acknowledge'] if self.supports_interactions else ['send_message']

    async def call_platform_api(self, action: str, params: dict):
        self.actions.append((action, params))
        if action == 'interaction.request' and params.get('update_target') and self.fail_updates:
            raise RuntimeError('update unavailable')
        update_target = params.get('update_target') or {}
        message_id = update_target.get('message_id') or f'message-{len(self.actions)}'
        card_id = update_target.get('card_id') or f'card-{len(self.actions)}'
        sequence = int(update_target.get('sequence') or 0) + (1 if update_target else 0)
        return {
            'ok': True,
            'message_id': message_id,
            'card_id': card_id,
            'sequence': sequence,
            'rich': True,
        }

    async def send_message(self, target_type: str, target_id: str, message_chain):
        self.messages.append((target_type, target_id, message_chain))


@pytest.fixture
async def store(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "manager.db"}', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield InteractionStore(engine)
    await engine.dispose()


@pytest.fixture
def event():
    return AgentEventEnvelope(
        event_id='evt-1',
        event_type='message.received',
        source='platform',
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor=ActorContext(actor_type='user', actor_id='user-1'),
        input=AgentInput(text='start'),
        delivery=DeliveryContext(
            surface='platform',
            reply_target={'target_type': 'group', 'target_id': 'chat-1'},
        ),
    )


@pytest.fixture
def binding():
    return AgentBinding(
        binding_id='binding-1',
        scope=BindingScope(scope_type='agent', scope_id='pipeline-1'),
        runner_id='plugin:test/ApprovalRunner/default',
        delivery_policy=DeliveryPolicy(enable_interactions=True),
        processor_type='pipeline',
        processor_id='pipeline-1',
    )


def _descriptor(*, permitted: bool = True):
    return SimpleNamespace(
        id='plugin:test/ApprovalRunner/default',
        capabilities=SimpleNamespace(interactions=permitted),
        permissions=SimpleNamespace(interactions=['request'] if permitted else []),
    )


def _result():
    return {
        'type': 'action.requested',
        'data': {
            'action': 'interaction.requested',
            'target': {'target_type': 'person', 'target_id': 'attacker-selected'},
            'payload': {
                'interaction_id': 'form-1',
                'kind': 'choice',
                'title': 'Approve request?',
                'actions': [
                    {'id': 'approve', 'label': 'Approve', 'style': 'primary'},
                    {'id': 'reject', 'label': 'Reject', 'style': 'danger'},
                ],
                'fallback_text': 'Reply approve or reject.',
            },
        },
    }


@pytest.mark.asyncio
async def test_structured_delivery_uses_frozen_target_and_persists_request(store, event, binding):
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)

    consumed = await manager.handle_result(
        result_dict=_result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )

    assert consumed is True
    assert adapter.actions[0][0] == 'interaction.request'
    params = adapter.actions[0][1]
    assert params['reply_target'] == {'target_type': 'group', 'target_id': 'chat-1'}
    assert params['callback_token']
    assert 'attacker-selected' not in str(params)

    record = await store.get_request('run-1', 'form-1')
    assert record is not None
    assert record['processor_type'] == 'pipeline'
    assert record['processor_id'] == 'pipeline-1'
    assert record['actor_id'] == 'user-1'
    assert record['expires_at'] is not None
    assert 0 < record['expires_at'] - time.time() <= 30 * 60
    assert record['delivery_result']['message_id'] == 'message-1'


@pytest.mark.asyncio
async def test_continuous_interaction_reuses_submitted_platform_presentation(store, event, binding):
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)
    event.delivery.interactions = InteractionDeliveryCapabilities(supports_updates=True)

    await manager.handle_result(
        result_dict=_result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )
    first_token = adapter.actions[0][1]['callback_token']
    submitted = await manager.consume_callback(
        callback_token=first_token,
        submission={'interaction_id': 'form-1', 'action_id': 'approve', 'values': {}},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )
    await manager.acknowledge_submission(submitted, adapter)

    event.event_type = 'interaction.submitted'
    event.input.interaction = InteractionSubmission(
        interaction_id='form-1',
        action_id='approve',
    )
    second_result = _result()
    second_result['data']['payload']['interaction_id'] = 'form-2'
    await manager.handle_result(
        result_dict=second_result,
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-2',
        adapter_context={'_delivery_adapter': adapter},
    )

    assert [action for action, _ in adapter.actions] == [
        'interaction.request',
        'interaction.acknowledge',
        'interaction.request',
    ]
    update_params = adapter.actions[-1][1]
    assert update_params['update_target']['message_id'] == 'message-1'
    assert update_params['update_target']['sequence'] == 1
    second_record = await store.get_request('run-2', 'form-2')
    assert second_record['replaces_interaction_id'] == 'form-1'
    assert second_record['delivery_result']['message_id'] == 'message-1'
    assert second_record['delivery_result']['sequence'] == 2


@pytest.mark.asyncio
async def test_interaction_update_failure_falls_back_to_new_presentation(store, event, binding):
    adapter = FakeAdapter(supports_interactions=True, fail_updates=True)
    manager = InteractionManager(SimpleNamespace(), store=store)
    event.delivery.interactions = InteractionDeliveryCapabilities(supports_updates=True)

    await manager.handle_result(
        result_dict=_result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )
    first_token = adapter.actions[0][1]['callback_token']
    await manager.consume_callback(
        callback_token=first_token,
        submission={'interaction_id': 'form-1', 'action_id': 'approve', 'values': {}},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )

    event.input.interaction = InteractionSubmission(interaction_id='form-1', action_id='approve')
    second_result = _result()
    second_result['data']['payload']['interaction_id'] = 'form-2'
    await manager.handle_result(
        result_dict=second_result,
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-2',
        adapter_context={'_delivery_adapter': adapter},
    )

    update_attempt = adapter.actions[-2][1]
    fallback_attempt = adapter.actions[-1][1]
    assert update_attempt['update_target']['message_id'] == 'message-1'
    assert 'update_target' not in fallback_attempt
    assert fallback_attempt['callback_token'] == update_attempt['callback_token']


@pytest.mark.asyncio
async def test_callback_scope_uses_frozen_delivery_conversation(store, event, binding):
    event.conversation_id = 'runner-owned-external-conversation'
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)

    await manager.handle_result(
        result_dict=_result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )

    record = await store.get_request('run-1', 'form-1')
    assert record['conversation_id'] == 'group_chat-1'


@pytest.mark.asyncio
async def test_adapter_without_interactions_receives_fallback_text(store, event, binding):
    adapter = FakeAdapter(supports_interactions=False)
    manager = InteractionManager(SimpleNamespace(), store=store)

    assert await manager.handle_result(
        result_dict=_result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )

    assert adapter.actions == []
    target_type, target_id, message_chain = adapter.messages[0]
    assert (target_type, target_id) == ('group', 'chat-1')
    assert str(message_chain) == 'Reply approve or reject.'


@pytest.mark.asyncio
async def test_runner_without_interaction_permission_is_rejected(store, event, binding):
    manager = InteractionManager(SimpleNamespace(), store=store)

    with pytest.raises(RunnerProtocolError, match='did not declare'):
        await manager.handle_result(
            result_dict=_result(),
            event=event,
            binding=binding,
            descriptor=_descriptor(permitted=False),
            run_id='run-1',
            adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
        )

    assert await store.get_request('run-1', 'form-1') is None


@pytest.mark.asyncio
async def test_binding_policy_can_disable_interactions(store, event, binding):
    manager = InteractionManager(SimpleNamespace(), store=store)
    binding.delivery_policy.enable_interactions = False

    with pytest.raises(RunnerProtocolError, match='delivery policy'):
        await manager.handle_result(
            result_dict=_result(),
            event=event,
            binding=binding,
            descriptor=_descriptor(),
            run_id='run-1',
            adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('expires_at', 'error'),
    [
        (lambda now: 0, 'already expired'),
        (lambda now: now - 1, 'already expired'),
        (lambda now: now + 24 * 60 * 60 + 1, 'exceeds 24 hours'),
    ],
)
async def test_interaction_expiry_is_bounded(store, event, binding, expires_at, error):
    result = _result()
    result['data']['payload']['expires_at'] = expires_at(int(time.time()))
    manager = InteractionManager(SimpleNamespace(), store=store)

    with pytest.raises(RunnerProtocolError, match=error):
        await manager.handle_result(
            result_dict=result,
            event=event,
            binding=binding,
            descriptor=_descriptor(),
            run_id='run-1',
            adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
        )


@pytest.mark.asyncio
async def test_interaction_rejects_duplicate_protocol_ids(store, event, binding):
    result = _result()
    result['data']['payload']['actions'].append({'id': 'approve', 'label': 'Approve again'})
    manager = InteractionManager(SimpleNamespace(), store=store)

    with pytest.raises(RunnerProtocolError, match='duplicate action IDs'):
        await manager.handle_result(
            result_dict=result,
            event=event,
            binding=binding,
            descriptor=_descriptor(),
            run_id='run-1',
            adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
        )


@pytest.mark.asyncio
async def test_interaction_request_payload_is_bounded(store, event, binding):
    result = _result()
    result['data']['payload']['fields'] = [
        {
            'id': f'field-{field_index}',
            'label': 'Field',
            'type': 'select',
            'options': [
                {
                    'value': f'{field_index}-{option_index}',
                    'label': 'x' * 512,
                }
                for option_index in range(100)
            ],
        }
        for field_index in range(10)
    ]
    manager = InteractionManager(SimpleNamespace(), store=store)

    with pytest.raises(RunnerProtocolError, match='exceeds 256 KiB'):
        await manager.handle_result(
            result_dict=result,
            event=event,
            binding=binding,
            descriptor=_descriptor(),
            run_id='run-1',
            adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
        )


@pytest.mark.asyncio
async def test_non_interaction_action_is_not_consumed(store, event, binding):
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = _result()
    result['data']['action'] = 'platform.message.delete'

    assert not await manager.handle_result(
        result_dict=result,
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': FakeAdapter(supports_interactions=True)},
    )


async def _deliver_interaction(store, event, binding, result=None):
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)
    await manager.handle_result(
        result_dict=result or _result(),
        event=event,
        binding=binding,
        descriptor=_descriptor(),
        run_id='run-1',
        adapter_context={'_delivery_adapter': adapter},
    )
    return manager, adapter.actions[0][1]['callback_token']


@pytest.mark.asyncio
async def test_callback_action_ref_resolves_persisted_action_and_ignores_forged_id(store, event, binding):
    manager, callback_token = await _deliver_interaction(store, event, binding)

    resumed = await manager.consume_callback(
        callback_token=callback_token,
        submission={
            'interaction_id': 'attacker-selected',
            'action_ref': 1,
            'values': {},
        },
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )

    assert resumed['submission']['interaction_id'] == 'form-1'
    assert resumed['submission']['action_id'] == 'reject'


@pytest.mark.asyncio
async def test_callback_submission_time_is_host_owned(store, event, binding):
    manager, callback_token = await _deliver_interaction(store, event, binding)
    before = int(time.time())

    resumed = await manager.consume_callback(
        callback_token=callback_token,
        submission={'action_ref': 0, 'submitted_at': 1},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )

    assert before <= resumed['submission']['submitted_at'] <= int(time.time())
    assert resumed['submitted_at'] == resumed['submission']['submitted_at']


@pytest.mark.asyncio
async def test_callback_option_refs_resolve_persisted_field_and_value(store, event, binding):
    result = _result()
    result['data']['payload']['fields'] = [
        {
            'id': 'priority',
            'label': 'Priority',
            'type': 'select',
            'options': [
                {'value': 'normal', 'label': 'Normal'},
                {'value': 'urgent', 'label': 'Urgent'},
            ],
        }
    ]
    manager, callback_token = await _deliver_interaction(store, event, binding, result)

    resumed = await manager.consume_callback(
        callback_token=callback_token,
        submission={'field_ref': 0, 'option_ref': 1},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )

    assert resumed['submission']['interaction_id'] == 'form-1'
    assert resumed['submission']['values'] == {'priority': 'urgent'}


@pytest.mark.asyncio
async def test_callback_rejects_out_of_range_reference(store, event, binding):
    manager, callback_token = await _deliver_interaction(store, event, binding)

    with pytest.raises(ValueError, match='action reference is invalid'):
        await manager.consume_callback(
            callback_token=callback_token,
            submission={'action_ref': 99},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )

    pending = await store.get_request('run-1', 'form-1')
    assert pending is not None
    assert pending['status'] == 'pending'


@pytest.mark.asyncio
async def test_callback_rejects_negative_reference(store, event, binding):
    manager, callback_token = await _deliver_interaction(store, event, binding)

    with pytest.raises(ValueError, match='action reference is invalid'):
        await manager.consume_callback(
            callback_token=callback_token,
            submission={'action_ref': -1},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )


@pytest.mark.asyncio
async def test_callback_rejects_action_not_present_in_request(store, event, binding):
    manager, callback_token = await _deliver_interaction(store, event, binding)

    with pytest.raises(ValueError, match='action is not present'):
        await manager.consume_callback(
            callback_token=callback_token,
            submission={'action_id': 'attacker-selected'},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )


@pytest.mark.asyncio
async def test_callback_rejects_option_not_present_in_request(store, event, binding):
    result = _result()
    result['data']['payload']['fields'] = [
        {
            'id': 'priority',
            'label': 'Priority',
            'type': 'select',
            'options': [{'value': 'normal', 'label': 'Normal'}],
        }
    ]
    manager, callback_token = await _deliver_interaction(store, event, binding, result)

    with pytest.raises(ValueError, match='option is not present'):
        await manager.consume_callback(
            callback_token=callback_token,
            submission={'values': {'priority': 'attacker-selected'}},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )
