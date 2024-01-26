from __future__ import annotations

import typing
import enum
import pydantic


class MessageRole(enum.Enum):

    SYSTEM = 'system'

    USER = 'user'

    ASSISTANT = 'assistant'

    FUNCTION = 'function'


class FunctionCall(pydantic.BaseModel):
    name: str

    args: dict[str, typing.Any]


class Message(pydantic.BaseModel):

    role: MessageRole

    content: typing.Optional[str] = None

    function_call: typing.Optional[FunctionCall] = None
