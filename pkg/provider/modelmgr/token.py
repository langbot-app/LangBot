from __future__ import annotations

import typing

import pydantic


class TokenManager():
    """鉴权 Token 管理器
    """

    provider: str

    tokens: list[str]

    using_token_index: typing.Optional[int] = 0

    def __init__(self, provider: str, tokens: list[str]):
        self.provider = provider
        self.tokens = tokens
        self.using_token_index = 0

    def get_token(self) -> str:
        return self.tokens[self.using_token_index]
    
    def next_token(self):
        self.using_token_index = (self.using_token_index + 1) % len(self.tokens)
