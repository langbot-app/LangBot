import asyncio
import importlib
import sys
import types
from functools import cache
from unittest.mock import patch

import langbot_plugin.api.entities.builtin.platform.message as platform_message

from langbot.pkg.platform.sources.wechatpad_message_guard import (
    WeChatPadMessageDeduplicator,
    is_wechatpad_message,
)


class _Logger:
    def info(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


@cache
def _load_message_converter():
    module_name = 'langbot.pkg.platform.sources.wechatpad'
    if module_name not in sys.modules:
        logger_module = types.ModuleType('langbot.pkg.platform.logger')
        logger_module.EventLogger = object
        with patch.dict(sys.modules, {'langbot.pkg.platform.logger': logger_module}):
            module = importlib.import_module(module_name)
        return module.WeChatPadMessageConverter

    return sys.modules[module_name].WeChatPadMessageConverter


def test_same_new_msg_id_is_seen_only_once():
    deduplicator = WeChatPadMessageDeduplicator()
    event = {'new_msg_id': 123, 'from_user_name': {'str': 'wxid_sender'}}

    assert deduplicator.is_duplicate(event) is False
    assert deduplicator.is_duplicate(event) is True


def test_same_content_with_different_message_ids_is_not_deduplicated():
    deduplicator = WeChatPadMessageDeduplicator()

    first = {'new_msg_id': 123, 'content': {'str': '相同内容'}}
    second = {'new_msg_id': 456, 'content': {'str': '相同内容'}}

    assert deduplicator.is_duplicate(first) is False
    assert deduplicator.is_duplicate(second) is False


def test_non_message_event_is_ignored():
    assert is_wechatpad_message({'Type': 10000, 'loginState': 1}) is False
    assert is_wechatpad_message({'from_user_name': {'str': 'wxid_sender'}}) is True


def test_group_member_at_from_wrapped_message_source_uses_wxid():
    converter = _load_message_converter()(
        {
            'wechatpad_url': 'http://wechatpad.invalid',
            'token': 'test-token',
            'wxid': 'wxid_bot',
        },
        _Logger(),
    )
    message = {
        'content': {'str': 'wxid_sender:\n@成员 积分 100'},
        'from_user_name': {'str': 'test@chatroom'},
        'to_user_name': {'str': 'wxid_bot'},
        'msg_source': {'str': '<msgsource><atuserlist>wxid_member</atuserlist></msgsource>'},
        'msg_type': 1,
    }

    message_chain = asyncio.run(converter.target2yiri(message, 'bot_nickname'))

    assert [component.target for component in message_chain if isinstance(component, platform_message.At)] == [
        'wxid_member'
    ]


def test_group_member_at_from_xml_message_source_uses_wxid():
    converter = _load_message_converter()(
        {
            'wechatpad_url': 'http://wechatpad.invalid',
            'token': 'test-token',
            'wxid': 'wxid_bot',
        },
        _Logger(),
    )
    message = {
        'content': {'str': 'wxid_sender:\n@成员 积分 100'},
        'from_user_name': {'str': 'test@chatroom'},
        'to_user_name': {'str': 'wxid_bot'},
        'msg_source': '<msgsource><atuserlist>wxid_member</atuserlist></msgsource>',
        'msg_type': 1,
    }

    message_chain = asyncio.run(converter.target2yiri(message, 'bot_nickname'))

    assert [component.target for component in message_chain if isinstance(component, platform_message.At)] == [
        'wxid_member'
    ]
