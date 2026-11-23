from __future__ import annotations

import typing

import pydantic

from . import requester
from . import token


class LLMModelInfo(pydantic.BaseModel):
    """模型"""

    name: str

    model_name: typing.Optional[str] = None

    token_mgr: token.TokenManager

    requester: requester.ProviderAPIRequester

    tool_call_supported: typing.Optional[bool] = False

    vision_supported: typing.Optional[bool] = False

    class Config:
        arbitrary_types_allowed = True
