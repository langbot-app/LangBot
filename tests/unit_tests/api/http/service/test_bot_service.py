from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.sql.dml import Update

from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.entity.persistence.bot import Bot
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


WORKSPACE_UUID = 'workspace-a'


async def test_bind_event_route_compares_and_swaps_the_database_snapshot(tmp_path):
    from langbot.pkg.entity.persistence.pipeline import LegacyPipeline

    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'bindings.db'))
    selected = {
        'id': 'private',
        'event_pattern': 'message.received',
        'target_type': 'discard',
        'target_uuid': '',
        'order': 1,
    }
    other = {'id': 'group', 'filters': [{'field': 'group'}], 'enabled': False}
    subscriptions = [{'processor_uuid': 'keep'}]
    with engine.begin() as db:
        Bot.__table__.create(db)
        db.execute(
            sa.insert(Bot).values(
                uuid='bot',
                workspace_uuid=WORKSPACE_UUID,
                name='bot',
                description='',
                adapter='http',
                adapter_config={'secret': 'keep'},
                event_bindings=[other, selected],
                plugin_processors=subscriptions,
            )
        )
        db.exec_driver_sql(f'CREATE TABLE {LegacyPipeline.__tablename__} (uuid TEXT, workspace_uuid TEXT)')
        db.exec_driver_sql(f'INSERT INTO {LegacyPipeline.__tablename__} VALUES (?, ?)', ('target', WORKSPACE_UUID))
    interrupt = False

    async def execute(statement):
        with engine.begin() as db:
            if interrupt and isinstance(statement, Update):
                db.execute(sa.update(Bot).values(event_bindings=[dict(other, enabled=True), selected]))
            return db.execute(statement)

    service = BotService(SimpleNamespace(persistence_mgr=SimpleNamespace(execute_async=execute)))
    service._apply_bot_configuration = AsyncMock()
    args = (WORKSPACE_UUID, 'bot', selected, 'pipeline', 'target')
    plan = await service.bind_event_route(*args, dry_run=True)
    assert plan['changed'] and plan['dry_run']
    with pytest.raises(WorkspaceNotFoundError):
        await service.bind_event_route('other-workspace', *args[1:])
    with pytest.raises(ValueError, match='Pipeline not found'):
        await service.bind_event_route(*args[:-1], 'missing')
    interrupt = True
    with pytest.raises(ApplicationAPIException) as conflict:
        await service.bind_event_route(*args)
    assert conflict.value.error.status_code == 409
    service._apply_bot_configuration.assert_not_awaited()
    interrupt = False
    saved = await service.bind_event_route(*args)
    assert saved['binding'] == plan['binding'] and not saved['dry_run']
    with pytest.raises(ApplicationAPIException):
        await service.bind_event_route(*args)
    repeated = await service.bind_event_route(*args[:2], saved['binding'], *args[3:])
    assert not repeated['changed']
    service._apply_bot_configuration.assert_awaited_once_with(WORKSPACE_UUID, 'bot')
    with engine.connect() as db:
        bot = db.execute(sa.select(Bot)).one()
        assert bot.event_bindings == [dict(other, enabled=True), saved['binding']]
        assert bot.plugin_processors == subscriptions and bot.adapter_config == {'secret': 'keep'}
    engine.dispose()


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
                key: value
                for key, value in statement.compile().params.items()
                if not key.startswith(('uuid_', 'workspace_uuid_'))
            }
            return None

        return _FakeResult(SimpleNamespace(name='Updated Pipeline'))


async def test_add_bot_admin_rejects_group_launcher():
    service = BotService(SimpleNamespace())

    with pytest.raises(ValueError, match='person'):
        await service.add_bot_admin(WORKSPACE_UUID, 'bot-1', 'group', 'group-1')


async def test_update_bot_copies_input_before_filtering_legacy_routing_fields():
    persistence_mgr = _PersistenceManager()
    runtime_bot = SimpleNamespace(enable=False, bot_entity=SimpleNamespace(name='Test Bot'))
    platform_mgr = SimpleNamespace(
        get_bot_by_uuid=AsyncMock(return_value=runtime_bot),
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
        'pipeline_routing_rules': [{'type': 'launcher_type'}],
    }

    await service.update_bot(WORKSPACE_UUID, 'bot-1', payload)

    # caller's dict must not be mutated
    assert payload == {
        'uuid': 'caller-owned-uuid',
        'name': 'Test Bot',
        'use_pipeline_uuid': 'pipeline-1',
        'pipeline_routing_rules': [{'type': 'launcher_type'}],
    }
    # legacy routing fields are stripped; only name is persisted
    assert persistence_mgr.update_values == {'name': 'Test Bot'}
