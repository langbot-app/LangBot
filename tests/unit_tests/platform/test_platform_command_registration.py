from __future__ import annotations

import asyncio
import datetime
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.platform.command_registration import (
    DISCORD_COMMANDS,
    TELEGRAM_COMMANDS,
    PlatformCommandEvent,
    PlatformCommandRegistrar,
    build_command_plan,
    command_sets,
    command_set_hash,
)
from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter
from tests.unit_tests.platform.test_discord_eba_adapter import make_adapter
from tests.unit_tests.platform.test_bot_command_routing import make_bot
from langbot_plugin.api.entities.builtin.platform import events, message


def command(name, owner='author/first', description=None):
    return SimpleNamespace(
        owner=owner, metadata=SimpleNamespace(name=name, description=description or {'en_US': name, 'zh_Hans': '画图'})
    )


def settings(selected, enabled=True):
    return {'enabled': True, 'platform_commands': {'enabled': enabled, 'selected': selected}}


def test_effective_selection_uses_processor_priority_and_workspace_language():
    manifests = [command('draw', 'author/second', {'en_US': 'second'}), command('draw'), command('help')]
    plan = build_command_plan(
        settings(['draw', 'missing']), manifests, ['author/first', 'author/second'], TELEGRAM_COMMANDS, 'zh-Hans'
    )
    assert plan['commands'][0]['description'] == '画图'
    assert [item['name'] for item in plan['commands']] == ['draw']
    assert plan['rejected'] == [{'name': 'missing', 'reason': 'unavailable'}]
    assert command_sets(plan, 'telegram', 'zh-Hans')['zh'][0]['description'] == '画图'


@pytest.mark.parametrize(
    'capability,name,valid',
    [
        (TELEGRAM_COMMANDS, 'a' * 32, True),
        (TELEGRAM_COMMANDS, 'a' * 33, False),
        (TELEGRAM_COMMANDS, 'bad-name', False),
        (TELEGRAM_COMMANDS, 'Upper', False),
        (DISCORD_COMMANDS, '画图', True),
        (DISCORD_COMMANDS, 'test-name', True),
        (DISCORD_COMMANDS, 'Upper', False),
        (DISCORD_COMMANDS, 'two words', False),
        (DISCORD_COMMANDS, 'ทดสอบ', True),
    ],
)
def test_official_platform_name_limits(capability, name, valid):
    plan = build_command_plan(settings([name]), [command(name)], ['author/first'], capability, 'en-US')
    assert bool(plan['commands']) == valid
    if not valid:
        assert plan['rejected'][0]['reason'] == 'invalid_name'


def test_description_and_count_limits_report_each_reason():
    manifests = [
        command('long', description={'en_US': 'x' * 101}),
        command('localized', description={'en_US': 'ok', 'zh_Hans': 'x' * 101}),
        command('first'),
        command('second'),
    ]
    plan = build_command_plan(
        settings(['long', 'localized', 'first', 'second']),
        manifests,
        ['author/first'],
        replace(DISCORD_COMMANDS, max_commands=1),
        'en-US',
    )
    assert [item['reason'] for item in plan['rejected']] == [
        'invalid_description',
        'invalid_localized_description',
        'command_limit',
    ]
    assert [item['name'] for item in plan['commands']] == ['first']


def test_disabled_registration_or_command_processing_produces_empty_sets():
    for value in [settings(['draw'], False), {**settings(['draw']), 'enabled': False}]:
        plan = build_command_plan(value, [command('draw')], ['author/first'], TELEGRAM_COMMANDS, 'en-US')
        assert command_sets(plan, 'telegram', 'en-US') == {'': []}


def test_unselected_invalid_commands_are_not_reported_as_rejected():
    plan = build_command_plan(
        settings(['draw']), [command('Bad'), command('draw')], ['author/first'], TELEGRAM_COMMANDS, 'en-US'
    )
    assert plan['rejected'] == []
    assert plan['available'][0]['reason'] == 'invalid_name'


