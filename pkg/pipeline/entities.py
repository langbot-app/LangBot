from __future__ import annotations

import enum
import typing

import pydantic.v1 as pydantic
from ..platform.types import message as platform_message

from ..core import entities


class ResultType(enum.Enum):
    CONTINUE = enum.auto()
    """继续流水线"""

    INTERRUPT = enum.auto()
    """中断流水线"""


class StageProcessResult(pydantic.BaseModel):
    result_type: ResultType

    new_query: entities.Query

    user_notice: typing.Optional[
        typing.Union[
            str,
            list[platform_message.MessageComponent],
            platform_message.MessageChain,
            None,
        ]
    ] = []
    """只要设置了就会发送给用户"""

    console_notice: typing.Optional[str] = ''
    """只要设置了就会输出到控制台"""

    debug_notice: typing.Optional[str] = ''

    error_notice: typing.Optional[str] = ''
