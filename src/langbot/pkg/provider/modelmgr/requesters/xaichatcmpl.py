from __future__ import annotations

import typing
import openai

from . import chatcmpl


class XaiChatCompletions(chatcmpl.OpenAIChatCompletions):
    """xAI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.x.ai/v1',
        'timeout': 120,
    }
