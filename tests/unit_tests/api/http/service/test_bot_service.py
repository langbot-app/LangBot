from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.sql.dml import Update

from langbot.pkg.api.http.service.bot import BotService


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _PersistenceManager:
    def __init__(self):
        self.update_values = None

    async def execute_async(self, statement):
        if isinstance(statement, Update):
            self.update_values = {
                key: value for key, value in statement.compile().params.items() if not key.startswith('uuid_')
            }
            return None

        return _FakeResult(SimpleNamespace(name='Updated Pipeline'))


async def test_update_bot_copies_input_before_filtering_and_setting_pipeline_name():
    persistence_mgr = _PersistenceManager()
    runtime_bot = SimpleNamespace(enable=False)
    platform_mgr = SimpleNamespace(
        remove_bot=AsyncMock(),
        load_bot=AsyncMock(return_value=runtime_bot),
    )
    ap = SimpleNamespace(
        persistence_mgr=persistence_mgr,
        platform_mgr=platform_mgr,
        sess_mgr=SimpleNamespace(session_list=[]),
    )
    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'uuid': 'bot-1'})
    payload = {
        'uuid': 'caller-owned-uuid',
        'name': 'Test Bot',
        'use_pipeline_uuid': 'pipeline-1',
    }

    await service.update_bot('bot-1', payload)

    assert payload == {
        'uuid': 'caller-owned-uuid',
        'name': 'Test Bot',
        'use_pipeline_uuid': 'pipeline-1',
    }
    assert persistence_mgr.update_values == {
        'name': 'Test Bot',
        'use_pipeline_uuid': 'pipeline-1',
        'use_pipeline_name': 'Updated Pipeline',
    }
