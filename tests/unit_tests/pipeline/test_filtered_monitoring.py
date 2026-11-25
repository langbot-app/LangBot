"""Messages dropped by pipeline rules say where they stopped (LANG-342)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.pipeline import entities, pipelinemgr
from langbot.pkg.pipeline.monitoring_helper import HANDLED_BY_VAR, MonitoringHelper
from langbot.pkg.pipeline.pool import get_query_execution_context


def _runtime(mock_app, sample_query, stages):
    runtime = pipelinemgr.RuntimePipeline.__new__(pipelinemgr.RuntimePipeline)
    runtime.ap = mock_app
    runtime.pipeline_entity = SimpleNamespace(uuid=sample_query.pipeline_uuid)
    runtime.stage_containers = [
        pipelinemgr.StageInstContainer(inst_name=name, inst=SimpleNamespace(process=process))
        for name, process in stages
    ]
    runtime._assert_execution_active = AsyncMock()
    return runtime


def _result(query, result_type):
    return entities.StageProcessResult(result_type=result_type, new_query=query)


def _interrupt(query, _name):
    return _result(query, entities.ResultType.INTERRUPT)


def _continue(query, _name):
    return _result(query, entities.ResultType.CONTINUE)


@pytest.mark.asyncio
async def test_daily_quota_interrupt_records_error_and_notifies_debug_chat(mock_app, sample_query, monkeypatch):
    from langbot.pkg.pipeline.ratelimit import daily_quota
    from langbot.pkg.platform.sources import websocket_adapter as ws

    quota = {
        'enforced': True,
        'limit': 2,
        'used': 2,
        'remaining': 0,
        'period': 'day',
        'timezone': 'UTC',
        'period_start': '2026-11-20T00:00:00Z',
        'resets_at': '2026-11-21T00:00:00Z',
    }
    monkeypatch.setattr(daily_quota, 'daily_message_quota', AsyncMock(return_value=(False, quota)))
    mock_app.deployment = SimpleNamespace(mode='cloud')
    mock_app.monitoring_service = AsyncMock()
    sample_query.variables.update(_monitoring_message_id='message', _cli_run_status='failed')
    context = get_query_execution_context(sample_query)
    adapter = ws.WebSocketAdapter.model_construct(ap=mock_app, logger=Mock(execution_context=context))
    adapter.websocket_person_session = ws.WebSocketSession(id='person')
    sample_query.adapter = adapter
    manager = AsyncMock()
    manager.get_connection_by_session_id.return_value = None
    manager.get_connection.return_value = None
    monkeypatch.setattr(ws, 'ws_connection_manager', manager)
    object.__setattr__(sample_query.message_event, '_langbot_pipeline_uuid', sample_query.pipeline_uuid)
    runtime = _runtime(mock_app, sample_query, [])
    result = await daily_quota.DailyMessageQuota(mock_app).process(sample_query, 'RequireDailyMessageQuota')
    assert result.result_type == entities.ResultType.INTERRUPT
    assert '2 per day' in result.user_notice
    await runtime._check_output(sample_query, result)
    assert sample_query.variables['_monitoring_has_error']
    event = manager.broadcast_to_pipeline.await_args.args[1]
    assert event['type'] == 'response'
    assert sample_query.variables['_cli_run_error'] == event['data']['error'] == result.structured_error
    assert result.structured_error['quota'] == quota
    assert mock_app.monitoring_service.record_error.await_args.kwargs['error_type'] == 'daily_message_quota_exceeded'
    assert mock_app.monitoring_service.update_message_status.await_args.kwargs['status'] == 'error'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'stage',
    [
        'BanSessionCheckStage',
        'GroupRespondRuleCheckStage',
        'PreContentFilterStage',
        'RequireRateLimitOccupancy',
    ],
)
async def test_filter_stage_interrupt_is_attributed(mock_app, sample_query, stage):
    sample_query.variables = {}
    later = Mock(side_effect=_continue)
    runtime = _runtime(mock_app, sample_query, [('PreProcessor', _continue), (stage, _interrupt), ('Next', later)])

    await runtime._execute_from_stage(0, sample_query)

    assert sample_query.variables[HANDLED_BY_VAR] == f'filtered:{stage}'
    later.assert_not_called()


@pytest.mark.asyncio
async def test_streaming_filter_interrupt_is_attributed(mock_app, sample_query):
    sample_query.variables = {}

    async def gen(query, _name):
        yield _result(query, entities.ResultType.INTERRUPT)

    runtime = _runtime(mock_app, sample_query, [('GroupRespondRuleCheckStage', gen)])

    await runtime._execute_from_stage(0, sample_query)

    assert sample_query.variables[HANDLED_BY_VAR] == 'filtered:GroupRespondRuleCheckStage'


@pytest.mark.asyncio
async def test_non_filter_interrupt_is_not_attributed(mock_app, sample_query):
    sample_query.variables = {}
    runtime = _runtime(mock_app, sample_query, [('MessageProcessor', _interrupt)])

    await runtime._execute_from_stage(0, sample_query)

    assert HANDLED_BY_VAR not in sample_query.variables


@pytest.mark.asyncio
async def test_existing_handler_is_kept(mock_app, sample_query):
    sample_query.variables = {HANDLED_BY_VAR: 'runner:plugin:a/b/default'}
    runtime = _runtime(mock_app, sample_query, [('PostContentFilterStage', _interrupt)])

    await runtime._execute_from_stage(0, sample_query)

    assert sample_query.variables[HANDLED_BY_VAR] == 'runner:plugin:a/b/default'


@pytest.mark.asyncio
async def test_finish_query_writes_filter_and_clears_runner(sample_query):
    service = SimpleNamespace(update_message_status=AsyncMock())
    ap = SimpleNamespace(monitoring_service=service, logger=Mock())
    sample_query.variables[HANDLED_BY_VAR] = 'filtered:BanSessionCheckStage'

    await MonitoringHelper.finish_query(ap, sample_query, 'user-message', 'success')

    service.update_message_status.assert_awaited_once_with(
        get_query_execution_context(sample_query),
        message_id='user-message',
        status='success',
        level='info',
        handled_by='filtered:BanSessionCheckStage',
        clear_runner_name=True,
    )
