from __future__ import annotations

import typing

import pydantic
import mirai

from . import context
from ..core import entities as core_entities
from ..provider import entities as llm_entities


class BaseEventModel(pydantic.BaseModel):

    query: core_entities.Query

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


class GroupMessageReceived(BaseEventModel):
    """收到任何群聊消息时"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    message_chain: mirai.MessageChain


class PersonNormalMessageReceived(BaseEventModel):
    """判断为应该处理的私聊普通消息时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    text_message: str

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

    alter: typing.Optional[str] = None
    """修改后的完整命令文本"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""


class GroupNormalMessageReceived(BaseEventModel):
    """判断为应该处理的群聊普通消息时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    text_message: str

    alter: typing.Optional[str] = None
    """修改后的消息文本"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""


class GroupCommandSent(BaseEventModel):
    """判断为应该处理的群聊命令时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    command: str

    params: list[str]

    text_message: str

    is_admin: bool

    alter: typing.Optional[str] = None
    """修改后的完整命令文本"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""


class NormalMessageResponded(BaseEventModel):
    """回复普通消息时触发"""

    launcher_type: str

    launcher_id: int
    
    sender_id: int

    session: core_entities.Session
    """会话对象"""

    prefix: str
    """回复消息的前缀，可修改"""

    response_text: str
    """回复消息的文本"""

    finish_reason: str
    """响应结束原因"""

    funcs_called: list[str]
    """调用的函数列表"""

    reply: typing.Optional[list] = None
    """回复消息组件列表"""


class ConversationFirstMessageReceived(BaseEventModel):
    """会话中收到第一条消息时触发"""
    
    session_name: str

    session: core_entities.Session

    default_prompt: str


SessionFirstMessageReceived = ConversationFirstMessageReceived
"""[过时]"""


class SessionExplicitReset(BaseEventModel):
    """会话被显式重置时触发"""

    session_name: str

    session: core_entities.Session


class SessionExpired(BaseEventModel):
    """会话过期时触发"""

    session_name: str

    session: core_entities.Session

    session_expire_time: int


class KeyExceeded(BaseEventModel):
    """[过时]会话中使用的Key超过限制时触发"""

    key_name: str


class KeySwitched(BaseEventModel):
    """[过时]会话中使用的Key切换时触发"""

    key_name: str


class PromptPreProcessing(BaseEventModel):
    """会话中的Prompt预处理时触发"""

    session_name: str

    default_prompt: list[llm_entities.Message]
    """此对话的情景预设，可修改"""

    prompt: list[llm_entities.Message]
    """此对话现有消息记录，可修改"""
    
    text_message: str
    """消息文本，可修改"""
