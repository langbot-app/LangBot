from __future__ import annotations

import typing
import openai

from . import chatcmpl


class CompShareChatCompletions(chatcmpl.OpenAIChatCompletions):
    """CompShare ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.modelverse.cn/v1',
        'timeout': 120,
    }
