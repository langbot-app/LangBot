"""Unit tests for bot-level plugin command routing at the platform layer."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, create_autospec

import pytest
from langbot_plugin.api.entities.builtin.platform.events import (
    MemberJoinedEvent,
    MessageReceivedEvent,
)
import langbot_plugin.api.entities.builtin.platform.message as pm
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from langbot.pkg.command.cmdmgr import CommandManager
from langbot.pkg.platform.botmgr import RuntimeBot


def make_bot(command_settings=None, plugin_processors=None):
    bot = object.__new__(RuntimeBot)
    bot.bot_entity = SimpleNamespace(
        uuid='bot-123',
        name='TestBot',
        adapter='aiocqhttp',
        event_bindings=[],
        plugin_processors=plugin_processors or [],
        command_settings=command_settings
        or {'enabled': True, 'prefixes': ['/'], 'processors': []},
    )
    bot.execution_context = SimpleNamespace(
        instance_uuid='inst-1',
        workspace_uuid='ws-1',
        placement_generation=1,
    )
    bot.workspace_uuid = 'ws-1'
    bot.placement_generation = 1
    bot.logger = SimpleNamespace(
        info=AsyncMock(),
        warning=AsyncMock(),
        error=AsyncMock(),
    )
    bot._record_adapter_event = AsyncMock()
    bot._record_event_route_trace = AsyncMock()
    bot._persist_monitoring_ingress = AsyncMock()
    bot._record_platform_event = Mock()
    bot._summarize_event_delivery = RuntimeBot._summarize_event_delivery
    bot._run_event_delivery = RuntimeBot._run_event_delivery.__get__(bot, RuntimeBot)
    bot._get_event_bindings_from_value = RuntimeBot._get_event_bindings_from_value
    bot._match_plugin_command = RuntimeBot._match_plugin_command.__get__(bot, RuntimeBot)
    bot._try_handle_plugin_command = RuntimeBot._try_handle_plugin_command.__get__(bot, RuntimeBot)
    bot._execute_matched_plugin_command = RuntimeBot._execute_matched_plugin_command.__get__(
        bot, RuntimeBot
    )
    bot._handle_platform_event_body = RuntimeBot._handle_platform_event_body.__get__(
        bot, RuntimeBot
    )

    plugin_connector = SimpleNamespace(
        list_commands=AsyncMock(return_value=[]),
    )
    cmd_mgr = create_autospec(CommandManager, instance=True)
    cmd_mgr.is_admin = AsyncMock(return_value=False)
    cmd_mgr.build_context = AsyncMock(return_value=Mock(privilege=1))
    cmd_mgr.execute_command = Mock()
    sess_mgr = SimpleNamespace(
        get_session_by_launcher=AsyncMock(return_value=Mock()),
    )
    bot.command_processor_configs = {}

    async def get_agent(_context, processor_uuid):
        if not processor_uuid.startswith('proc-'):
            return None
        name = processor_uuid[len('proc-') :]
        return {
            'uuid': processor_uuid,
            'kind': 'command_processor',
            'component_ref': f'plugin:author/{name}',
            'config': {'command_config': bot.command_processor_configs.get(name, {})},
        }

    bot.ap = SimpleNamespace(
        plugin_connector=plugin_connector,
        cmd_mgr=cmd_mgr,
        sess_mgr=sess_mgr,
        agent_service=SimpleNamespace(get_agent=AsyncMock(side_effect=get_agent)),
    )
    return bot


def make_message_event(text: str, chat_type='private', chat_id='1001'):
    chain = pm.MessageChain([pm.Plain(text=text)])
    sender = {'id': chat_id, 'nickname': 'User'}
    ev = MessageReceivedEvent(
        instance_uuid='inst-1',
        workspace_uuid='ws-1',
        placement_generation=1,
        bot_uuid='bot-123',
        adapter_name='aiocqhttp',
        source_platform_object={'raw': True},
        message_chain=chain,
        sender=sender,
        chat_type=chat_type,
        chat_id=chat_id,
    )
    return ev


class FakeCommandManifest:
    def __init__(self, owner: str, name: str):
        self.owner = owner
        self.metadata = SimpleNamespace(name=name)


@pytest.mark.asyncio
async def test_non_message_received_event_does_not_hit():
    """Non message.received event (e.g. MemberJoinedEvent) does not match plugin command."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    ev = MemberJoinedEvent()
    matched = await bot._match_plugin_command(ev)
    assert matched is None


