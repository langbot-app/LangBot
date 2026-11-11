from __future__ import annotations

import typing

import pydantic

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.prompt as provider_prompt
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot_plugin.api.entities.execution import WorkspaceExecutionScope


class Query(WorkspaceExecutionScope):
    """一次请求的信息封装"""

    query_id: int
    """请求ID，添加进请求池时生成"""

    query_uuid: str | None = None
    """Opaque query identifier used by Workspace-scoped hosts."""

    launcher_type: provider_session.LauncherTypes
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

    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter | None = None
    """消息平台适配器对象，单个app中可能启用了多个消息平台适配器，此对象表明发起此query的适配器"""

    session: provider_session.Session | None = None
    """会话对象，由前置处理器阶段设置"""

    messages: typing.Optional[
        list[typing.Union[provider_message.Message, provider_message.MessageChunk]]
    ] = []
    """历史消息列表，由前置处理器阶段设置"""

    prompt: provider_prompt.Prompt | None = None
    """情景预设内容，由前置处理器阶段设置"""

    user_message: typing.Optional[
        typing.Union[provider_message.Message, provider_message.MessageChunk]
    ] = None
    """此次请求的用户消息对象，由前置处理器阶段设置"""

    variables: typing.Optional[dict[str, typing.Any]] = None
    """变量，由前置处理器阶段设置。在prompt中嵌入或由 Runner 传递到 LLMOps 平台。"""

    use_llm_model_uuid: typing.Optional[str] = None
    """使用的对话模型，由前置处理器阶段设置"""

    use_funcs: typing.Optional[list[resource_tool.LLMTool]] = None
    """使用的函数，由前置处理器阶段设置"""

    resp_messages: (
        typing.Optional[
            list[typing.Union[provider_message.Message, provider_message.MessageChunk]]
        ]
        | typing.Optional[list[platform_message.MessageChain]]
    ) = []
    """由Process阶段生成的回复消息对象列表"""

    resp_message_chain: typing.Optional[list[platform_message.MessageChain]] = None
    """回复消息链，从resp_messages包装而得"""

    # ======= 内部保留 =======
    current_stage_name: typing.Optional[str] = None
    """当前所处阶段"""

    class Config:
        arbitrary_types_allowed = True

    @pydantic.model_validator(mode="after")
    def propagate_execution_scope(self) -> Query:
        """Keep nested Event and Session scope aligned with this Query."""

        self.inherit_execution_scope(self.message_event)
        self.inherit_execution_scope(self.session)
        self.message_event.inherit_execution_scope(self)
        if self.session is not None:
            self.session.inherit_execution_scope(self)
            if self.session.bot_uuid is None:
                self.session.bot_uuid = self.bot_uuid
            elif self.bot_uuid is not None and self.session.bot_uuid != self.bot_uuid:
                raise ValueError("Session bot_uuid does not match Query bot_uuid")
        return self

    def model_dump(self, **kwargs):
        return {
            **self.execution_scope_dump(),
            "query_id": self.query_id,
            **({"query_uuid": self.query_uuid} if self.query_uuid is not None else {}),
            "launcher_type": self.launcher_type.value,
            "launcher_id": self.launcher_id,
            "sender_id": self.sender_id,
            "message_event": self.message_event.model_dump(),
            "message_chain": self.message_chain.model_dump(),
            "bot_uuid": self.bot_uuid,
            "pipeline_uuid": self.pipeline_uuid,
            "pipeline_config": self.pipeline_config,
            "session": self.session.model_dump() if self.session else None,
            "messages": [message.model_dump() for message in self.messages],
            "prompt": self.prompt.model_dump() if self.prompt else None,
        }

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
