from __future__ import annotations

import typing

import pydantic
import mirai

from . import context
from ..core import entities as core_entities


class BaseEventModel(pydantic.BaseModel):

    class Config:
        arbitrary_types_allowed = True


class PersonMessageReceived(BaseEventModel):
    """收到任何私聊消息时"""

    launcher_type: str
    """发起对象类型(group/person)"""

    launcher_id: int
    """发起对象ID(群号/QQ号)"""
    
    sender_id: int
    """发送者ID(QQ号)"""

    message_chain: mirai.MessageChain

    query: core_entities.Query
    """此次请求的上下文"""


class GroupMessageReceived(BaseEventModel):
    """收到任何群聊消息时"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    message_chain: mirai.MessageChain

    query: core_entities.Query
    """此次请求的上下文"""


class PersonNormalMessageReceived(BaseEventModel):
    """判断为应该处理的私聊普通消息时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    text_message: str

    query: core_entities.Query
    """此次请求的上下文"""

    alter: typing.Optional[str] = None
    """修改后的消息文本"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""


class PersonCommandSent(BaseEventModel):
    """判断为应该处理的私聊命令时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    command: str

    params: list[str]

    text_message: str

    is_admin: bool

    query: core_entities.Query
    """此次请求的上下文"""

    alter: typing.Optional[str] = None
    """修改后的完整命令文本"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""
