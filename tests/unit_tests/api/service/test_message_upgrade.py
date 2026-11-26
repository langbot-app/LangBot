import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import sqlalchemy as sa

from langbot.pkg.api.application.contracts import ApplicationAPIException
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.entity.persistence.bot import Bot, BotAdmin
from langbot.pkg.entity.persistence.metadata import WorkspaceMetadata
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.persistence.message_upgrade_report import REPORT_PREFIX
from langbot.pkg.workspace.errors import WorkspaceNotFoundError


@pytest.fixture
def service():
    engine = sa.create_engine('sqlite://')
    route = {'id': 'chat', 'event_pattern': 'message.received', 'policy': {'output': {'misc': {'quote-origin': True}}}}
    with engine.begin() as conn:
        for model in (Bot, BotAdmin, WorkspaceMetadata, PluginSetting):
            model.__table__.create(conn)
        for ws in ('own', 'other'):
            conn.execute(
                sa.insert(Bot).values(
                    uuid=ws,
                    workspace_uuid=ws,
                    name=ws,
                    description='',
                    adapter='http',
                    adapter_config={},
                    event_bindings=[route],
                    message_policy={
                        'plugins': {'enable_all': False, 'plugins': [{'author': 'author', 'name': 'plugin'}]}
                    },
                )
            )
        for key, value in {
            '0059': {'route_overrides': [{'bot_uuid': 'own', 'route_id': 'chat'}]},
            '0060': {'enabled_plugins': {'own': {'author/plugin': [None]}}},
            'commands': {'original_prefixes': ['!']},
        }.items():
            conn.execute(
                sa.insert(WorkspaceMetadata).values(
                    workspace_uuid='own', key=REPORT_PREFIX + key, value=json.dumps(value)
                )
            )
        conn.execute(
            sa.insert(PluginSetting).values(
                workspace_uuid='own', plugin_author='langbot-team', plugin_name='EssentialCommands'
            )
        )

    async def execute(stmt):
        with engine.begin() as db:
            return db.execute(stmt)

    @contextlib.asynccontextmanager
    async def write(ws, **kwargs):
        with engine.begin() as conn:

            async def execute_owned(stmt):
                return conn.execute(stmt)

            yield SimpleNamespace(execute=execute_owned)

    app = SimpleNamespace(
        persistence_mgr=SimpleNamespace(execute_async=execute, tenant_write_uow=write),
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=None)),
        message_policy_mgr=Mock(),
        plugin_connector=SimpleNamespace(
            require_workspace_context=AsyncMock(), list_commands=AsyncMock(return_value=[]), delete_plugin=AsyncMock()
        ),
    )
    service = BotService(app)

    async def get_bots(ws):
        return [dict(row) for row in (await execute(sa.select(Bot).where(Bot.workspace_uuid == ws))).mappings()]

    service.get_bots = get_bots
    yield service
    engine.dispose()


async def test_current_checks_and_workspace_confirmations(service):
    items = (await service.list_upgrade_checks('own'))['items']
    assert {item['code'] for item in items} == {
        'equivalent_route_policies',
        'command_plugin_enabled',
        'command_admin_missing',
        'plugin_command_collision',
        'chat_settings_moved',
        'command_prefix_changed',
    }
    await service.confirm_upgrade_checks('own', items[0]['id'])
    assert sum(item['confirmed'] for item in (await service.list_upgrade_checks('own'))['items']) == 1
    await service.confirm_upgrade_checks('own', None)
    assert all(item['confirmed'] for item in (await service.list_upgrade_checks('own'))['items'])
    assert not any(item['confirmed'] for item in (await service.list_upgrade_checks('other'))['items'])
    with pytest.raises(ApplicationAPIException):
        await service.apply_upgrade_action('other', 'plugin_command_collision', 'uninstall_essential')
    service.ap.plugin_connector.delete_plugin.assert_not_awaited()
    await service.apply_upgrade_action('own', 'plugin_command_collision', 'uninstall_essential')
    service.ap.plugin_connector.delete_plugin.assert_awaited_once_with(
        'langbot-team', 'EssentialCommands', delete_data=False
    )


async def test_promotion_is_workspace_scoped_and_rechecks(service):
    with pytest.raises(WorkspaceNotFoundError):
        await service.promote_route_policy('other', 'own')
    result = await service.promote_route_policy('own', 'own')
    assert result['changes_unrouted_commands']
    service.ap.message_policy_mgr.invalidate_bot.assert_called_once_with('own', 'own')
    bot = (await service.get_bots('own'))[0]
    assert bot['message_policy']['output']['misc']['quote-origin']
    assert 'policy' not in bot['event_bindings'][0]
    with pytest.raises(ApplicationAPIException) as exc:
        await service.promote_route_policy('own', 'own')
    assert exc.value.error.code == 'policy_promotion_not_equivalent'