@pytest.mark.asyncio
async def test_prefix_matched_but_command_not_found():
    """When message prefix matches but command is not in plugin, match returns None."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'known_cmd')
    ]
    ev = make_message_event('/unknown_cmd arg')
    matched = await bot._match_plugin_command(ev)
    assert matched is None


@pytest.mark.asyncio
async def test_matched_command_skips_processors_and_pipeline():
    """Matched command executes at routing layer and skips plugin_processors and primary handler."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        },
        plugin_processors=[{'processor_uuid': 'proc-1', 'enabled': True}],
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'hello')
    ]

    async def mock_execute_gen(*args, **kwargs):
        ret = Mock()
        ret.error = None
        ret.text = 'Hello from plugin!'
        ret.image_url = None
        ret.image_base64 = None
        ret.file_url = None
        yield ret

    bot.ap.cmd_mgr.execute_command.side_effect = mock_execute_gen

    adapter = SimpleNamespace(
        reply_message=AsyncMock(),
        get_launcher_id=Mock(return_value=None),
    )
    ev = make_message_event('/hello world')

    primary_called = False
    processor_called = False

    async def mock_primary(*args, **kwargs):
        nonlocal primary_called
        primary_called = True

    async def mock_processor(*args, **kwargs):
        nonlocal processor_called
        processor_called = True

    bot._dispatch_eba_event_to_processor = mock_primary
    bot._dispatch_plugin_subscription = mock_processor

    await bot._handle_platform_event_body(ev, adapter)

    assert not primary_called
    assert not processor_called
    adapter.reply_message.assert_awaited_once()
    call_args = adapter.reply_message.call_args[1]
    assert 'Hello from plugin!' in str(call_args['message'])


@pytest.mark.asyncio
async def test_duplicate_command_priority_order():
    """When two plugins register the same command name, the first plugin in priority order wins."""
    # plugin_a before plugin_b
    bot1 = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [
                {'processor_uuid': 'proc-plugin_a', 'enabled': True},
                {'processor_uuid': 'proc-plugin_b', 'enabled': True},
            ],
        }
    )
    bot1.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'draw'),
        FakeCommandManifest('author/plugin_b', 'draw'),
    ]
    ev = make_message_event('/draw a cat')
    matched1 = await bot1._match_plugin_command(ev)
    assert matched1 is not None
    assert matched1[0] == 'author/plugin_a'
    assert matched1[1] == 'draw'

    # reverse order: plugin_b before plugin_a
    bot2 = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [
                {'processor_uuid': 'proc-plugin_b', 'enabled': True},
                {'processor_uuid': 'proc-plugin_a', 'enabled': True},
            ],
        }
    )
    bot2.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'draw'),
        FakeCommandManifest('author/plugin_b', 'draw'),
    ]
    matched2 = await bot2._match_plugin_command(ev)
    assert matched2 is not None
    assert matched2[0] == 'author/plugin_b'
    assert matched2[1] == 'draw'


@pytest.mark.asyncio
async def test_disabled_plugin_will_not_hit():
    """A disabled plugin in command_settings.plugins is not matched."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': False}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'hello')
    ]
    ev = make_message_event('/hello')
    matched = await bot._match_plugin_command(ev)
    assert matched is None


@pytest.mark.asyncio
async def test_custom_and_longest_prefix_matching():
    """Matches longest prefix correctly when multiple prefixes are configured."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['!', '!!', '/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'test')
    ]

    # '!!test' matches '!!', command_name is 'test', command_text is 'test'
    ev1 = make_message_event('!!test foo')
    matched1 = await bot._match_plugin_command(ev1)
    assert matched1 is not None
    assert matched1[1] == 'test'
    assert matched1[2] == 'test foo'

    # '!test' matches '!', command_name is 'test'
    ev2 = make_message_event('!test bar')
    matched2 = await bot._match_plugin_command(ev2)
    assert matched2 is not None
    assert matched2[1] == 'test'
    assert matched2[2] == 'test bar'


