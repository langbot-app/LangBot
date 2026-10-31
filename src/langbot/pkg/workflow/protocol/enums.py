from __future__ import annotations

from enum import Enum


class ExecutionStatus(str, Enum):
    """工作流执行状态"""

    PENDING = "pending"
    """待执行"""

    RUNNING = "running"
    """执行中"""

    WAITING = "waiting"
    """等待中"""

    COMPLETED = "completed"
    """已完成"""

    FAILED = "failed"
    """执行失败"""

    CANCELLED = "cancelled"
    """已取消"""


class NodeStatus(str, Enum):
    """节点执行状态"""

    PENDING = "pending"
    """待执行"""

    RUNNING = "running"
    """执行中"""

    COMPLETED = "completed"
    """已完成"""

    FAILED = "failed"
    """执行失败"""

    SKIPPED = "skipped"
    """已跳过"""


class TriggerType(str, Enum):
    """工作流触发类型"""

    MESSAGE = "message"
    """消息触发"""

    CRON = "cron"
    """定时触发"""

    WEBHOOK = "webhook"
    """Webhook 触发"""

    EVENT = "event"
    """事件触发"""


class LauncherType(str, Enum):
    """会话类型"""

    PERSON = "person"
    """个人会话"""

    GROUP = "group"
    """群组会话"""


class PortType(str, Enum):
    """端口类型"""

    ANY = "any"
    """任意类型"""

    STRING = "string"
    """字符串"""

    NUMBER = "number"
    """数字"""

    INTEGER = "integer"
    """整数"""

    BOOLEAN = "boolean"
    """布尔值"""

    OBJECT = "object"
    """对象"""

    ARRAY = "array"
    """数组"""

    MESSAGE = "message"
    """消息对象"""

    PIPELINE_SELECTOR = "pipeline-selector"
    """流水线选择器"""

    MODEL_SELECTOR = "model-selector"
    """模型选择器"""

    JSON = "json"
    """JSON 数据"""

    TEXTAREA = "textarea"
    """多行文本"""

    SELECT = "select"
    """下拉选择"""
