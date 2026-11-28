from types import SimpleNamespace
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager

import pytest

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.api.http.service.workflow import WorkflowExecutionFailedError
from langbot_plugin.api.entities.builtin.platform import events, message
from tests.unit_tests.platform.test_botmgr_execution_trace import make_bot, message_received_event, TEST_CONTEXT
from tests.factories import text_query


def workflow_bot(workflow):
    binding = {'id': 'route', 'event_pattern': '*', 'target_type': 'workflow', 'target_uuid': 'workflow-1'}
    bot, _, _ = make_bot([binding])
    bot.ap.workflow_service = SimpleNamespace(
        get_workflow=AsyncMock(return_value=workflow), execute_workflow=AsyncMock()
    )
    bot.adapter.reply_message = AsyncMock()
    bot.adapter.send_message = AsyncMock()
    bot._record_event_route_trace = AsyncMock()
    return bot, binding


@pytest.mark.asyncio
async def test_workflow_message_replies_through_adapter():
    bot, binding = workflow_bot({'uuid': 'workflow-1', 'is_enabled': True})

    async def execute(context, workflow_uuid, **kwargs):
        assert context == TEST_CONTEXT
        assert kwargs['message_context'].message_content == 'hello'
        assert kwargs['message_context'].conversation_id == 'user-1'
        await kwargs['runtime'].reply(message.MessageChain([message.Plain(text='world')]))

    bot.ap.workflow_service.execute_workflow.side_effect = execute
    await bot._dispatch_eba_event_to_processor(message_received_event(), bot.adapter)
    bot.adapter.reply_message.assert_awaited_once()
    assert str(bot.adapter.reply_message.call_args.args[1]) == 'world'
    assert bot._record_event_route_trace.call_args.kwargs['status'] == 'delivered'


@pytest.mark.asyncio
@pytest.mark.parametrize('workflow', [None, {'is_enabled': False}])
async def test_missing_or_disabled_workflow(workflow):
    bot, binding = workflow_bot(workflow)
    await bot._dispatch_eba_workflow(message_received_event(), bot.adapter, binding)
    assert bot._record_event_route_trace.call_args.kwargs['failure_code'] == 'processor_not_found'
    bot.ap.workflow_service.get_workflow.assert_awaited_once_with(TEST_CONTEXT, 'workflow-1')
    bot.ap.workflow_service.execute_workflow.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_rejects_non_message_event():
    bot, binding = workflow_bot({'is_enabled': True})
    event = events.PlatformSpecificEvent(platform='test', action='test', data={})
    await bot._dispatch_eba_workflow(event, bot.adapter, binding)
    assert bot._record_event_route_trace.call_args.kwargs['failure_code'] == 'processor_incompatible'
    bot.ap.workflow_service.get_workflow.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_failure_is_traced():
    bot, binding = workflow_bot({'is_enabled': True})
    bot.ap.workflow_service.execute_workflow.side_effect = WorkflowExecutionFailedError('execution', 'failed')
    await bot._dispatch_eba_workflow(message_received_event(), bot.adapter, binding)
    trace = bot._record_event_route_trace.call_args.kwargs
    assert trace['status'] == 'failed'
    assert trace['failure_code'] == 'runner_failed'


@pytest.mark.asyncio
async def test_binding_cannot_select_invisible_workflow():
    bot, binding = workflow_bot(None)
    binding['event_pattern'] = 'message.received'
    service = BotService(bot.ap)
    with pytest.raises(ValueError, match='Workflow not found'):
        await service._normalize_event_bindings(TEST_CONTEXT, [binding])
    bot.ap.workflow_service.get_workflow.assert_awaited_once_with(TEST_CONTEXT, 'workflow-1')


