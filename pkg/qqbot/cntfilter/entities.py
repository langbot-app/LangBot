
import typing
import enum

import pydantic


class ResultLevel(enum.Enum):
    """结果等级"""
    PASS = enum.auto()
    """通过"""

    WARN = enum.auto()
    """警告"""

    MASKED = enum.auto()
    """已掩去"""

    BLOCK = enum.auto()
    """阻止"""


class EnableStage(enum.Enum):
    """启用阶段"""
    PRE = enum.auto()
    """预处理"""

    POST = enum.auto()
    """后处理"""


class FilterResult(pydantic.BaseModel):
    level: ResultLevel

    replacement: str
    """替换后的消息"""

    user_notice: str
    """不通过时，用户提示消息"""

    console_notice: str
    """不通过时，控制台提示消息"""


class ManagerResultLevel(enum.Enum):
    """处理器结果等级"""
    CONTINUE = enum.auto()
    """继续"""

    INTERRUPT = enum.auto()
    """中断"""

class FilterManagerResult(pydantic.BaseModel):

    level: ManagerResultLevel

    replacement: str
    """替换后的消息"""

    user_notice: str
    """用户提示消息"""

    console_notice: str
    """控制台提示消息"""
