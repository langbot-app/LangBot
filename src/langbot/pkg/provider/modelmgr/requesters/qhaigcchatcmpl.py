from __future__ import annotations

import openai
import typing

from . import chatcmpl


class QHAIGCChatCompletions(chatcmpl.OpenAIChatCompletions):
    """启航 AI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.qhaigc.com/v1',
        'timeout': 120,
    }
