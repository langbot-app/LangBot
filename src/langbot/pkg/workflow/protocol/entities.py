from __future__ import annotations

import typing
from datetime import datetime
from typing import TYPE_CHECKING

import pydantic

from .enums import ExecutionStatus, NodeStatus

if TYPE_CHECKING:
    from .query import WorkflowQuery


class MessageContext(pydantic.BaseModel):
    """消息上下文

    包含消息的完整上下文信息，用于 Workflow 执行时的消息处理。
    """

    message_id: str
    """消息 ID"""

    message_content: str
    """消息内容"""

    sender_id: str
    """发送者 ID"""

    sender_name: str = ""
    """发送者名称"""

    platform: str = ""
    """平台标识（qq, wechat, telegram 等）"""

    conversation_id: str = ""
    """对话 ID"""

    is_group: bool = False
    """是否群聊"""

    group_id: typing.Optional[str] = None
    """群 ID"""

    mentions: list[str] = pydantic.Field(default_factory=list)
    """@提及列表"""

    reply_to: typing.Optional[str] = None
    """回复的消息 ID"""

    raw_message: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """原始消息数据"""

    class Config:
        arbitrary_types_allowed = True


class NodeState(pydantic.BaseModel):
    """节点执行状态

    记录单个节点的执行状态、输入输出和错误信息。
    """

    node_id: str
    """节点 ID"""

    node_type: str
    """节点类型"""

    status: NodeStatus
    """执行状态"""

    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """节点输入数据"""

    outputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """节点输出数据"""

    error: typing.Optional[str] = None
    """错误信息"""

    start_time: typing.Optional[datetime] = None
    """开始时间"""

    end_time: typing.Optional[datetime] = None
    """结束时间"""

    retry_count: int = 0
    """重试次数"""

    class Config:
        arbitrary_types_allowed = True


class ExecutionStep(pydantic.BaseModel):
    """执行步骤

    记录工作流执行过程中的每一步操作。
    """

    step_id: str
    """步骤 ID"""

    node_id: str
    """节点 ID"""

    node_type: str
    """节点类型"""

    status: NodeStatus
    """执行状态"""

    timestamp: datetime
    """执行时间戳"""

    duration_ms: typing.Optional[int] = None
    """执行耗时（毫秒）"""

    error: typing.Optional[str] = None
    """错误信息"""

    inputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """步骤输入数据"""

    outputs: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """步骤输出数据"""

    class Config:
        arbitrary_types_allowed = True


class ExecutionContext(pydantic.BaseModel):
    """工作流执行上下文

    贯穿整个工作流生命周期的执行上下文，包含执行状态、变量、节点状态等信息。
    """

    execution_id: str
    """执行唯一 ID（UUID）"""

    workflow_id: str
    """工作流 ID"""

    workflow_version: int = 1
    """工作流版本"""

    status: ExecutionStatus = ExecutionStatus.PENDING
    """执行状态"""

    error: typing.Optional[str] = None
    """错误信息"""

    variables: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """执行变量（当前执行有效）"""

    conversation_variables: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """会话变量（跨执行持久化）"""

    node_states: dict[str, NodeState] = pydantic.Field(default_factory=dict)
    """节点状态字典"""

    memory: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """工作流内存（用于存储/检索数据）"""

    start_time: typing.Optional[datetime] = None
    """开始时间"""

    end_time: typing.Optional[datetime] = None
    """结束时间"""

    message_context: typing.Optional[MessageContext] = None
    """消息触发时的上下文"""

    query: typing.Optional[typing.Union[str, WorkflowQuery]] = None
    """用户查询文本或 WorkflowQuery 对象（用于日志记录和获取 launcher_type 等信息）"""

    trigger_type: typing.Optional[str] = None
    """触发类型：message | cron | webhook | event"""

    trigger_data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """触发器数据"""

    history: list[ExecutionStep] = pydantic.Field(default_factory=list)
    """执行步骤历史"""

    session_id: typing.Optional[str] = None
    """会话 ID"""

    user_id: typing.Optional[str] = None
    """用户 ID"""

    bot_id: typing.Optional[str] = None
    """机器人 ID"""

    class Config:
        arbitrary_types_allowed = True

    def get_variable(self, key: str) -> typing.Any:
        """获取执行变量"""
        return self.variables.get(key)

    def set_variable(self, key: str, value: typing.Any) -> None:
        """设置执行变量"""
        self.variables[key] = value

    def get_conversation_variable(self, key: str) -> typing.Any:
        """获取会话变量"""
        return self.conversation_variables.get(key)

    def set_conversation_variable(self, key: str, value: typing.Any) -> None:
        """设置会话变量"""
        self.conversation_variables[key] = value

    def get_node_state(self, node_id: str) -> typing.Optional[NodeState]:
        """获取节点状态"""
        return self.node_states.get(node_id)

    def set_node_state(self, node_id: str, state: NodeState) -> None:
        """设置节点状态"""
        self.node_states[node_id] = state


