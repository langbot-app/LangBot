import typing

import pydantic

from . import api
from . import token


class LLMModelInfo(pydantic.BaseModel):
    """模型"""

    name: str

    provider: str

    token_mgr: token.TokenManager

    requester: api.LLMAPIRequester

    function_call_supported: typing.Optional[bool] = False

    class Config:
        arbitrary_types_allowed = True
