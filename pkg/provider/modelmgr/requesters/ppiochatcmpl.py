from __future__ import annotations

import openai
import typing

from . import chatcmpl


class PPIOChatCompletions(chatcmpl.OpenAIChatCompletions):
    """欧派云 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.ppinfra.com/v3/openai',
        'timeout': 120,
    }