class MessageEnvelope(pydantic.BaseModel):
    """Workflow 消息信封

    与 Pipeline Query 兼容的消息载体，用于 Workflow 节点间的通信。
    """

    # ====== 消息来源字段（来自 Platform） ======
    message_id: str
    """消息唯一 ID"""

    message_content: str
    """消息文本内容"""

    message_chain: list[typing.Any] = pydantic.Field(default_factory=list)
    """原始消息链（平台特定）"""

    sender_id: str
    """发送者 ID"""

    sender_name: str = ""
    """发送者名称"""

    platform: str = ""
    """平台标识（qq, wechat, telegram 等）"""

    # ====== 会话字段 ======
    session_id: str = ""
    """会话 ID"""

    conversation_id: str = ""
    """对话 ID"""

    launcher_type: str = "person"
    """会话类型：'person' | 'group'"""

    launcher_id: str = ""
    """会话 ID（群号/用户 ID）"""

    is_group: bool = False
    """是否群聊"""

    # ====== 上下文字段 ======
    bot_id: str = ""
    """机器人 ID"""

    user_id: str = ""
    """用户 ID"""

    mentions: list[str] = pydantic.Field(default_factory=list)
    """@提及列表"""

    reply_to: typing.Optional[str] = None
    """回复的消息 ID"""

    raw_message: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """原始消息数据"""

    # ====== 处理字段（由节点填充） ======
    variables: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """变量字典"""

    conversation_variables: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """会话变量（跨执行持久化）"""

    memory: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """工作流内存"""

    # ====== 输出字段（由 End 节点或 Reply 节点设置） ======
    response: typing.Optional[str] = None
    """响应文本"""

    response_chain: list[typing.Any] = pydantic.Field(default_factory=list)
    """响应消息链"""

    status: str = "pending"
    """状态：'success' | 'error' | 'cancelled'"""

    # ====== 内部字段 ======
    execution_id: str = ""
    """执行 ID"""

    workflow_id: str = ""
    """工作流 ID"""

    trigger_type: str = ""
    """触发类型：'message' | 'cron' | 'webhook' | 'event'"""

    trigger_data: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """触发器数据"""

    class Config:
        arbitrary_types_allowed = True

    def get_variable(self, key: str) -> typing.Any:
        """获取变量"""
        return self.variables.get(key)

    def set_variable(self, key: str, value: typing.Any) -> None:
        """设置变量"""
        self.variables[key] = value

    def get_variables(self) -> dict[str, typing.Any]:
        """获取所有变量"""
        return self.variables

    def get_conversation_variable(self, key: str) -> typing.Any:
        """获取会话变量"""
        return self.conversation_variables.get(key)

    def set_conversation_variable(self, key: str, value: typing.Any) -> None:
        """设置会话变量"""
        self.conversation_variables[key] = value

    def is_success(self) -> bool:
        """检查是否成功"""
        return self.status == "success"

    def is_error(self) -> bool:
        """检查是否出错"""
        return self.status == "error"

    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.status == "cancelled"


class PortDefinition(pydantic.BaseModel):
    """端口定义

    描述节点输入/输出的类型和约束。
    """

    name: str
    """端口名称"""

    type: str
    """端口类型"""

    required: bool = False
    """是否必填"""

    label: dict[str, str] = pydantic.Field(default_factory=dict)
    """多语言标签"""

    description: dict[str, str] = pydantic.Field(default_factory=dict)
    """多语言描述"""

    default_value: typing.Optional[typing.Any] = None
    """默认值"""

    class Config:
        arbitrary_types_allowed = True


class NodeDefinition(pydantic.BaseModel):
    """节点定义

    描述工作流中的节点配置。
    """

    id: str
    """节点 ID"""

    type: str
    """节点类型"""

    label: str = ""
    """节点标签"""

    config: dict[str, typing.Any] = pydantic.Field(default_factory=dict)
    """节点配置"""

    inputs: list[PortDefinition] = pydantic.Field(default_factory=list)
    """输入端口定义"""

    outputs: list[PortDefinition] = pydantic.Field(default_factory=list)
    """输出端口定义"""

    class Config:
        arbitrary_types_allowed = True
