# -*- coding: utf-8 -*-
"""
此模块提供事件模型。
"""
from datetime import datetime
from enum import Enum
import typing

import pydantic.v1 as pydantic

from . import entities as platform_entities
from . import message as platform_message


class Event(pydantic.BaseModel):
    """事件基类。

    Args:
        type: 事件名。
    """
    type: str
    """事件名。"""
    def __repr__(self):
        return self.__class__.__name__ + '(' + ', '.join(
            (
                f'{k}={repr(v)}'
                for k, v in self.__dict__.items() if k != 'type' and v
            )
        ) + ')'

    @classmethod
    def parse_subtype(cls, obj: dict) -> 'Event':
        try:
            return typing.cast(Event, super().parse_subtype(obj))
        except ValueError:
            return Event(type=obj['type'])

    @classmethod
    def get_subtype(cls, name: str) -> typing.Type['Event']:
        try:
            return typing.cast(typing.Type[Event], super().get_subtype(name))
        except ValueError:
            return Event


###############################
# Message Event
class MessageEvent(Event):
    """消息事件。

    Args:
        type: 事件名。
        message_chain: 消息内容。
    """
    type: str
    """事件名。"""
    message_chain: platform_message.MessageChain
    """消息内容。"""

    time: float | None = None
    """消息发送时间戳。"""

    source_platform_object: typing.Optional[typing.Any] = None
    """原消息平台对象。
    供消息平台适配器开发者使用，如果回复用户时需要使用原消息事件对象的信息，
    那么可以将其存到这个字段以供之后取出使用。"""


class FriendMessage(MessageEvent):
    """私聊消息。

    Args:
        type: 事件名。
        sender: 发送消息的好友。
        message_chain: 消息内容。
    """
    type: str = 'FriendMessage'
    """事件名。"""
    sender: platform_entities.Friend
    """发送消息的好友。"""
    message_chain: platform_message.MessageChain
    """消息内容。"""


class GroupMessage(MessageEvent):
    """群消息。

    Args:
        type: 事件名。
        sender: 发送消息的群成员。
        message_chain: 消息内容。
    """
    type: str = 'GroupMessage'
    """事件名。"""
    sender: platform_entities.GroupMember
    """发送消息的群成员。"""
    message_chain: platform_message.MessageChain
    """消息内容。"""
    @property
    def group(self) -> platform_entities.Group:
        return self.sender.group
