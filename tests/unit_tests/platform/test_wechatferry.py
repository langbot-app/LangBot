import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.platform.sources.wechatferry import (
    WeChatFerryAdapter,
    WeChatFerryEventConverter,
    WeChatFerryMessageConverter,
    WeChatFerryMessageDeduplicator,
)


class DummyLogger(abstract_platform_logger.AbstractEventLogger):
    async def info(self, msg: str):
        pass

    async def debug(self, msg: str):
        pass

    async def warning(self, msg: str):
        pass

    async def error(self, msg: str):
        pass


def test_deduplicator():
    dedup = WeChatFerryMessageDeduplicator(max_size=10)
    assert dedup.is_duplicate(1001) is False
    assert dedup.is_duplicate(1001) is True
    assert dedup.is_duplicate(1002) is False
    assert dedup.is_duplicate(1002) is True


@pytest.mark.asyncio
async def test_message_converter_yiri2target():
    chain = platform_message.MessageChain(
        [
            platform_message.At(target='wxid_target1'),
            platform_message.Plain(text=' 问道签到'),
            platform_message.Image(url='http://example.com/test.png'),
        ]
    )
    payload = await WeChatFerryMessageConverter.yiri2target(chain)
    assert payload['text'] == ' 问道签到'
    assert payload['ats'] == ['wxid_target1']
    assert len(payload['images']) == 1
    assert payload['images'][0]['url'] == 'http://example.com/test.png'


@pytest.mark.asyncio
async def test_message_converter_target2yiri():
    data = {
        'id': 12345,
        'type': 1,
        'content': '问道签到',
        'is_at': True,
    }
    chain = await WeChatFerryMessageConverter.target2yiri(data, bot_account_id='wxid_bot')
    assert len(chain) == 2
    assert isinstance(chain[0], platform_message.At)
    assert chain[0].target == 'wxid_bot'
    assert isinstance(chain[1], platform_message.Plain)
    assert chain[1].text == '问道签到'


@pytest.mark.asyncio
async def test_message_converter_image_base64_and_windows_path_guard():
    # 1. Helper V4/V7 inline <img_b64> XML payload -> Image(base64=...) and sanitize data['content']
    inline_data = {
        'id': 20001,
        'type': 3,
        'content': '<msg><img_b64>/9j/4AAQSkZJRgABAQAAAQABAAD/</img_b64></msg>',
        'extra': r'C:\wcf_service\temp\img_01.jpg',
    }
    chain = await WeChatFerryMessageConverter.target2yiri(inline_data, bot_account_id='wxid_bot')
    assert len(chain) == 1
    assert isinstance(chain[0], platform_message.Image)
    assert chain[0].base64 == 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/'
    assert inline_data['content'] == '[图片]'

    # 2. Windows host path without base64 must NOT pass C:\... path into Linux container
    win_path_only = {
        'id': 20002,
        'type': 3,
        'content': '',
        'extra': r'C:\Users\Admin\WeChat Files\pic.jpg',
    }
    chain_win = await WeChatFerryMessageConverter.target2yiri(win_path_only, bot_account_id='wxid_bot')
    assert len(chain_win) == 1
    assert isinstance(chain_win[0], platform_message.Plain)
    assert chain_win[0].text == '[图片]'

    # 3. Local POSIX path without drive colon remains supported
    posix_path_data = {
        'id': 20003,
        'type': 3,
        'content': '',
        'extra': '/tmp/wcf_img.png',
    }
    chain_posix = await WeChatFerryMessageConverter.target2yiri(posix_path_data, bot_account_id='wxid_bot')
    assert len(chain_posix) == 1
    assert isinstance(chain_posix[0], platform_message.Image)
    assert chain_posix[0].path == '/tmp/wcf_img.png'


@pytest.mark.asyncio
async def test_event_converter_group_message():
    config = {'bot_wxid': 'wxid_bot'}
    logger = AsyncMock()
    converter = WeChatFerryEventConverter(config, logger)

    group_data = {
        'id': 10001,
        'type': 1,
        'is_group': True,
        'roomid': '249827391@chatroom',
        'room_name': '测试鱼塘群',
        'sender': 'wxid_member_abc',
        'sender_name': '路人甲',
        'content': '问道签到',
        'is_at': True,
        'ts': 1727800000,
    }

    event = await converter.target2yiri(group_data, bot_account_id='wxid_bot')
    assert isinstance(event, platform_events.GroupMessage)
    assert event.sender.id == 'wxid_member_abc'
    assert event.sender.member_name == '路人甲'
    assert event.sender.group.id == '249827391@chatroom'
    assert event.sender.group.name == '测试鱼塘群'
    assert event.time == 1727800000


