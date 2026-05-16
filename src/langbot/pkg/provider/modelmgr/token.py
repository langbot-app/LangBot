from __future__ import annotations

import typing


class TokenManager:
    """鉴权 Token 管理器"""

    name: str

    tokens: list[str]

    using_token_index: typing.Optional[int] = 0

    def __init__(self, name: str, tokens: list[str]):
        self.name = name
        self.tokens = []
        seen_tokens = set()
        for token in tokens:
            normalized_token = token.strip() if isinstance(token, str) else ''
            if not normalized_token or normalized_token in seen_tokens:
                continue
            self.tokens.append(normalized_token)
            seen_tokens.add(normalized_token)
        self.using_token_index = 0

    def get_token(self) -> str:
        if len(self.tokens) == 0:
            return ''
        return self.tokens[self.using_token_index]

    def next_token(self):
        if len(self.tokens) == 0:
            return
        self.using_token_index = (self.using_token_index + 1) % len(self.tokens)
