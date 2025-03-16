from __future__ import annotations

import typing
import openai

from . import chatcmpl
from .. import requester
from ....core import app


class SiliconFlowChatCompletions(chatcmpl.OpenAIChatCompletions):
    """SiliconFlow ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base-url': 'https://api.siliconflow.cn/v1',
        'timeout': 120,
    }
