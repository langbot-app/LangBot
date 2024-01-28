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
    role: str

    name: typing.Optional[str] = None

    content: typing.Optional[str] = None

    function_call: typing.Optional[FunctionCall] = None

    tool_calls: typing.Optional[list[ToolCall]] = None

    tool_call_id: typing.Optional[str] = None
