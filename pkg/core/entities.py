from __future__ import annotations

import enum
import typing
import datetime
import asyncio

import pydantic
import mirai

from ..provider import entities as llm_entities
from ..provider.requester import entities
from ..provider.sysprompt import entities as sysprompt_entities
from ..provider.tools import entities as tools_entities


class LauncherTypes(enum.Enum):

    PERSON = 'person'
    """私聊"""

    GROUP = 'group'
    """群聊"""


class Query(pydantic.BaseModel):
    """一次请求的信息封装"""

    query_id: int
    """请求ID，添加进请求池时生成"""

    launcher_type: LauncherTypes
    """会话类型，platform设置"""

    launcher_id: int
    """会话ID，platform设置"""

    sender_id: int
    """发送者ID，platform设置"""

    message_event: mirai.MessageEvent
    """事件，platform收到的事件"""

    message_chain: mirai.MessageChain
    """消息链，platform收到的消息链"""

    session: typing.Optional[Session] = None

    resp_messages: typing.Optional[list[llm_entities.Message]] = []
    """由provider生成的回复消息对象列表"""

    resp_message_chain: typing.Optional[mirai.MessageChain] = None
    """回复消息链，从resp_messages包装而得"""


class Conversation(pydantic.BaseModel):
    """对话"""

    prompt: sysprompt_entities.Prompt

    messages: list[llm_entities.Message]

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    use_model: entities.LLMModelInfo

    use_funcs: typing.Optional[list[tools_entities.LLMFunction]]


class Session(pydantic.BaseModel):
    """会话"""
    launcher_type: LauncherTypes

    launcher_id: int

    sender_id: typing.Optional[int] = 0

    use_prompt_name: typing.Optional[str] = 'default'

    using_conversation: typing.Optional[Conversation] = None

    conversations: typing.Optional[list[Conversation]] = []

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    semaphore: typing.Optional[asyncio.Semaphore] = None

    class Config:
        arbitrary_types_allowed = True