def test_hash_is_stable_and_tracks_description_changes():
    assert command_set_hash({'en': [], '': []}) == command_set_hash({'': [], 'en': []})
    assert command_set_hash({'': [{'name': 'draw', 'description': 'a'}]}) != command_set_hash(
        {'': [{'name': 'draw', 'description': 'b'}]}
    )


def test_adapter_list_and_detail_expose_the_same_registration_capability():
    from langbot.pkg.platform.botmgr import PlatformManager

    component = SimpleNamespace(
        metadata=SimpleNamespace(name='telegram'), to_plain_dict=lambda: {'name': 'telegram', 'spec': {}}
    )
    manager = SimpleNamespace(adapter_components=[component], adapter_dict={'telegram': TelegramAdapter})
    listing = PlatformManager.get_available_adapters_info(manager)
    detail = PlatformManager.get_available_adapter_info_by_name(manager, 'telegram')
    assert listing == [detail]
    assert detail['spec']['command_registration']['max_commands'] == 100


@pytest.mark.asyncio
async def test_telegram_registration_uses_default_scope_and_language_codes():
    adapter = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))
    result = await TelegramAdapter.sync_platform_commands(
        adapter, {'': [{'name': 'draw', 'description': 'Draw'}], 'zh': []}
    )
    assert result == {'success': True}
    calls = adapter.bot.set_my_commands.await_args_list
    assert calls[0].args[0][0].to_dict() == {'command': 'draw', 'description': 'Draw'}
    assert calls[0].kwargs['scope'].to_dict() == {'type': 'default'}
    assert calls[0].kwargs['language_code'] == ''
    assert calls[1].args == ([],)
    assert calls[1].kwargs['language_code'] == 'zh'


@pytest.mark.asyncio
async def test_discord_bulk_registration_contains_optional_args_and_localizations():
    adapter = make_adapter()
    adapter.bot.http.bulk_upsert_global_commands = AsyncMock()
    assert isinstance(adapter, PlatformCommandRegistrar)
    await adapter.sync_platform_commands(
        {'': [{'name': 'draw', 'description': 'Draw'}], 'zh-CN': [{'name': 'draw', 'description': '画图'}]}
    )
    call = adapter.bot.http.bulk_upsert_global_commands.await_args
    assert call.args == (123,)
    payload = call.kwargs['payload'][0]
    assert payload['description_localizations'] == {'zh-CN': '画图'}
    assert payload['options'][0]['type'] == 3
    assert payload['options'][0]['name'] == 'args'
    assert payload['options'][0]['required'] is False
    await adapter.sync_platform_commands({'': []})
    assert adapter.bot.http.bulk_upsert_global_commands.await_args.kwargs['payload'] == []


@pytest.mark.asyncio
async def test_discord_defers_before_dispatch_and_replies_through_followup():
    adapter = make_adapter()
    adapter.configure_platform_commands('!', AsyncMock())
    interaction = Mock(spec=discord.Interaction)
    interaction.type = discord.InteractionType.application_command
    interaction.data = {'type': 1, 'name': 'draw', 'options': [{'name': 'args', 'value': 'cat'}]}
    interaction.user = SimpleNamespace(id=42, name='user')
    interaction.id = 99
    interaction.guild_id = 100
    interaction.channel_id = 200
    interaction.channel = SimpleNamespace(name='chat')
    interaction.created_at = datetime.datetime.now(datetime.timezone.utc)
    interaction.response = SimpleNamespace(defer=AsyncMock())
    interaction.followup = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=101)))
    captured = []

    async def receive(event, source):
        interaction.response.defer.assert_awaited_once_with(thinking=True)
        captured.append(event)

    adapter.register_listener(events.EBAEvent, receive)
    await adapter.bot.on_interaction(interaction)
    event = captured[0]
    assert isinstance(event, PlatformCommandEvent)
    assert event.platform_command is True
    assert str(event.message_chain) == '!draw cat'
    bot = make_bot(
        {'enabled': True, 'prefixes': ['#'], 'processors': [{'processor_uuid': 'proc-first', 'enabled': True}]}
    )
    bot.ap.plugin_connector.list_commands.return_value = [command('draw')]
    matched = await bot._match_plugin_command(event)
    assert matched[1:3] == ('draw', 'draw cat')
    result = await adapter.reply_message(event.to_legacy_event(), message.MessageChain([message.Plain(text='done')]))
    interaction.followup.send.assert_awaited_once_with(content='done', files=[], wait=True)
    assert result.message_id == 101


