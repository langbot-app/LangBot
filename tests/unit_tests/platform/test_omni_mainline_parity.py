"""Regression coverage for master fixes carried into the Omni adapter path."""

import asyncio
import base64
import importlib
import json
import time
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiocqhttp
import pytest
import yaml

from langbot.pkg.platform.adapters.aiocqhttp.event_converter import AiocqhttpEventConverter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot.pkg.platform.adapters.discord.adapter import DiscordAdapter
from langbot.pkg.platform.adapters.discord.message_converter import DiscordMessageConverter
from langbot.pkg.platform.adapters.lark.adapter import LarkAdapter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.adapters.qqofficial.adapter import QQOfficialAdapter
from langbot.pkg.platform.adapters.wecombot.adapter import WecomBotAdapter
from langbot.pkg.platform.sources.aiocqhttp import AiocqhttpEventConverter as LegacyOneBotConverter
from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot_plugin.api.definition.abstract.platform.event_logger import AbstractEventLogger
from langbot_plugin.api.entities.builtin.platform import message as pm

PLATFORM = Path(__file__).parents[3] / 'src/langbot/pkg/platform'
OMNI_NAMES = sorted(p.parent.name for p in (PLATFORM / 'adapters').glob('*/manifest.yaml'))


def chain(text):
    return pm.MessageChain([pm.Plain(text=text)])


@pytest.mark.parametrize('name', OMNI_NAMES)
def test_omni_config_contains_mainline_options_and_help(name):
    legacy = yaml.safe_load((PLATFORM / 'sources' / f'{name}.yaml').read_text())['spec']
    omni = yaml.safe_load((PLATFORM / 'adapters' / name / 'manifest.yaml').read_text())['spec']
    assert {c['name'] for c in legacy['config']} <= {c['name'] for c in omni['config']}
    assert omni['help_links'] == legacy['help_links']


@pytest.mark.asyncio
@pytest.mark.parametrize('prefix', ['', 'base64://', 'data:image/png;base64,'])
@pytest.mark.parametrize('kind', [pm.Image, pm.Voice, pm.File])
async def test_onebot_media_base64_is_normalized_once(prefix, kind):
    component = kind(base64=prefix + 'YWJj')
    output, _, _ = await AiocqhttpMessageConverter.yiri2target(pm.MessageChain([component]))
    assert output[0].data['file'] == 'base64://YWJj'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'raw,expected',
    [
        (
            {
                'app': 'com.tencent.structmsg',
                'meta': {'detail_1': {'desc': 'Article', 'qqdocurl': 'https://example.test/a'}},
            },
            'Article',
        ),
        ({'app': 'music', 'meta': {'music': {'title': 'Song', 'jumpUrl': 'https://example.test/song'}}}, 'Song'),
        ('{invalid', '[收到一张JSON卡片]'),
    ],
)
async def test_onebot_json_cards_are_readable(raw, expected):
    payload = json.dumps(raw) if isinstance(raw, dict) else raw
    result = await AiocqhttpMessageConverter.target2yiri([{'type': 'json', 'data': {'data': payload}}])
    assert expected in result[1].text


@pytest.mark.asyncio
async def test_onebot_metadata_lookup_is_cached_and_survives_legacy_conversion():
    bot = SimpleNamespace(
        get_group_info=AsyncMock(return_value={'group_name': 'Team'}),
        get_group_member_info=AsyncMock(return_value={'title': 'Maintainer'}),
    )
    event = aiocqhttp.Event(
        {
            'post_type': 'message',
            'message_type': 'group',
            'message_id': 1,
            'time': 1,
            'group_id': 2,
            'user_id': 3,
            'message': 'hello',
            'sender': {'user_id': 3, 'nickname': 'Alice', 'role': 'admin'},
        }
    )
    lookup = LegacyOneBotConverter()
    first = await AiocqhttpEventConverter.target2yiri(event, bot, lookup=lookup)
    second = await AiocqhttpEventConverter.target2legacy(event, bot, lookup=lookup)
    assert first.group.name == second.group.name == 'Team'
    assert first.sender_member.title == second.sender.special_title == 'Maintainer'
    bot.get_group_info.assert_awaited_once()
    bot.get_group_member_info.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', [pm.Image, pm.Voice, pm.File])
async def test_discord_outbound_base64_obeys_mainline_limit(monkeypatch, kind):
    legacy = importlib.import_module('langbot.pkg.platform.sources.discord')
    monkeypatch.setattr(legacy, '_MAX_DISCORD_MEDIA_BYTES', 4)
    with pytest.raises(ValueError, match='exceeds'):
        await DiscordMessageConverter.yiri2target(pm.MessageChain([kind(base64=base64.b64encode(b'12345').decode())]))


