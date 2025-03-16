from __future__ import annotations

import typing
import openai

from . import chatcmpl
from .. import requester
from ....core import app


class XaiChatCompletions(chatcmpl.OpenAIChatCompletions):
    """xAI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base-url': 'https://api.x.ai/v1',
        'timeout': 120,
    }
