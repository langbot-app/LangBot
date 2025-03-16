from __future__ import annotations

import typing
import openai

from . import chatcmpl
from .. import requester
from ....core import app


class BailianChatCompletions(chatcmpl.OpenAIChatCompletions):
    """阿里云百炼大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base-url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'timeout': 120,
    }
