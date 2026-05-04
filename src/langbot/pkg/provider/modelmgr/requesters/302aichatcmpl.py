from __future__ import annotations

import typing
import openai

from . import chatcmpl


class AI302ChatCompletions(chatcmpl.OpenAIChatCompletions):
    """302.AI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.302.ai/v1',
        'timeout': 120,
    }
