from __future__ import annotations

import typing
import openai

from . import chatcmpl


class LangBotSpaceChatCompletions(chatcmpl.OpenAIChatCompletions):
    """LangBot Space ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.langbot.cloud/v1',
        'timeout': 120,
    }
