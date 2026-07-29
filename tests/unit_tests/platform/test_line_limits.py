from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from langbot.pkg.platform import botmgr as _botmgr  # noqa: F401
from langbot.pkg.platform.sources import line


def test_line_media_content_accepts_limit_boundary(monkeypatch) -> None:
    monkeypatch.setattr(line, 'MAX_LINE_MEDIA_BYTES', 4)
    content = b'1234'

    assert line._validate_line_media_content(content) is content


def test_line_media_content_rejects_oversized_payload(monkeypatch) -> None:
    monkeypatch.setattr(line, 'MAX_LINE_MEDIA_BYTES', 4)

    with pytest.raises(ValueError, match='LINE media exceeds'):
        line._validate_line_media_content(b'12345')


@pytest.mark.asyncio
async def test_line_kill_closes_api_client() -> None:
    api_client = MagicMock()
    adapter = line.LINEAdapter.model_construct(api_client=api_client)

    assert await adapter.kill() is True
    api_client.close.assert_called_once_with()
