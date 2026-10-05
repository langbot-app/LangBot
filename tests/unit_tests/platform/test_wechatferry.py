import pytest
from unittest.mock import AsyncMock, patch

from langbot.pkg.platform.sources.wechatferry import (
    WeChatFerryAdapter,
    WeChatFerryEventConverter,
    WeChatFerryMessageConverter,
    WeChatFerryMessageDeduplicator,
)
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities


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
async def test_event_converter_group_message():
    config = {'bot_wxid': 'wxid_bot'}
    logger = AsyncMock()
    converter = WeChatFerryEventConverter(config, logger)

    group_data = {
        'id': 10001,
        'type': 1,
        'is_group': True,
        'roomid': '249827391@chatroom',
        'sender': 'wxid_member_abc',
        'content': '问道签到',
        'is_at': True,
        'ts': 1727800000,
    }

    event = await converter.target2yiri(group_data, bot_account_id='wxid_bot')
    assert isinstance(event, platform_events.GroupMessage)
    # 核心检验：真实 wxid
    assert event.sender.id == 'wxid_member_abc'
    assert event.sender.group.id == '249827391@chatroom'
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
        'content': '问道帮助',
        'ts': 1727800001,
    }

    event = await converter.target2yiri(private_data, bot_account_id='wxid_bot')
    assert isinstance(event, platform_events.FriendMessage)
    assert event.sender.id == 'wxid_private_user'
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
            id='group123@chatroom', name='Group', permission=platform_entities.Permission.Member
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
