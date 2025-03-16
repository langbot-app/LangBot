from __future__ import annotations

import typing
import openai

from . import chatcmpl
from .. import requester
from ....core import app


class LmStudioChatCompletions(chatcmpl.OpenAIChatCompletions):
    """LMStudio ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base-url': 'http://127.0.0.1:1234/v1',
        'timeout': 120,
    }
