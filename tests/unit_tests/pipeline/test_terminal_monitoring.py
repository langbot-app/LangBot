"""Terminal monitoring must not prevent query cleanup."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper
from langbot.pkg.pipeline.pipelinemgr import RuntimePipeline


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, RuntimeError('stage'), asyncio.CancelledError()])
async def test_terminal_cleanup(sample_query, failure):
    sample_query.variables['_monitoring_message_id'] = 'original'
    service = SimpleNamespace(update_message_status=AsyncMock())
    app = SimpleNamespace(
        monitoring_service=service, logger=Mock(), query_pool=SimpleNamespace(remove_query=AsyncMock())
    )
    runtime = SimpleNamespace(
        ap=app, _assert_execution_active=AsyncMock(), _process_query_body=AsyncMock(side_effect=failure)
    )
    if failure:
        with pytest.raises(type(failure)):
            await RuntimePipeline._process_query(runtime, sample_query)
    else:
        await RuntimePipeline._process_query(runtime, sample_query)
    assert service.update_message_status.await_args.kwargs['status'] == ('error' if failure else 'success')
    app.query_pool.remove_query.assert_awaited_once_with(sample_query)


@pytest.mark.asyncio
@pytest.mark.parametrize('failures', [1, 3])
async def test_terminal_write_retries_are_bounded(sample_query, failures):
    service = SimpleNamespace(update_message_status=AsyncMock(side_effect=[RuntimeError('db')] * failures + [None]))
    app = SimpleNamespace(monitoring_service=service, logger=Mock())
    await MonitoringHelper.finish_query(app, sample_query, 'original', 'error')
    assert service.update_message_status.await_count == min(failures + 1, 3)


@pytest.mark.asyncio
async def test_stale_placement_does_not_write(sample_query):
    sample_query.variables['_monitoring_message_id'] = 'original'
    service = SimpleNamespace(update_message_status=AsyncMock())
    app = SimpleNamespace(
        monitoring_service=service, logger=Mock(), query_pool=SimpleNamespace(remove_query=AsyncMock())
    )
    runtime = SimpleNamespace(
        ap=app, _assert_execution_active=AsyncMock(side_effect=RuntimeError('stale')), _process_query_body=AsyncMock()
    )
    await RuntimePipeline._process_query(runtime, sample_query)
    service.update_message_status.assert_not_awaited()
    app.query_pool.remove_query.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'veto,cancel_adapter,stage_error', [(True, False, False), (False, True, False), (False, False, True)]
)
async def test_real_body_early_exits(sample_query, veto, cancel_adapter, stage_error):
    service = SimpleNamespace(
        update_message_status=AsyncMock(), record_message=AsyncMock(return_value='original'), record_error=AsyncMock()
    )
    event = SimpleNamespace(is_prevented_default=lambda: veto, event=sample_query)
    app = SimpleNamespace(
        monitoring_service=service,
        logger=Mock(),
        query_pool=SimpleNamespace(remove_query=AsyncMock()),
        plugin_connector=SimpleNamespace(emit_event=AsyncMock(return_value=event)),
    )
    runtime = object.__new__(RuntimePipeline)
    runtime.ap = app
    runtime.pipeline_entity = SimpleNamespace(uuid='pipeline')
    runtime._assert_execution_active = AsyncMock()
    runtime._record_lane_failure = Mock()
    runtime._execute_from_stage = AsyncMock(side_effect=RuntimeError('stage') if stage_error else None)
    sample_query.pipeline_config = {}
    sample_query.adapter.on_monitoring_message_created = AsyncMock(
        side_effect=asyncio.CancelledError() if cancel_adapter else None
    )
    if cancel_adapter:
        with pytest.raises(asyncio.CancelledError):
            await runtime._process_query(sample_query)
    else:
        await runtime._process_query(sample_query)
    assert service.update_message_status.await_args.kwargs['status'] == (
        'error' if cancel_adapter or stage_error else 'success'
    )
    app.query_pool.remove_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_detail_survives_status_write_failure(sample_query):
    sample_query.variables['_monitoring_message_id'] = 'original'
    service = SimpleNamespace(
        update_message_status=AsyncMock(side_effect=RuntimeError('db')),
        record_message=AsyncMock(return_value='detail'),
        record_error=AsyncMock(),
    )
    app = SimpleNamespace(monitoring_service=service, logger=Mock())
    assert (
        await MonitoringHelper.record_query_error(
            app, sample_query, 'bot', 'bot', 'pipeline', 'pipeline', ValueError('failed')
        )
        == 'detail'
    )
    service.record_error.assert_awaited_once()
