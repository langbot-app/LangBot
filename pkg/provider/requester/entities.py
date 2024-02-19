from __future__ import annotations

import typing

import pydantic

from . import api
from . import token, tokenizer


class LLMModelInfo(pydantic.BaseModel):
    """模型"""

    name: str

    model_name: typing.Optional[str] = None

    token_mgr: token.TokenManager

    requester: api.LLMAPIRequester

    tokenizer: 'tokenizer.LLMTokenizer'

    tool_call_supported: typing.Optional[bool] = False

    max_tokens: typing.Optional[int] = 2048

    class Config:
        arbitrary_types_allowed = True
