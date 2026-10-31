from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.api.http.service.workflow import WorkflowExecutionFailedError
from langbot_plugin.api.entities.builtin.platform import events, message
from tests.unit_tests.platform.test_botmgr_execution_trace import make_bot, message_received_event, TEST_CONTEXT


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