@pytest.mark.asyncio
async def test_event_converter_friend_message():
    config = {'bot_wxid': 'wxid_bot'}
    logger = AsyncMock()
    converter = WeChatFerryEventConverter(config, logger)

    private_data = {
        'id': 10002,
        'type': 1,
        'is_group': False,
        'roomid': '',
        'sender': 'wxid_private_user',
        'sender_name': '老朋友',
        'content': '问道帮助',
        'ts': 1727800001,
    }

    event = await converter.target2yiri(private_data, bot_account_id='wxid_bot')
    assert isinstance(event, platform_events.FriendMessage)
    assert event.sender.id == 'wxid_private_user'
    assert event.sender.nickname == '老朋友'
    assert event.time == 1727800001


@pytest.mark.asyncio
async def test_event_converter_filters_self_and_official():
    config = {'bot_wxid': 'wxid_bot'}
    logger = AsyncMock()
    converter = WeChatFerryEventConverter(config, logger)

    # 1. 过滤机器人自身
    self_msg = {'id': 1, 'sender': 'wxid_bot', 'content': 'hello'}
    assert await converter.target2yiri(self_msg, 'wxid_bot') is None

    # 2. 过滤微信官方公众号
    gh_msg = {'id': 2, 'sender': 'gh_123456', 'content': '推送'}
    assert await converter.target2yiri(gh_msg, 'wxid_bot') is None

    # 3. 过滤微信系统账号
    sys_msg = {'id': 3, 'sender': 'weixin', 'content': '安全提醒'}
    assert await converter.target2yiri(sys_msg, 'wxid_bot') is None


@pytest.mark.asyncio
async def test_ws_loop_large_max_size_and_concurrent_dispatch():
    config = {
        'api_url': 'http://127.0.0.1:18080',
        'ws_url': 'ws://127.0.0.1:18080/ws',
        'bot_wxid': 'wxid_bot',
        'ws_max_size_mb': 64,
    }
    logger = DummyLogger()
    adapter = WeChatFerryAdapter(config, logger)
    adapter._running = True

    received_events = []

    async def fake_listener(ev, adp):
        received_events.append(ev)
        adapter._running = False

    adapter.register_listener(platform_events.FriendMessage, fake_listener)

    class FakeWS:
        def __init__(self, frames):
            self._frames = list(frames)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._frames:
                adapter._running = False
                raise StopAsyncIteration
            return self._frames.pop(0)

    sample_frame = json.dumps(
        {
            'id': 30001,
            'type': 1,
            'is_group': False,
            'sender': 'wxid_alice',
            'sender_name': 'Alice',
            'content': '你好大肥鱼',
            'ts': 1727800099,
        }
    )

    captured_kwargs = {}

    def fake_connect(url, **kwargs):
        captured_kwargs['url'] = url
        captured_kwargs.update(kwargs)
        return FakeWS([sample_frame])

    with patch('langbot.pkg.platform.sources.wechatferry.websockets.connect', side_effect=fake_connect):
        await adapter._ws_loop('ws://127.0.0.1:18080/ws')
        if adapter._inbound_tasks:
            await asyncio.gather(*list(adapter._inbound_tasks))

    assert captured_kwargs['max_size'] == 64 * 1024 * 1024
    assert len(received_events) == 1
    assert received_events[0].sender.nickname == 'Alice'


@pytest.mark.asyncio
async def test_adapter_reply_routing():
    config = {
        'api_url': 'http://127.0.0.1:18080',
        'ws_url': 'ws://127.0.0.1:18080/ws',
        'bot_wxid': 'wxid_bot',
    }
    logger = DummyLogger()
    adapter = WeChatFerryAdapter(config, logger)

    # 模拟群回复
    group_member = platform_entities.GroupMember(
        id='wxid_user',
        member_name='User',
        permission=platform_entities.Permission.Member,
        group=platform_entities.Group(
            id='group123@chatroom',
            name='Group',
            permission=platform_entities.Permission.Member,
        ),
        special_title='',
    )
    group_msg_event = platform_events.GroupMessage(
        sender=group_member,
        message_chain=platform_message.MessageChain([platform_message.Plain(text='test')]),
        time=1727800000,
        source_platform_object={},
    )

    reply_chain = platform_message.MessageChain([platform_message.Plain(text='签到成功！')])
    with patch.object(WeChatFerryAdapter, 'send_message', new_callable=AsyncMock) as mock_send:
        await adapter.reply_message(group_msg_event, reply_chain)
        mock_send.assert_awaited_once_with('group', 'group123@chatroom', reply_chain)