@pytest.mark.asyncio
async def test_lark_component_loading_obeys_mainline_limit(monkeypatch, tmp_path):
    legacy = importlib.import_module('langbot.pkg.platform.sources.lark')
    monkeypatch.setattr(legacy, '_MAX_LARK_MEDIA_BYTES', 4)
    file = tmp_path / 'oversized.txt'
    file.write_bytes(b'12345')
    assert await LarkMessageConverter._get_component_bytes(pm.File(path=str(file))) is None
    assert await LarkMessageConverter._get_component_bytes(pm.File(url=file.as_uri())) is None
    assert await LarkMessageConverter._get_component_bytes(pm.File(base64=base64.b64encode(b'12345').decode())) is None


@pytest.mark.asyncio
async def test_lark_callbacks_are_bounded_and_cancelled_on_shutdown():
    bot = SimpleNamespace(_auto_reconnect=True, _disconnect=AsyncMock())
    adapter = LarkAdapter.model_construct(config={}, bot=bot)
    completed = []

    async def work():
        try:
            await asyncio.Event().wait()
        finally:
            completed.append(True)

    for _ in range(105):
        adapter._submit_coro(work())
    assert len(adapter.inbound_event_tasks) == 100
    await asyncio.sleep(0)
    await adapter.kill()
    assert len(completed) == 100
    assert not adapter.inbound_event_tasks
    bot._disconnect.assert_awaited_once()


def test_lark_domains_and_markdown_table_rendering():
    adapter = LarkAdapter.model_construct(config={})
    for domain in ['https://open.larksuite.com', 'https://open.feishu.cn']:
        assert adapter.build_api_client({'app_id': 'a', 'app_secret': 'b', 'domain': domain})._config.domain == domain
    table = '| Name |\n| --- |\n| Alice |'
    payloads = adapter._outbound_payloads([[{'tag': 'md', 'text': table}]], [])
    assert payloads[0][0] == 'interactive'
    assert payloads[0][1]['body']['elements'] == [{'tag': 'markdown', 'content': table}]


@pytest.mark.asyncio
async def test_qq_optional_token(monkeypatch):
    module = importlib.import_module('langbot.pkg.platform.adapters.qqofficial.adapter')
    client = MagicMock()
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(module, 'QQOfficialClient', factory)
    QQOfficialAdapter(config={'appid': 'app', 'secret': 'secret'}, logger=MagicMock(spec=AbstractEventLogger))
    assert factory.call_args.kwargs['token'] == ''


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['c2c', 'group'])
@pytest.mark.parametrize('markdown', [False, True])
async def test_qq_markdown_configuration_reaches_send_api(target, markdown):
    bot = SimpleNamespace(
        **{
            name: AsyncMock()
            for name in [
                'send_private_text_msg',
                'send_private_markdown_msg',
                'send_group_text_msg',
                'send_group_markdown_msg',
            ]
        }
    )
    adapter = QQOfficialAdapter.model_construct(config={'enable-markdown-rendering': markdown}, bot=bot)
    await adapter._send_content_list(target, 'target', [{'type': 'text', 'content': '**hello**'}], msg_id='anchor')
    name = f'send_{"private" if target == "c2c" else "group"}_{"markdown" if markdown else "text"}_msg'
    assert getattr(bot, name).await_args.kwargs['content'] == '**hello**'
    assert getattr(bot, name).await_args.kwargs['msg_id'] == 'anchor'
    assert sum(m.await_count for m in vars(bot).values()) == 1