def sync_service():
    adapter = SimpleNamespace(
        command_registration_capability=lambda: DISCORD_COMMANDS,
        sync_platform_commands=AsyncMock(return_value={'success': True}),
    )
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)
    runtime = SimpleNamespace(
        adapter=adapter,
        assert_execution_active=AsyncMock(),
        _platform_command_sync_lock=asyncio.Lock(),
        bot_entity=SimpleNamespace(),
    )
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=runtime)),
        plugin_connector=SimpleNamespace(require_workspace_context=AsyncMock()),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
    )
    service = BotService(ap)
    bot = {
        'adapter': 'discord',
        'platform_command_sync': {},
        'command_settings': settings(['draw']),
        'platform_command_registration': build_command_plan(
            settings(['draw']), [command('draw')], ['author/first'], DISCORD_COMMANDS, 'en-US'
        ),
    }
    service.get_bot = AsyncMock(return_value=bot)
    return service, context, bot, adapter


@pytest.mark.asyncio
async def test_sync_deduplicates_success_and_clears_previous_locales_on_disable():
    service, context, bot, adapter = sync_service()
    first = await service.sync_platform_commands(context, 'bot')
    assert first['error'] is None
    bot['platform_command_sync'] = first
    assert (await service.sync_platform_commands(context, 'bot'))['skipped'] is True
    assert adapter.sync_platform_commands.await_count == 1
    bot['command_settings']['platform_commands']['enabled'] = False
    bot['platform_command_registration']['commands'] = []
    cleared = await service.sync_platform_commands(context, 'bot')
    assert cleared['hash'] != first['hash']
    assert all(not commands for commands in adapter.sync_platform_commands.await_args.args[0].values())
    assert 'zh-CN' in adapter.sync_platform_commands.await_args.args[0]


@pytest.mark.asyncio
async def test_sync_failure_keeps_previous_hash_and_retries():
    service, context, bot, adapter = sync_service()
    adapter.sync_platform_commands.side_effect = RuntimeError('remote failure')
    failed = await service.sync_platform_commands(context, 'bot')
    assert 'hash' not in failed
    assert failed['error'] == 'remote failure'
    bot['platform_command_sync'] = failed
    adapter.sync_platform_commands.side_effect = None
    assert (await service.sync_platform_commands(context, 'bot'))['error'] is None
    assert adapter.sync_platform_commands.await_count == 2


@pytest.mark.asyncio
async def test_never_enabled_registration_does_not_clear_manual_commands():
    service, context, bot, adapter = sync_service()
    bot['command_settings']['platform_commands']['enabled'] = False
    assert await service.sync_platform_commands(context, 'bot') == {'status': 'disabled'}
    adapter.sync_platform_commands.assert_not_awaited()


@pytest.mark.asyncio
async def test_discord_ready_triggers_synchronization():
    adapter = make_adapter()
    callback = AsyncMock()
    adapter.configure_platform_commands('/', callback)
    await adapter.bot.on_ready()
    callback.assert_awaited_once()


@pytest.mark.asyncio
async def test_workspace_refresh_does_not_synchronize_another_tenant_or_generation():
    from langbot.pkg.platform.botmgr import PlatformManager

    service, context, bot, adapter = sync_service()
    manager = SimpleNamespace(
        bots=[
            SimpleNamespace(
                workspace_uuid='workspace',
                placement_generation=1,
                adapter=adapter,
                bot_entity=SimpleNamespace(uuid='one'),
            ),
            SimpleNamespace(
                workspace_uuid='other', placement_generation=1, adapter=adapter, bot_entity=SimpleNamespace(uuid='two')
            ),
            SimpleNamespace(
                workspace_uuid='workspace',
                placement_generation=2,
                adapter=adapter,
                bot_entity=SimpleNamespace(uuid='three'),
            ),
        ],
        ap=SimpleNamespace(bot_service=SimpleNamespace(sync_platform_commands=AsyncMock()), logger=Mock()),
    )
    await PlatformManager.sync_workspace_commands(manager, context)
    manager.ap.bot_service.sync_platform_commands.assert_awaited_once_with(context, 'one')


