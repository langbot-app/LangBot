from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.box.service import BoxService
from langbot_plugin.box.client import BoxRuntimeClient
from tests.unit_tests.box.test_box_service import make_app, make_query


@pytest.mark.asyncio
async def test_host_without_openat_uses_sandbox_attachment_channel(monkeypatch, tmp_path):
    monkeypatch.setattr('os.supports_dir_fd', set())
    service = BoxService(make_app(Mock()), client=Mock(spec=BoxRuntimeClient))
    service._available = True
    service._tenant_workspace = Mock(return_value=str(tmp_path))
    service._read_outbox_host = Mock(side_effect=AssertionError('POSIX host reader must not run'))
    service._read_outbox_via_exec = AsyncMock(return_value=[])
    service._clear_outbox = AsyncMock()
    query = make_query()
    assert service._host_query_dir(service.OUTBOX_SUBDIR, query) is None
    assert await service.collect_outbound_attachments(query) == []
    service._read_outbox_via_exec.assert_awaited_once_with(query)
    service._clear_outbox.assert_awaited_once_with(query, None)