@pytest.mark.asyncio
async def test_qq_stream_sends_snapshots_and_cleans_final_state():
    bot = SimpleNamespace(send_stream_msg=AsyncMock(return_value={'id': 'stream'}))
    adapter = QQOfficialAdapter.model_construct(config={}, bot=bot)
    adapter._stream_ctx['response'] = {
        'user_openid': 'user',
        'msg_id': 'anchor',
        'stream_msg_id': None,
        'msg_seq': 1,
        'index': 0,
        'last_update_ts': 0,
        'accumulated_text': '',
        'sent_length': 0,
        'session_started': False,
    }
    adapter._stream_ctx_ts['response'] = time.time()
    for text, final in [('Hello', False), ('Hello world', True)]:
        await adapter.reply_message_chunk(None, {'resp_message_id': 'response'}, chain(text), is_final=final)
    assert [c.kwargs['content'] for c in bot.send_stream_msg.await_args_list] == ['Hello', 'Hello world']
    assert bot.send_stream_msg.await_args.kwargs['input_state'] == 10
    assert not adapter._stream_ctx and not adapter._stream_ctx_ts


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['image', 'voice', 'file'])
@pytest.mark.parametrize('stream', [False, True])
async def test_wecombot_reply_uploads_media_instead_of_placeholder(kind, stream):
    bot = SimpleNamespace(
        reply_text=AsyncMock(),
        push_stream_chunk=AsyncMock(return_value=True),
        upload_media=AsyncMock(return_value={'media_id': 'media'}),
        reply_image=AsyncMock(),
        reply_voice=AsyncMock(),
        reply_file=AsyncMock(),
    )
    adapter = WecomBotAdapter.model_construct(config={}, bot=bot)
    event = WecomBotEvent({'message_id': 'message', 'req_id': 'request'})
    source = SimpleNamespace(source_platform_object=event)
    part = {'image': pm.Image, 'voice': pm.Voice, 'file': pm.File}[kind](base64=base64.b64encode(b'payload').decode())
    message = pm.MessageChain([pm.Plain(text='hello'), part])
    if stream:
        await adapter.reply_message_chunk(source, {}, message, is_final=False)
        bot.upload_media.assert_not_awaited()
        await adapter.reply_message_chunk(source, {}, message, is_final=True)
    else:
        await adapter.reply_message(source, message)
    assert bot.upload_media.await_args.args[0] == b'payload'
    assert bot.upload_media.await_args.kwargs['media_type'] == kind
    getattr(bot, f'reply_{kind}').assert_awaited_once_with('request', 'media')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'name,cls', [('wecom', 'WecomAdapter'), ('wecomcs', 'WecomCSAdapter'), ('qqofficial', 'QQOfficialAdapter')]
)
async def test_shutdown_closes_client(name, cls):
    module = importlib.import_module(f'langbot.pkg.platform.adapters.{name}.adapter')
    bot = SimpleNamespace(close=AsyncMock(), clear=MagicMock())
    adapter = getattr(module, cls).model_construct(bot=bot, config={})
    await adapter.kill()
    bot.close.assert_awaited_once()


def test_kook_compressed_gateway_limit(monkeypatch):
    source = importlib.import_module('langbot.pkg.platform.sources.kook')
    omni = importlib.import_module('langbot.pkg.platform.adapters.kook.adapter')
    monkeypatch.setattr(source, '_KOOK_MAX_GATEWAY_MESSAGE_BYTES', 32)
    assert json.loads(omni.KookAdapter._decode_ws_message(zlib.compress(b'{"s": 1}'))) == {'s': 1}
    with pytest.raises(ValueError, match='size limit'):
        omni.KookAdapter._decode_ws_message(zlib.compress(b' ' * 1000))


@pytest.mark.asyncio
async def test_discord_stream_edits_one_message_with_complete_text():
    sent = SimpleNamespace(content='first', edit=AsyncMock())
    channel = SimpleNamespace(send=AsyncMock(return_value=sent))
    adapter = DiscordAdapter.model_construct(config={}, bot=None)
    adapter._stream_buffer['response'] = {
        'channel': channel,
        'sent_message': None,
        'last_content': '',
        'chunk_count': 0,
    }
    await adapter.reply_message_chunk(None, {'resp_message_id': 'response'}, chain('first'))
    await adapter.reply_message_chunk(None, {'resp_message_id': 'response'}, chain('first second'), is_final=True)
    channel.send.assert_awaited_once_with('first')
    sent.edit.assert_awaited_once_with(content='first second')
    assert not adapter._stream_buffer


@pytest.mark.parametrize('name', ['domain', 'custom_domain'])
def test_lark_legacy_and_omni_have_identical_region_fields(name):
    legacy = yaml.safe_load((PLATFORM / 'sources/lark.yaml').read_text())['spec']['config']
    omni = yaml.safe_load((PLATFORM / 'adapters/lark/manifest.yaml').read_text())['spec']['config']
    assert next(c for c in legacy if c['name'] == name) == next(c for c in omni if c['name'] == name)


@pytest.mark.asyncio
@pytest.mark.parametrize('variant', ['sources.lark', 'adapters.lark.adapter'])
@pytest.mark.parametrize(
    'region,expected',
    [
        ({}, 'https://open.feishu.cn'),
        ({'domain': 'https://open.feishu.cn'}, 'https://open.feishu.cn'),
        ({'domain': 'https://open.larksuite.com'}, 'https://open.larksuite.com'),
        ({'domain': 'custom', 'custom_domain': 'https://open.example.test/'}, 'https://open.example.test'),
    ],
)
async def test_lark_http_and_websocket_use_selected_region(monkeypatch, variant, region, expected):
    import lark_oapi

    module = importlib.import_module(f'langbot.pkg.platform.{variant}')
    ws = MagicMock(spec=lark_oapi.ws.Client)
    factory = MagicMock(return_value=ws)
    monkeypatch.setattr(module, 'NonBlockingLarkWSClient', factory)
    adapter = module.LarkAdapter(
        config={'app_id': 'app', 'app_secret': 'secret', 'bot_name': 'bot', **region},
        logger=MagicMock(spec=AbstractEventLogger),
    )
    assert factory.call_args.kwargs['domain'] == expected
    assert adapter.api_client._config.domain == expected


