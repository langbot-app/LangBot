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
    """结果等级

    对于前置处理阶段，只要有任意一个返回 非PASS 的内容过滤器结果，就会中断处理。
    对于后置处理阶段，当且内容过滤器返回 BLOCK 时，会中断处理。
    """

    replacement: str
    """替换后的文本消息
    
    内容过滤器可以进行一些遮掩处理，然后把遮掩后的消息返回。
    若没有修改内容，也需要返回原消息。
    """

    user_notice: str
    """不通过时，若此值不为空，将对用户提示消息"""

    console_notice: str
    """不通过时，若此值不为空，将在控制台提示消息"""


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
