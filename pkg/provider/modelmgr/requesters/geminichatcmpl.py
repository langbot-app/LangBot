from __future__ import annotations

import typing

from . import chatcmpl


class GeminiChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Google Gemini API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'timeout': 120,
    }
