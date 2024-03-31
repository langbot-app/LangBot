from __future__ import annotations

import typing
import enum
import pydantic

import mirai


class FunctionCall(pydantic.BaseModel):
    name: str

    arguments: str


class ToolCall(pydantic.BaseModel):
    id: str

    type: str

    function: FunctionCall


class Message(pydantic.BaseModel):
    """消息"""

    role: str  # user, system, assistant, tool, command, plugin
    """消息的角色"""

    name: typing.Optional[str] = None
    """名称，仅函数调用返回时设置"""

    content: typing.Optional[str] | typing.Optional[mirai.MessageChain] = None
    """内容"""

    function_call: typing.Optional[FunctionCall] = None
    """函数调用，不再受支持，请使用tool_calls"""

    tool_calls: typing.Optional[list[ToolCall]] = None
    """工具调用"""

    tool_call_id: typing.Optional[str] = None

    def readable_str(self) -> str:
        if self.content is not None:
            return str(self.content)
        elif self.function_call is not None:
            return f'{self.function_call.name}({self.function_call.arguments})'
        elif self.tool_calls is not None:
            return f'调用工具: {self.tool_calls[0].id}'
        else:
            return '未知消息'