@pytest.mark.asyncio
async def test_failed_registration_retains_attempted_locales_for_later_clear():
    service, context, bot, adapter = sync_service()
    adapter.sync_platform_commands.side_effect = RuntimeError('partial remote failure')
    failed = await service.sync_platform_commands(context, 'bot')
    assert 'zh-CN' in failed['locales']
    bot['platform_command_sync'] = failed
    bot['command_settings']['platform_commands']['enabled'] = False
    bot['platform_command_registration']['commands'] = []
    adapter.sync_platform_commands.side_effect = None
    await service.sync_platform_commands(context, 'bot')
    assert adapter.sync_platform_commands.await_args.args[0]['zh-CN'] == []


@pytest.mark.asyncio
async def test_platform_errors_redact_adapter_credentials_before_persistence():
    service, context, bot, adapter = sync_service()
    adapter.config = {'token': 'test-only-secret'}
    adapter.sync_platform_commands.side_effect = RuntimeError('Rejected token test-only-secret')
    state = await service.sync_platform_commands(context, 'bot')
    assert state['error'] == 'Rejected token ***'
    assert 'test-only-secret' not in str(service.ap.persistence_mgr.execute_async.await_args)


@pytest.mark.asyncio
async def test_telegram_sync_starts_after_application_is_ready():
    order = []

    async def started():
        order.append('started')

    async def synced():
        order.append('synced')

    adapter = SimpleNamespace(
        application=SimpleNamespace(
            initialize=AsyncMock(),
            updater=SimpleNamespace(start_polling=AsyncMock()),
            start=AsyncMock(side_effect=started),
        ),
        bot=SimpleNamespace(get_me=AsyncMock(return_value=SimpleNamespace(username='test_bot'))),
        _command_sync=AsyncMock(side_effect=synced),
        logger=SimpleNamespace(info=AsyncMock()),
    )
    await TelegramAdapter.run_async(adapter)
    assert order == ['started', 'synced']


@pytest.mark.asyncio
async def test_plugin_install_enable_change_and_removal_refresh_command_menus():
    from langbot.pkg.plugin.connector import PluginRuntimeConnector

    context = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)
    desired = SimpleNamespace(binding=SimpleNamespace(installation_uuid='one'), enabled=True)
    handler = SimpleNamespace(remove_plugin_installation=AsyncMock(), unregister_installation_binding=Mock())
    connector = SimpleNamespace(
        is_enable_plugin=True,
        handler=handler,
        _runtime_handler=lambda: handler,
        _state_lock=asyncio.Lock(),
        _load_workspace_settings=AsyncMock(return_value=[]),
        _load_workspace_desired_states=AsyncMock(return_value=[desired]),
        _workspace_installations={},
        _known_desired_states={},
        _installation_failures={},
        _apply_desired_state=AsyncMock(),
        _refresh_platform_commands=AsyncMock(),
    )
    await PluginRuntimeConnector._synchronize_workspace(connector, context)
    connector._refresh_platform_commands.assert_awaited_once_with(context)
    await PluginRuntimeConnector._synchronize_workspace(connector, context)
    assert connector._refresh_platform_commands.await_count == 1
    connector._load_workspace_desired_states.return_value = [SimpleNamespace(binding=desired.binding, enabled=False)]
    await PluginRuntimeConnector._synchronize_workspace(connector, context)
    assert connector._refresh_platform_commands.await_count == 2
    connector._load_workspace_desired_states.return_value = []
    await PluginRuntimeConnector._synchronize_workspace(connector, context)
    assert connector._refresh_platform_commands.await_count == 3
    handler.remove_plugin_installation.assert_awaited_once_with(desired.binding)