@pytest.mark.parametrize('result', ['drop', 'intercept', 'mute', 'rewrite', 'block', 'send'])
async def test_workflow_policy_and_hooks(result):
    bot, binding = workflow_bot({'is_enabled': True})
    event = message_received_event()
    query = text_query('hello')
    active = False

    @asynccontextmanager
    async def admit(entry):
        nonlocal active
        assert entry is query
        active = True
        yield 'safety.rate-limit' if result == 'drop' else None
        active = False

    async def hook(payload, plugins):
        assert active and plugins == ['test/listener']
        if type(payload).__name__ == 'NormalMessageResponded':
            # Plugins see the raw reply before the outbound policy, as on the Agent path.
            bot.adapter.reply_message.assert_not_awaited()
            policy.prepare_reply_chain.assert_not_awaited()
            assert payload.response_text == str(event.message_chain)
            return SimpleNamespace(
                event=SimpleNamespace(
                    reply_message_chain=None,
                    response_text='rewritten' if result == 'rewrite' else payload.response_text,
                ),
                is_prevented_default=lambda: result == 'mute',
            )
        return SimpleNamespace(
            event=SimpleNamespace(user_message_alter='changed', reply_message_chain=None),
            is_prevented_default=lambda: result == 'intercept',
        )

    prepared = message.MessageChain([message.Plain(text='prepared')])
    policy = SimpleNamespace(
        admit=admit,
        quote_origin=True,
        prepare_reply_chain=AsyncMock(return_value=None if result == 'block' else prepared),
        ap=bot.ap,
    )
    bot.ap.plugin_connector = SimpleNamespace(emit_event=AsyncMock(side_effect=hook))
    object.__setattr__(query, '_message_policy', policy)
    object.__setattr__(query, '_listener_plugins', ['test/listener'])
    object.__setattr__(event, '_entry_query', query)

    async def execute(context, target, *, message_context, runtime, **kwargs):
        assert active and message_context.message_content == 'changed'
        reason = await runtime.reply(event.message_chain)
        assert reason == {'block': 'outbound_block', 'mute': 'plugin_prevented'}.get(result)

    bot.ap.workflow_service.execute_workflow.side_effect = execute
    await bot._dispatch_eba_event_to_processor(event, bot.adapter, binding)
    assert not active
    trace = bot._record_event_route_trace.call_args.kwargs
    if result == 'drop':
        assert (trace['status'], trace['failure_code']) == ('discarded', 'message_policy')
        bot.ap.plugin_connector.emit_event.assert_not_awaited()
    elif result == 'intercept':
        assert (trace['target_type'], trace['details']['hook']) == ('plugin', 'NormalMessageReceived')
    elif result == 'mute':
        policy.prepare_reply_chain.assert_not_awaited()
    elif result == 'rewrite':
        assert str(policy.prepare_reply_chain.call_args.args[1]) == 'rewritten'
    if result in ('drop', 'intercept'):
        bot.ap.workflow_service.execute_workflow.assert_not_awaited()
    if result not in ('send', 'rewrite'):
        bot.adapter.reply_message.assert_not_awaited()
    else:
        bot.adapter.reply_message.assert_awaited_once_with(
            message_source=query.message_event, message=prepared, quote_origin=True
        )


async def test_workflow_dry_run_previews_route_policy():
    from langbot.pkg.message_policy.manager import MessagePolicyManager
    from tests.factories import FakeApp

    app = FakeApp()
    app.message_policy_mgr = MessagePolicyManager(app)
    app.workflow_service = SimpleNamespace(get_workflow=AsyncMock(return_value={'name': 'Echo'}))
    binding = {
        'id': 'route',
        'event_pattern': 'message.received',
        'target_type': 'workflow',
        'target_uuid': 'echo',
        'policy': {'trigger': {'ignore-rules': {'prefix': ['skip']}}},
    }
    service = BotService(app)
    service.get_bot = AsyncMock(return_value={'event_bindings': [binding]})
    for text, code in [('hello', None), ('skip this', 'message_policy')]:
        result = await service.dry_run_event_route(
            TEST_CONTEXT,
            TEST_CONTEXT.bot_uuid,
            'message.received',
            {'chat_id': 'p', 'user_id': 'p', 'message_text': text},
        )
        assert (result['target_type'], result['target_uuid'], result['failure_code']) == ('workflow', 'echo', code)
