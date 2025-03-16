from __future__ import annotations

import typing
import openai

from . import chatcmpl
from .. import requester
from ....core import app


class VolcArkChatCompletions(chatcmpl.OpenAIChatCompletions):
    """火山方舟大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base-url': 'https://ark.cn-beijing.volces.com/api/v3',
        'timeout': 120,
    }