@pytest.mark.asyncio
async def test_lark_resource_download_rejects_oversized_platform_response(monkeypatch):
    import io

    legacy = importlib.import_module('langbot.pkg.platform.sources.lark')
    monkeypatch.setattr(legacy, '_MAX_LARK_MEDIA_BYTES', 4)
    response = SimpleNamespace(success=lambda: True, raw=SimpleNamespace(headers={}), file=io.BytesIO(b'12345'))
    client = SimpleNamespace(
        im=SimpleNamespace(v1=SimpleNamespace(message_resource=SimpleNamespace(aget=AsyncMock(return_value=response))))
    )
    with pytest.raises(ValueError, match='exceeds'):
        await LarkMessageConverter._download_resource(client, 'message', 'key', 'image')


@pytest.mark.asyncio
async def test_qq_non_stream_fallback_replaces_snapshot(monkeypatch):
    reply = AsyncMock()
    monkeypatch.setattr(QQOfficialAdapter, 'reply_message', reply)
    adapter = QQOfficialAdapter.model_construct(config={}, bot=None)
    for text, final in [('A', False), ('AB', False), ('ABC', True)]:
        await adapter.reply_message_chunk(None, {'resp_message_id': 'fallback'}, chain(text), is_final=final)
    reply.assert_awaited_once()
    assert reply.await_args.args[1][0].text == 'ABC'
    assert not adapter._fallback_text and not adapter._fallback_text_ts


@pytest.mark.asyncio
async def test_telegram_stream_reuses_persistent_message():
    import telegram
    from langbot.pkg.platform.adapters.telegram.adapter import TelegramAdapter

    update = MagicMock(spec=telegram.Update)
    update.effective_chat = SimpleNamespace(id=123, type='private')
    update.effective_message = SimpleNamespace(message_thread_id=None)
    bot = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=456)), edit_message_text=AsyncMock()
    )
    adapter = TelegramAdapter.model_construct(config={}, bot=bot, msg_stream_id={}, seq=1)
    source = SimpleNamespace(source_platform_object=update)
    await adapter.create_message_card('response', source)
    await adapter.reply_message_chunk(
        source, SimpleNamespace(resp_message_id='response', msg_sequence=1, tool_calls=None), chain('Hello')
    )
    await adapter.reply_message_chunk(
        source,
        SimpleNamespace(resp_message_id='response', msg_sequence=2, tool_calls=None),
        chain('Hello world'),
        is_final=True,
    )
    bot.send_message.assert_awaited_once()
    assert [call.kwargs['message_id'] for call in bot.edit_message_text.await_args_list] == [456, 456]
    assert bot.edit_message_text.await_args.kwargs['text'] == 'Hello world'
    assert not adapter.msg_stream_id


@pytest.mark.asyncio
async def test_telegram_inbound_image_does_not_expose_token_url(monkeypatch):
    import datetime
    from langbot.pkg.platform.sources import telegram as source
    from langbot.pkg.platform.adapters.telegram.message_converter import TelegramMessageConverter

    download = MagicMock()
    download.__aenter__ = AsyncMock(return_value=SimpleNamespace())
    download.__aexit__ = AsyncMock()
    monkeypatch.setattr(source.httpclient, 'get_session', lambda **kwargs: SimpleNamespace(get=lambda url: download))
    monkeypatch.setattr(source.httpclient, 'read_limited', AsyncMock(return_value=b'image'))
    message = SimpleNamespace(
        message_id=1,
        date=datetime.datetime.now(),
        text='',
        caption='',
        photo=[
            SimpleNamespace(
                get_file=AsyncMock(
                    return_value=SimpleNamespace(file_path='https://api.telegram.org/file/botSECRET/photo')
                )
            )
        ],
        voice=None,
        document=None,
    )
    bot = SimpleNamespace(
        get_file=AsyncMock(return_value=SimpleNamespace(file_path='https://api.telegram.org/file/botSECRET/photo'))
    )
    converted = await TelegramMessageConverter.target2yiri(message, bot, 'bot')
    image = next(p for p in converted if isinstance(p, pm.Image))
    assert image.base64 and not image.url
    assert 'SECRET' not in image.model_dump_json()
