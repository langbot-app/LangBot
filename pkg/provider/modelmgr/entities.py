from __future__ import annotations

import typing

import pydantic

from . import api
from . import token


class LLMModelInfo(pydantic.BaseModel):
    """模型"""

    name: str

    model_name: typing.Optional[str] = None

    token_mgr: token.TokenManager

    requester: api.LLMAPIRequester

    tool_call_supported: typing.Optional[bool] = False

    class Config:
        arbitrary_types_allowed = True
