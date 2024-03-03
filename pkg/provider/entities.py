from __future__ import annotations

import typing
import enum
import pydantic


class FunctionCall(pydantic.BaseModel):
    name: str

    arguments: str


class ToolCall(pydantic.BaseModel):
    id: str

    type: str

    function: FunctionCall


class Message(pydantic.BaseModel):
    """消息"""

    role: str  # user, system, assistant, tool, command

    name: typing.Optional[str] = None

    content: typing.Optional[str] = None

    function_call: typing.Optional[FunctionCall] = None

    tool_calls: typing.Optional[list[ToolCall]] = None

    tool_call_id: typing.Optional[str] = None

    def readable_str(self) -> str:
        if self.content is not None:
            return self.content
        elif self.function_call is not None:
            return f'{self.function_call.name}({self.function_call.arguments})'
        elif self.tool_calls is not None:
            return f'调用工具: {self.tool_calls[0].id}'
        else:
            return '未知消息'