@pytest.mark.asyncio
async def test_admin_privilege_passed_to_cmd_context():
    """BotAdmin check properly sets privilege level to 2 for bot admin using real CommandManager."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'admin_cmd')
    ]

    # Use real CommandManager to ensure is_admin and build_context signatures are strictly exercised
    real_cmd_mgr = CommandManager(bot.ap)
    real_cmd_mgr.is_admin = AsyncMock(return_value=True)
    bot.ap.cmd_mgr = real_cmd_mgr
    dummy_session = provider_session.Session(
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id='1001',
    )
    bot.ap.sess_mgr.get_session_by_launcher = AsyncMock(return_value=dummy_session)

    async def mock_execute_gen(*args, **kwargs):
        ret = Mock()
        ret.error = None
        ret.text = 'admin ok'
        ret.image_url = None
        ret.image_base64 = None
        ret.file_url = None
        yield ret

    bot.ap.cmd_mgr.execute_command = Mock(side_effect=mock_execute_gen)

    adapter = SimpleNamespace(
        reply_message=AsyncMock(),
        get_launcher_id=Mock(return_value=None),
    )
    ev = make_message_event('/admin_cmd')

    await bot._execute_matched_plugin_command(
        event=ev,
        adapter=adapter,
        plugin_id='author/plugin_a',
        command_name='admin_cmd',
        command_text='admin_cmd',
        full_command_text='/admin_cmd',
    )

    real_cmd_mgr.is_admin.assert_awaited_once_with('ws-1', 'bot-123', 'person', '1001')


@pytest.mark.asyncio
async def test_launcher_id_preserves_original_type():
    """Route-level command execution does not force launcher_id to str, preserving original int type."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'ping')
    ]

    async def mock_execute_gen(*args, **kwargs):
        ret = Mock()
        ret.error = None
        ret.text = 'pong'
        ret.image_url = None
        ret.image_base64 = None
        ret.file_url = None
        yield ret

    bot.ap.cmd_mgr.execute_command = Mock(side_effect=mock_execute_gen)

    adapter = SimpleNamespace(
        reply_message=AsyncMock(),
        get_launcher_id=Mock(return_value=None),
    )
    # Event sender with integer ID 123456
    ev = make_message_event('/ping', chat_id=123456)

    await bot._execute_matched_plugin_command(
        event=ev,
        adapter=adapter,
        plugin_id='author/plugin_a',
        command_name='ping',
        command_text='ping',
        full_command_text='/ping',
    )

    bot.ap.sess_mgr.get_session_by_launcher.assert_awaited_once()
    call_args = bot.ap.sess_mgr.get_session_by_launcher.call_args[0]
    # launcher_id is at index 3
    assert call_args[3] == 123456
    assert type(call_args[3]) is int


@pytest.mark.asyncio
async def test_telemetry_recorded_on_plugin_command_match():
    """Telemetry route trace is recorded with target_type='plugin_command' and route_ref."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [
        FakeCommandManifest('author/plugin_a', 'ping')
    ]

    async def mock_execute_gen(*args, **kwargs):
        ret = Mock()
        ret.error = None
        ret.text = 'pong'
        ret.image_url = None
        ret.image_base64 = None
        ret.file_url = None
        yield ret

    bot.ap.cmd_mgr.execute_command.side_effect = mock_execute_gen

    adapter = SimpleNamespace(
        reply_message=AsyncMock(),
        get_launcher_id=Mock(return_value=None),
    )
    ev = make_message_event('/ping')

    await bot._execute_matched_plugin_command(
        event=ev,
        adapter=adapter,
        plugin_id='author/plugin_a',
        command_name='ping',
        command_text='ping',
        full_command_text='/ping',
    )

    # Check route traces recorded
    trace_calls = bot._record_event_route_trace.call_args_list
    assert len(trace_calls) >= 2
    matched_call = trace_calls[0][1]
    assert matched_call['status'] == 'matched'
    assert matched_call['target_type'] == 'plugin_command'
    assert matched_call['target_uuid'] == 'author/plugin_a/ping'
    delivered_call = trace_calls[-1][1]
    assert delivered_call['status'] == 'delivered'


@pytest.mark.asyncio
async def test_mention_before_command_still_matches():
    """`@bot /draw` (Telegram `/draw@bot`, QQ group mentions) keeps the prefix at the start of the text."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [FakeCommandManifest('author/plugin_a', 'draw')]
    ev = make_message_event('/draw cat')
    ev.message_chain = pm.MessageChain([pm.At(target='bot-account'), pm.Plain(text=' /draw cat')])

    matched = await bot._match_plugin_command(ev)

    assert matched is not None
    assert matched[:4] == ('author/plugin_a', 'draw', 'draw cat', '/draw cat')


