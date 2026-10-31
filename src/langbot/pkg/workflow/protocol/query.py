from __future__ import annotations

import typing

import pydantic

import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.provider.prompt as provider_prompt
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter

from .entities import MessageContext, NodeState
from .enums import ExecutionStatus, TriggerType


class WorkflowQuery(pydantic.BaseModel):
    """Workflow 执行请求的信息封装

    类似于 Pipeline 的 Query 类，封装了 Workflow 执行时需要的上下文信息。
    """

    query_id: typing.Optional[int] = None
    """请求ID，添加进请求池时生成"""

    workflow_uuid: typing.Optional[str] = None
    """Workflow UUID，标识具体的工作流定义"""

    workflow_name: typing.Optional[str] = None
    """Workflow 名称，便于日志和调试中识别"""

    execution_id: typing.Optional[str] = None
    """执行ID，标识本次 Workflow 的具体执行实例"""

    launcher_type: typing.Optional[provider_session.LauncherTypes] = None
    """会话类型，platform处理阶段设置"""

    launcher_id: typing.Optional[typing.Union[int, str]] = None
    """会话ID，platform处理阶段设置"""

    sender_id: typing.Optional[typing.Union[int, str]] = None
    """发送者ID，platform处理阶段设置"""

    sender_name: typing.Optional[str] = None
    """发送者名称，用于显示和日志"""

    message_event: typing.Optional[platform_events.MessageEvent] = None
    """事件，platform收到的原始事件"""

    message_chain: typing.Optional[platform_message.MessageChain] = None
    """消息链，platform收到的原始消息链"""

    message_context: typing.Optional[MessageContext] = None
    """消息上下文，由 Workflow 引擎构建并传递给节点"""

    bot_uuid: typing.Optional[str] = None
    """机器人UUID，标识具体的机器人实例"""

    adapter: typing.Optional[abstract_platform_adapter.AbstractMessagePlatformAdapter] = None
    """消息平台适配器对象，单个app中可能启用了多个消息平台适配器，此对象表明发起此query的适配器"""

    session: typing.Optional[provider_session.Session] = None
    """会话对象，由前置处理器阶段设置"""

    messages: typing.Optional[
        list[typing.Union[provider_message.Message, provider_message.MessageChunk]]
    ] = []
    """历史消息列表，由前置处理器阶段设置"""

    prompt: typing.Optional[provider_prompt.Prompt] = None
    """情景预设内容，由前置处理器阶段设置"""

    user_message: typing.Optional[
        typing.Union[provider_message.Message, provider_message.MessageChunk]
    ] = None
    """此次请求的用户消息对象，由前置处理器阶段设置"""

    variables: typing.Optional[dict[str, typing.Any]] = None
    """变量字典，由前置处理器或节点设置和读取"""

    use_llm_model_uuid: typing.Optional[str] = None
    """使用的对话模型，由前置处理器阶段设置"""

    use_funcs: typing.Optional[list[resource_tool.LLMTool]] = None
    """使用的函数，由前置处理器阶段设置"""

    trigger_type: typing.Optional[TriggerType] = None
    """触发类型，标识本次 Workflow 的触发方式（如手动、定时、事件等）"""

    trigger_data: typing.Optional[dict[str, typing.Any]] = None
    """触发数据，与触发类型相关的附加信息"""

    node_states: typing.Optional[dict[str, NodeState]] = None
    """节点状态字典，记录各节点的执行状态和输出"""

    status: typing.Optional[ExecutionStatus] = None
    """执行状态，表示当前 Workflow 的执行状态（如运行中、成功、失败等）"""

    resp_messages: typing.Optional[
        list[typing.Union[provider_message.Message, provider_message.MessageChunk]]
    ] = []
    """由节点生成的回复消息对象列表"""

    resp_message_chain: typing.Optional[list[platform_message.MessageChain]] = None
    """回复消息链，从resp_messages包装而得"""

    class Config:
        arbitrary_types_allowed = True

    def model_dump(self, **kwargs):
        return {
            "query_id": self.query_id,
            "workflow_uuid": self.workflow_uuid,
            "workflow_name": self.workflow_name,
            "execution_id": self.execution_id,
            "launcher_type": self.launcher_type.value if self.launcher_type else None,
            "launcher_id": self.launcher_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "message_event": self.message_event.model_dump() if self.message_event else None,
            "message_chain": self.message_chain.model_dump() if self.message_chain else None,
            "message_context": self.message_context.model_dump() if self.message_context else None,
            "bot_uuid": self.bot_uuid,
            "session": self.session.model_dump() if self.session else None,
            "messages": [msg.model_dump() for msg in self.messages] if self.messages else [],
            "prompt": self.prompt.model_dump() if self.prompt else None,
            "user_message": self.user_message.model_dump() if self.user_message else None,
            "variables": self.variables,
            "use_llm_model_uuid": self.use_llm_model_uuid,
            "use_funcs": [func.model_dump() for func in self.use_funcs] if self.use_funcs else [],
            "trigger_type": self.trigger_type.value if self.trigger_type else None,
            "trigger_data": self.trigger_data,
            "status": self.status.value if self.status else None,
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
