from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.pipeline import PipelineService


@pytest.mark.asyncio
async def test_update_pipeline_filters_protected_fields_without_mutating_input(mock_app):
    service = PipelineService(mock_app)
    loaded_pipeline = Mock()
    service.get_pipeline = AsyncMock(return_value=loaded_pipeline)

    bot = Mock(uuid='bot-uuid')
    bot_result = Mock(all=Mock(return_value=[bot]))
    mock_app.persistence_mgr.execute_async = AsyncMock(side_effect=[None, bot_result])
    mock_app.bot_service = Mock(update_bot=AsyncMock())
    mock_app.pipeline_mgr = Mock(remove_pipeline=AsyncMock(), load_pipeline=AsyncMock())
    mock_app.sess_mgr.session_list = []

    pipeline_data = {
        'uuid': 'caller-uuid',
        'for_version': '1.0.0',
        'stages': ['CallerStage'],
        'is_default': True,
        'name': 'Updated pipeline',
    }
    original_pipeline_data = pipeline_data.copy()

    await service.update_pipeline('pipeline-uuid', pipeline_data)

    assert pipeline_data == original_pipeline_data

    update_stmt = mock_app.persistence_mgr.execute_async.await_args_list[0].args[0]
    updated_fields = {getattr(field, 'key', str(field)) for field in update_stmt._values}
    assert updated_fields == {'name'}

    mock_app.bot_service.update_bot.assert_awaited_once_with(
        'bot-uuid',
        {'use_pipeline_name': 'Updated pipeline'},
    )
    mock_app.pipeline_mgr.remove_pipeline.assert_awaited_once_with('pipeline-uuid')
    mock_app.pipeline_mgr.load_pipeline.assert_awaited_once_with(loaded_pipeline)
