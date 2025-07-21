from __future__ import annotations

import enum
import typing
import datetime
import asyncio

import pydantic.v1 as pydantic

from ..provider import entities as llm_entities
from ..provider.modelmgr import requester
from ..provider.tools import entities as tools_entities
from ..platform import adapter as msadapter
from ..platform.types import message as platform_message
from ..platform.types import events as platform_events


class LifecycleControlScope(enum.Enum):
    APPLICATION = 'application'
    PLATFORM = 'platform'
    PLUGIN = 'plugin'
    PROVIDER = 'provider'  


class LauncherTypes(enum.Enum):
    """一个请求的发起者类型"""

    PERSON = 'person'
    """私聊"""

    GROUP = 'group'
    """群聊"""


class Query(pydantic.BaseModel):
    """一次请求的信息封装"""

    query_id: int
    """请求ID，添加进请求池时生成"""

    launcher_type: LauncherTypes
    """会话类型，platform处理阶段设置"""

    launcher_id: typing.Union[int, str]
    """会话ID，platform处理阶段设置"""

    sender_id: typing.Union[int, str]
    """发送者ID，platform处理阶段设置"""

    message_event: platform_events.MessageEvent
    """事件，platform收到的原始事件"""

    message_chain: platform_message.MessageChain
    """消息链，platform收到的原始消息链"""

    bot_uuid: typing.Optional[str] = None
    """机器人UUID。"""

    pipeline_uuid: typing.Optional[str] = None
    """流水线UUID。"""

    pipeline_config: typing.Optional[dict[str, typing.Any]] = None
    """流水线配置，由 Pipeline 在运行开始时设置。"""

    adapter: msadapter.MessagePlatformAdapter
    """消息平台适配器对象，单个app中可能启用了多个消息平台适配器，此对象表明发起此query的适配器"""

    session: typing.Optional[Session] = None
    """会话对象，由前置处理器阶段设置"""

    messages: typing.Optional[list[llm_entities.Message]] = []
    """历史消息列表，由前置处理器阶段设置"""

    prompt: typing.Optional[llm_entities.Prompt] = None
    """情景预设内容，由前置处理器阶段设置"""

    user_message: typing.Optional[llm_entities.Message] = None
    """此次请求的用户消息对象，由前置处理器阶段设置"""

    variables: typing.Optional[dict[str, typing.Any]] = None
    """变量，由前置处理器阶段设置。在prompt中嵌入或由 Runner 传递到 LLMOps 平台。"""

    use_llm_model: typing.Optional[requester.RuntimeLLMModel] = None
    """使用的对话模型，由前置处理器阶段设置"""

    use_funcs: typing.Optional[list[tools_entities.LLMFunction]] = None
    """使用的函数，由前置处理器阶段设置"""

    resp_messages: (
        typing.Optional[list[llm_entities.Message]] | typing.Optional[list[platform_message.MessageChain]]
    ) = []
    """由Process阶段生成的回复消息对象列表"""

    resp_message_chain: typing.Optional[list[platform_message.MessageChain]] = None
    """回复消息链，从resp_messages包装而得"""

    # ======= 内部保留 =======
    current_stage: typing.Optional['pkg.pipeline.pipelinemgr.StageInstContainer'] = None
    """当前所处阶段"""

    class Config:
        arbitrary_types_allowed = True

    # ========== 插件可调用的 API（请求 API） ==========

    def set_variable(self, key: str, value: typing.Any):
        """设置变量"""
        if self.variables is None:
            self.variables = {}
        self.variables[key] = value

    def get_variable(self, key: str) -> typing.Any:
        """获取变量"""
        if self.variables is None:
            return None
        return self.variables.get(key)

    def get_variables(self) -> dict[str, typing.Any]:
        """获取所有变量"""
        if self.variables is None:
            return {}
        return self.variables


class Conversation(pydantic.BaseModel):
    """对话，包含于 Session 中，一个 Session 可以有多个历史 Conversation，但只有一个当前使用的 Conversation"""

    prompt: llm_entities.Prompt

    messages: list[llm_entities.Message]

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    use_llm_model: typing.Optional[requester.RuntimeLLMModel] = None

    use_funcs: typing.Optional[list[tools_entities.LLMFunction]]

    pipeline_uuid: str
    """流水线UUID。"""

    bot_uuid: str
    """机器人UUID。"""

    uuid: typing.Optional[str] = None
    """该对话的 uuid，在创建时不会自动生成。而是当使用 Dify API 等由外部管理对话信息的服务时，用于绑定外部的会话。具体如何使用，取决于 Runner。"""

    class Config:
        arbitrary_types_allowed = True


class Session(pydantic.BaseModel):
    """会话，一个 Session 对应一个 {launcher_type.value}_{launcher_id}"""

    launcher_type: LauncherTypes

    launcher_id: typing.Union[int, str]

    sender_id: typing.Optional[typing.Union[int, str]] = 0

    use_prompt_name: typing.Optional[str] = 'default'

    using_conversation: typing.Optional[Conversation] = None

    conversations: typing.Optional[list[Conversation]] = pydantic.Field(default_factory=list)

    create_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    update_time: typing.Optional[datetime.datetime] = pydantic.Field(default_factory=datetime.datetime.now)

    semaphore: typing.Optional[asyncio.Semaphore] = None
    """当前会话的信号量，用于限制并发"""

    class Config:
        arbitrary_types_allowed = True
