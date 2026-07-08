from __future__ import annotations

import enum
import typing

import pydantic

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class ResultType(enum.Enum):
    CONTINUE = enum.auto()
    """继续流水线"""

    INTERRUPT = enum.auto()
    """中断流水线"""


class StageProcessResult(pydantic.BaseModel):
    result_type: ResultType

    new_query: pipeline_query.Query

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