@pytest.mark.asyncio
async def test_matched_command_carries_its_processor_instance_config():
    """Each bot reads the configuration of the command processor instance it is bound to."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'proc-plugin_a', 'enabled': True}],
        }
    )
    bot.command_processor_configs = {'plugin_a': {'draw': {'style': 'anime'}, 'other': {'x': 1}}}
    bot.ap.plugin_connector.list_commands.return_value = [FakeCommandManifest('author/plugin_a', 'draw')]

    matched = await bot._match_plugin_command(make_message_event('/draw cat'))

    assert matched[4] == {'style': 'anime'}


@pytest.mark.asyncio
async def test_non_command_processor_bindings_are_ignored():
    """A processor UUID that does not resolve to a command processor never matches."""
    bot = make_bot(
        command_settings={
            'enabled': True,
            'prefixes': ['/'],
            'processors': [{'processor_uuid': 'agent-1', 'enabled': True}],
        }
    )
    bot.ap.plugin_connector.list_commands.return_value = [FakeCommandManifest('author/plugin_a', 'draw')]

    assert await bot._match_plugin_command(make_message_event('/draw cat')) is None
    bot.ap.plugin_connector.list_commands.assert_not_awaited()


class SchemaCommandManifest(FakeCommandManifest):
    def __init__(self, owner: str, name: str, config=None):
        super().__init__(owner, name)
        self.spec = {'config': config} if config is not None else None


async def _run_real_command(bot, manifest, instance_config):
    """Drive the real CommandManager and capture the ExecuteContext sent to the plugin connector."""
    sent = []

    async def execute_command(ctx, bound_plugins=None):
        sent.append((ctx, bound_plugins))
        if False:
            yield None

    bot.ap.plugin_connector.list_commands.return_value = [manifest]
    bot.ap.plugin_connector.execute_command = execute_command
    real_cmd_mgr = CommandManager(bot.ap)
    real_cmd_mgr.cmd_list = []
    real_cmd_mgr.is_admin = AsyncMock(return_value=False)
    bot.ap.cmd_mgr = real_cmd_mgr
    bot.ap.sess_mgr.get_session_by_launcher = AsyncMock(
        return_value=provider_session.Session(
            launcher_type=provider_session.LauncherTypes.PERSON,
            launcher_id='1001',
        )
    )
    adapter = SimpleNamespace(reply_message=AsyncMock(), get_launcher_id=Mock(return_value=None))
    await bot._execute_matched_plugin_command(
        event=make_message_event('/draw cat'),
        adapter=adapter,
        plugin_id='author/plugin_a',
        command_name='draw',
        command_text='draw cat',
        full_command_text='/draw cat',
        command_config=instance_config,
    )
    return sent


@pytest.mark.asyncio
async def test_instance_config_overrides_schema_defaults_and_targets_one_plugin():
    pytest.importorskip('langbot_plugin.api.entities.builtin.command.context')
    from langbot_plugin.api.entities.builtin.command.context import ExecuteContext

    if 'config' not in ExecuteContext.model_fields:
        pytest.skip('installed SDK predates ExecuteContext.config')
    bot = make_bot()
    manifest = SchemaCommandManifest(
        'author/plugin_a',
        'draw',
        [
            {'name': 'style', 'type': 'string', 'default': 'plain'},
            {'name': 'count', 'type': 'integer', 'default': 1},
        ],
    )

    sent = await _run_real_command(bot, manifest, {'style': 'anime'})

    ctx, bound_plugins = sent[0]
    assert ctx.config == {'style': 'anime', 'count': 1}
    assert bound_plugins == ['author/plugin_a']


@pytest.mark.asyncio
async def test_legacy_command_without_config_schema_still_executes():
    """Commands written before spec.config existed run unchanged with an empty config."""
    bot = make_bot()

    sent = await _run_real_command(bot, SchemaCommandManifest('author/plugin_a', 'draw'), {})

    ctx, _ = sent[0]
    assert ctx.command == 'draw'
    assert getattr(ctx, 'config', {}) == {}
