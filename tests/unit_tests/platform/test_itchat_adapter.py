"""Tests for itchat adapter group/private message conversion."""

from __future__ import annotations

from types import SimpleNamespace

import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.platform import botmgr as _botmgr  # noqa: F401

from langbot.pkg.platform.sources.itchat import ItchatAdapter, ItchatEventConverter


def _make_adapter(bot_account_id: str = '@bot_wxid', bot_nickname: str = 'MyBot'):
    adapter = SimpleNamespace(
        bot_account_id=bot_account_id,
        _bot_nickname=bot_nickname,
        _core=SimpleNamespace(storageClass=SimpleNamespace(userName=bot_account_id)),
        _get_obj_value=ItchatAdapter._get_obj_value,
    )
    return adapter


def _make_converter(adapter) -> ItchatEventConverter:
    return ItchatEventConverter(adapter_ref=lambda: adapter)


def test_group_text_becomes_group_message():
    converter = _make_converter(_make_adapter())

    msg = {
        'FromUserName': '@@group_wxid',
        'Type': 'Text',
        'Text': 'hello',
        'ActualUserName': '@member_wxid',
        'ActualNickName': 'MemberNick',
        'IsAt': False,
        'CreateTime': 123456,
        'User': SimpleNamespace(NickName='Group Name'),
    }

    event = converter.target2yiri(msg)

    assert isinstance(event, platform_events.GroupMessage)
    assert isinstance(event.sender, platform_entities.GroupMember)
    assert event.sender.id == '@member_wxid'
    assert event.sender.member_name == 'MemberNick'
    assert event.sender.group.id == '@@group_wxid'
    assert event.sender.group.name == 'Group Name'

    components = list(event.message_chain)
    assert len(components) == 1
    assert isinstance(components[0], platform_message.Plain)
    assert components[0].text == 'hello'


def test_private_text_becomes_friend_message():
    converter = _make_converter(_make_adapter())

    msg = {
        'FromUserName': '@friend_wxid',
        'Type': 'Text',
        'Text': 'hi',
        'CreateTime': 123456,
        'User': SimpleNamespace(NickName='FriendNick', RemarkName='FriendRemark'),
    }

    event = converter.target2yiri(msg)

    assert isinstance(event, platform_events.FriendMessage)
    assert isinstance(event.sender, platform_entities.Friend)
    assert event.sender.id == '@friend_wxid'
    assert event.sender.nickname == 'FriendNick'
    assert event.sender.remark == 'FriendRemark'


def test_bot_own_message_is_ignored():
    converter = _make_converter(_make_adapter(bot_account_id='@bot_wxid'))

    msg = {
        'FromUserName': '@bot_wxid',
        'Type': 'Text',
        'Text': 'self echo',
    }

    assert converter.target2yiri(msg) is None


def test_group_at_bot_strips_prefix_and_adds_at():
    converter = _make_converter(_make_adapter(bot_account_id='@bot_wxid', bot_nickname='MyBot'))

    msg = {
        'FromUserName': '@@group_wxid',
        'Type': 'Text',
        'Text': '@MyBot hello world',
        'ActualUserName': '@member_wxid',
        'ActualNickName': 'MemberNick',
        'IsAt': True,
        'CreateTime': 123456,
        'User': SimpleNamespace(NickName='Group Name'),
    }

    event = converter.target2yiri(msg)

    assert isinstance(event, platform_events.GroupMessage)
    components = list(event.message_chain)
    assert len(components) == 2
    assert isinstance(components[0], platform_message.At)
    assert components[0].target == '@bot_wxid'
    assert isinstance(components[1], platform_message.Plain)
    assert components[1].text == 'hello world'


def test_group_message_without_sender_is_ignored():
    converter = _make_converter(_make_adapter())

    msg = {
        'FromUserName': '@@group_wxid',
        'Type': 'Text',
        'Text': 'system note',
        'ActualUserName': '',
        'ActualNickName': '',
        'IsAt': False,
        'CreateTime': 123456,
        'User': SimpleNamespace(NickName='Group Name'),
    }

    assert converter.target2yiri(msg) is None
