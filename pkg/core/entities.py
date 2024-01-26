from __future__ import annotations

import enum
import typing

import pydantic
import mirai


class LauncherTypes(enum.Enum):

    PERSON = 'person'
    """私聊"""

    GROUP = 'group'
    """群聊"""


class Query(pydantic.BaseModel):
    """一次请求的信息封装"""

    query_id: int
    """请求ID"""

    launcher_type: LauncherTypes
    """会话类型"""

    launcher_id: int
    """会话ID"""

    sender_id: int
    """发送者ID"""

    message_event: mirai.MessageEvent
    """事件"""

    message_chain: mirai.MessageChain
    """消息链"""

    resp_message_chain: typing.Optional[mirai.MessageChain] = None
    """回复消息链"""
