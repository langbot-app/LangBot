# -*- coding: utf-8 -*-
"""
此模块提供事件模型。
"""
from datetime import datetime
from enum import Enum
import typing

import pydantic

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
# Bot Event
class BotEvent(Event):
    """Bot 自身事件。

    Args:
        type: 事件名。
        qq: Bot 的 QQ 号。
    """
    type: str
    """事件名。"""
    qq: int
    """Bot 的 QQ 号。"""


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


class FriendMessage(MessageEvent):
    """好友消息。

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


class StrangerMessage(MessageEvent):
    """陌生人消息。

    Args:
        type: 事件名。
        sender: 发送消息的人。
        message_chain: 消息内容。
    """
    type: str = 'StrangerMessage'
    """事件名。"""
    sender: platform_entities.Friend
    """发送消息的人。"""
    message_chain: platform_message.MessageChain
    """消息内容。"""
