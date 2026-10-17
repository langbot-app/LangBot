from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy

from langbot.pkg.entity.persistence.metadata import Metadata, WorkspaceMetadata
from langbot.pkg.api.http.service.bot import BotService


def test_metadata_supports_long_wizard_json():
    for model in (Metadata, WorkspaceMetadata):
        assert isinstance(model.__table__.c.value.type, sqlalchemy.Text)


@pytest.mark.asyncio
async def test_saved_bot_without_runtime_has_empty_logs():
    service = BotService(SimpleNamespace(platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=None))))
    service.get_bot = AsyncMock(return_value={'uuid': 'bot'})
    assert await service.list_event_logs('workspace', 'bot', 0, 20) == ([], 0)
