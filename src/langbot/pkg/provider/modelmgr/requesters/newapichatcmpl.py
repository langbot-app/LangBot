from __future__ import annotations

import typing
import openai

from . import chatcmpl


class NewAPIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """New API ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'http://localhost:3000/v1',
        'timeout': 120,
    }
