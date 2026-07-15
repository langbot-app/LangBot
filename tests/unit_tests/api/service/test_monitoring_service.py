from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.monitoring import MonitoringService


class _MonitoringMessageRow:
    """Match the Row shape returned by Core connections for ORM selects."""

    id = 'message-1'
    bot_id = 'bot-1'
    bot_name = 'QA Bot'
    pipeline_id = 'pipeline-1'
    pipeline_name = 'QA Pipeline'
    session_id = 'person_1'

    def __getitem__(self, index: int) -> str:
        assert index == 0
        return self.id


@pytest.mark.asyncio
async def test_record_tool_call_uses_full_monitoring_message_row_for_context():
    message_row = _MonitoringMessageRow()
    select_result = Mock(first=Mock(return_value=message_row))
    insert_result = Mock()
    persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(side_effect=[select_result, insert_result]),
    )
    service = MonitoringService(SimpleNamespace(persistence_mgr=persistence_mgr))

    await service.record_tool_call(
        tool_name='exec',
        tool_source='native',
        duration=12,
        message_id='message-1',
    )

    insert_statement = persistence_mgr.execute_async.await_args_list[1].args[0]
    values = insert_statement.compile().params
    assert values['bot_id'] == 'bot-1'
    assert values['pipeline_id'] == 'pipeline-1'
    assert values['session_id'] == 'person_1'
    assert values['message_id'] == 'message-1'
