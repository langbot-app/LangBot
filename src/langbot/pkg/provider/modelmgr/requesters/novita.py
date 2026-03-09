from __future__ import annotations

import typing

import openai

from . import chatcmpl


class NovitaChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Novita ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.novita.ai/openai',
        'timeout': 120,
    }
