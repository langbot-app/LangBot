"""Tests for structured interaction authorization and delivery."""

from __future__ import annotations

from types import SimpleNamespace
import asyncio
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.event import ActorContext
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.interaction import (
    InteractionDeliveryCapabilities,
    InteractionHandle,
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
from langbot.pkg.entity.persistence.pipeline import LegacyPipeline

CONFIG = {
    'ai': {
        'runner': {'id': 'plugin:test/ApprovalRunner/default'},
        'runner_config': {'plugin:test/ApprovalRunner/default': {}},
    }
}


def _context(adapter):
    conversation = SimpleNamespace(pipeline_uuid='pipeline-1')
    query = SimpleNamespace(
        pipeline_uuid='pipeline-1', pipeline_config=CONFIG, session=SimpleNamespace(using_conversation=conversation)
    )
    return {
        '_delivery_adapter': adapter,
        '_query': query,
        '_pipeline_expected_config': CONFIG,
        '_pipeline_conversation': conversation,
    }


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
        await conn.execute(
            sa.insert(LegacyPipeline).values(
                uuid='pipeline-1',
                workspace_uuid='workspace-1',
                name='test',
                description='',
                for_version='4.11',
                stages=[],
                config=CONFIG,
                extensions_preferences={},
            )
        )
    yield InteractionStore(engine)
    await engine.dispose()


@pytest.fixture
def event():
    return AgentEventEnvelope(
        event_id='evt-1',
        event_type='message.received',
        source='platform',
        bot_id='bot-1',
        workspace_id='workspace-1',
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
        adapter_context=_context(adapter),
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
async def test_text_reply_consumes_latest_scoped_plain_form_once(store):
    async def create(interaction_id, *, field_type='textarea', rich=False):
        await store.create_request(
            interaction_id=interaction_id,
            run_id=f'run-{interaction_id}',
            binding_id='binding-1',
            runner_id='runner-1',
            processor_type='agent',
            processor_id='agent-1',
            request={
                'fields': [{'id': 'question', 'type': field_type}],
                'actions': [],
            },
            delivery_target={'target_type': 'person', 'target_id': 'user-1'},
            workspace_id='workspace-1',
            bot_id='bot-1',
            conversation_id='person_user-1',
            actor_id='user-1',
            expires_at=time.time() + 600,
        )
        await store.record_delivery_success(f'run-{interaction_id}', interaction_id, {'ok': True, 'rich': rich})

    async def reply(**overrides):
        scope = dict(
            workspace_id='workspace-1',
            bot_id='bot-1',
            conversation_id='person_user-1',
            actor_id='user-1',
            binding_id='binding-1',
            runner_id='runner-1',
            processor_id='agent-1',
            text='  answer  ',
            message_id='message-1',
        )
        scope.update(overrides)
        return await store.consume_text_reply(**scope)

    await create('old')
    await create('new')
    assert await reply(actor_id='user-2') is None
    assert await reply(conversation_id='person_user-2') is None
    assert await reply(workspace_id='workspace-2') is None
    assert await reply(text='   ') is None
    submitted = await reply()
    assert submitted['interaction_id'] == 'new'
    assert submitted['submission']['values'] == {'question': 'answer'}
    assert (await reply())['duplicate_text_reply'] is True
    assert await reply(message_id='message-2') is None
    assert (await store.get_request('run-old', 'old'))['status'] == 'pending'

    await create('rich', rich=True)
    assert await reply(message_id='message-3') is None
    await create('select', field_type='select')
    assert await reply(message_id='message-4') is None


@pytest.mark.asyncio
async def test_agent_tool_card_uses_host_token_and_persists_resume_target(store, event):
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)
    event.delivery.interactions = InteractionDeliveryCapabilities(
        field_types=['text', 'textarea', 'select', 'number'],
        action_styles=['default', 'primary', 'danger'],
        supports_updates=True,
        max_fields=1,
    )
    session = {
        'run_id': 'agent-run-1',
        'runner_id': 'plugin:test/CardAgent/default',
        'authorization': {
            'binding_id': 'agent-binding-1',
            'processor_type': 'agent',
            'processor_id': 'agent-1',
            'interactions_enabled': True,
            'bot_id': 'bot-1',
            'workspace_id': 'workspace-1',
            'thread_id': None,
            'platform_context': {
                'actor': {'actor_type': 'user', 'actor_id': 'user-1'},
                'delivery': event.delivery.model_dump(mode='json'),
            },
        },
    }
    request = {
        'interaction_id': 'card-host-generated',
        'kind': 'choice',
        'title': 'Choose priority',
        'fields': [
            {
                'id': 'priority',
                'label': 'Priority',
                'type': 'select',
                'options': [{'value': 'high', 'label': 'High'}],
            }
        ],
        'actions': [],
        'expires_at': int(time.time()) + 600,
        'fallback_text': 'Choose priority',
    }

    result = await manager.present_tool_request(request_payload=request, session=session, adapter=adapter)

    assert result['status'] == 'pending'
    assert 'callback_token' not in result
    params = adapter.actions[0][1]
    assert params['callback_token']
    assert params['reply_target'] == {'target_type': 'group', 'target_id': 'chat-1'}
    record = await store.get_request('agent-run-1', 'card-host-generated')
    assert record is not None
    assert record['processor_type'] == 'agent'
    assert record['processor_id'] == 'agent-1'
    assert record['binding_id'] == 'agent-binding-1'
    assert record['conversation_id'] == 'group_chat-1'
    assert record['actor_id'] == 'user-1'


@pytest.mark.asyncio
async def test_pipeline_tool_card_preserves_pipeline_authority(store, event):
    adapter = FakeAdapter(supports_interactions=True)
    manager = InteractionManager(SimpleNamespace(), store=store)
    event.delivery.interactions = InteractionDeliveryCapabilities(
        field_types=['select'],
        action_styles=['default', 'primary', 'danger'],
        supports_updates=True,
        max_fields=1,
    )
    conversation = SimpleNamespace(pipeline_uuid='pipeline-1')
    execution_query = SimpleNamespace(
        pipeline_uuid='pipeline-1',
        pipeline_config=CONFIG,
        session=SimpleNamespace(using_conversation=conversation),
    )
    session = {
        'run_id': 'pipeline-tool-run-1',
        'runner_id': 'plugin:test/ApprovalRunner/default',
        'execution_query': execution_query,
        'authorization': {
            'binding_id': 'pipeline-binding-1',
            'processor_type': 'pipeline',
            'processor_id': 'pipeline-1',
            'interactions_enabled': True,
            'bot_id': 'bot-1',
            'workspace_id': 'workspace-1',
            'thread_id': None,
            'platform_context': {
                'actor': {'actor_type': 'user', 'actor_id': 'user-1'},
                'delivery': event.delivery.model_dump(mode='json'),
            },
        },
    }
    request = {
        'interaction_id': 'pipeline-card-host-generated',
        'kind': 'choice',
        'title': 'Continue?',
        'actions': [
            {'id': 'confirm', 'label': 'Confirm', 'style': 'primary'},
            {'id': 'cancel', 'label': 'Cancel', 'style': 'default'},
        ],
        'fallback_text': 'Reply confirm or cancel.',
    }

    result = await manager.present_tool_request(request_payload=request, session=session, adapter=adapter)

    assert result['status'] == 'pending'
    record = await store.get_request('pipeline-tool-run-1', 'pipeline-card-host-generated')
    assert record is not None
    assert record['processor_type'] == 'pipeline'
    assert record['processor_id'] == 'pipeline-1'
    assert record['binding_id'] == 'pipeline-binding-1'


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
        adapter_context=_context(adapter),
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
        adapter_context=_context(adapter),
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
        adapter_context=_context(adapter),
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
        adapter_context=_context(adapter),
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
        adapter_context=_context(adapter),
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
        adapter_context=_context(adapter),
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
            adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
            adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
            adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
            adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
            adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
        adapter_context=_context(FakeAdapter(supports_interactions=True)),
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
        adapter_context=_context(adapter),
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


class BlockingAdapter:
    def __init__(self):
        self.sent = asyncio.Event()
        self.token = None
        self.updates = []

    def get_interaction_capabilities(self):
        return InteractionDeliveryCapabilities(
            action_styles=['default', 'primary', 'danger'],
            max_actions=6,
            supports_updates=True,
        )

    async def send_interaction(self, target_type, target_id, request, callback_token, reply_to=None):
        self.token = callback_token
        self.sent.set()
        return InteractionHandle(message_id='card-1')

    async def update_interaction(self, handle, state, submission=None):
        self.updates.append(state)
        return handle


class TextAdapter:
    def __init__(self):
        self.messages = []
        self.sent = asyncio.Event()

    def get_interaction_capabilities(self):
        return InteractionDeliveryCapabilities()

    async def send_message(self, target_type, target_id, message):
        self.messages.append(str(message))
        self.sent.set()


class BlockingStore:
    def __init__(self):
        self.record = None
        self.token = 'test-token'

    async def create_request(self, **data):
        self.record = {
            **data,
            'status': 'pending',
            'submission': None,
        }
        return self.record, self.token

    async def record_delivery_success(self, run_id, interaction_id, delivery_result):
        self.record['delivery_result'] = delivery_result

    async def get_by_callback_token(self, token):
        return self.record if token == self.token else None

    async def consume_submission(self, *, callback_token, submission, bot_id, conversation_id, actor_id, **kwargs):
        if self.record['status'] != 'pending':
            raise ValueError('Interaction was already submitted')
        if self.record['actor_id'] and self.record['actor_id'] != actor_id:
            raise ValueError('Actor mismatch')
        self.record['status'] = 'submitted'
        self.record['submission'] = submission
        return self.record

    async def mark_terminal(self, run_id, interaction_id, status):
        self.record['status'] = status
        return True

    async def mark_delivery_failed(self, run_id, interaction_id, reason):
        self.record['status'] = 'delivery_failed'
        return True


def _blocking_session():
    return {
        'run_id': 'blocking-run',
        'runner_id': 'plugin:test/ApprovalRunner/default',
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


@pytest.mark.asyncio
async def test_blocking_request_returns_submission_in_same_run():
    adapter = BlockingAdapter()
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    session = _blocking_session()
    original_deadline = session['runtime_context']['deadline_at']
    task = asyncio.create_task(
        manager.request_interaction(
            session=session,
            adapter=adapter,
            request_payload={
                'interaction_id': 'approval',
                'title': 'Approve?',
                'actions': [
                    {'id': 'yes', 'label': 'Yes'},
                    {'id': 'no', 'label': 'No'},
                ],
            },
            timeout=1,
            on_unsupported='error',
            responders='actor',
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    record = await manager.consume_callback(
        callback_token=adapter.token,
        submission={'action_ref': 0},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )
    assert manager.wake_waiter(record, 'user-1')
    result = await task
    assert result['status'] == 'submitted'
    assert result['submission']['action_id'] == 'yes'
    assert adapter.updates == ['submitted']
    assert original_deadline <= result['deadline_at'] < original_deadline + 1
    with pytest.raises(Exception):
        await manager.consume_callback(
            callback_token=adapter.token,
            submission={'action_ref': 1},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-1',
        )


@pytest.mark.asyncio
async def test_blocking_request_times_out_without_polling():
    adapter = BlockingAdapter()
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = await manager.request_interaction(
        session=_blocking_session(),
        adapter=adapter,
        request_payload={
            'interaction_id': 'timeout',
            'title': 'Approve?',
            'actions': [
                {'id': 'yes', 'label': 'Yes'},
            ],
        },
        timeout=0.02,
        on_unsupported='error',
        responders='actor',
    )
    assert result['status'] == 'timeout'
    assert adapter.updates == ['expired']
    record = await store.get_by_callback_token(adapter.token)
    assert record['status'] == 'expired'


@pytest.mark.asyncio
async def test_blocking_request_cancel_invalidates_card():
    adapter = BlockingAdapter()
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = asyncio.create_task(
        manager.request_interaction(
            session=_blocking_session(),
            adapter=adapter,
            request_payload={
                'interaction_id': 'cancel',
                'title': 'Approve?',
                'actions': [
                    {'id': 'yes', 'label': 'Yes'},
                ],
            },
            timeout=1,
            on_unsupported='error',
            responders='actor',
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.record['status'] == 'cancelled'
    assert adapter.updates == ['cancelled']
    assert not manager._waiters


@pytest.mark.asyncio
async def test_blocking_request_rejects_unlisted_responder_before_consuming():
    adapter = BlockingAdapter()
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = asyncio.create_task(
        manager.request_interaction(
            session=_blocking_session(),
            adapter=adapter,
            request_payload={
                'interaction_id': 'restricted',
                'title': 'Approve?',
                'actions': [
                    {'id': 'yes', 'label': 'Yes'},
                ],
            },
            timeout=1,
            on_unsupported='error',
            responders=['user-1'],
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    with pytest.raises(ValueError, match='allowed responder'):
        await manager.consume_callback(
            callback_token=adapter.token,
            submission={'action_ref': 0},
            bot_id='bot-1',
            conversation_id='group_chat-1',
            actor_id='user-2',
        )
    assert store.record['status'] == 'pending'
    record = await manager.consume_callback(
        callback_token=adapter.token,
        submission={'action_ref': 0},
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
    )
    assert manager.wake_waiter(record, 'user-1')
    assert (await task)['status'] == 'submitted'


@pytest.mark.asyncio
async def test_text_fallback_consumes_numbered_action():
    adapter = TextAdapter()
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    task = asyncio.create_task(
        manager.request_interaction(
            session=_blocking_session(),
            adapter=adapter,
            request_payload={
                'interaction_id': 'text-choice',
                'title': 'Approve?',
                'actions': [
                    {'id': 'yes', 'label': 'Yes'},
                    {'id': 'no', 'label': 'No'},
                ],
            },
            timeout=1,
            on_unsupported='degrade',
            responders='actor',
        )
    )
    await asyncio.wait_for(adapter.sent.wait(), 1)
    assert '1 Yes / 2 No' in adapter.messages[0]
    assert await manager.consume_text_message(
        workspace_id='workspace-1',
        bot_id='bot-1',
        conversation_id='group_chat-1',
        actor_id='user-1',
        text='2',
    )
    result = await task
    assert result['submission']['action_id'] == 'no'
    assert result['degraded'][-1]['applied'] == 'text_fallback'


@pytest.mark.asyncio
async def test_unsupported_error_does_not_persist_request():
    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = await manager.request_interaction(
        session=_blocking_session(),
        adapter=TextAdapter(),
        request_payload={'interaction_id': 'error', 'title': 'Approve?', 'actions': [{'id': 'yes', 'label': 'Yes'}]},
        timeout=1,
        on_unsupported='error',
        responders='actor',
    )
    assert result['unsupported'][0]['path'] == 'platform'
    assert store.record is None


@pytest.mark.asyncio
async def test_advertised_card_shape_without_send_api_is_unsupported():
    class UnavailableCardAdapter(BlockingAdapter):
        def get_supported_apis(self):
            return ['send_message']

    store = BlockingStore()
    manager = InteractionManager(SimpleNamespace(), store=store)
    result = await manager.request_interaction(
        session=_blocking_session(),
        adapter=UnavailableCardAdapter(),
        request_payload={
            'interaction_id': 'unavailable',
            'title': 'Approve?',
            'actions': [
                {'id': 'yes', 'label': 'Yes'},
            ],
        },
        timeout=1,
        on_unsupported='error',
        responders='actor',
    )
    assert result['unsupported'][0]['reason'] == 'native_interactions_unavailable'
    assert store.record is None
