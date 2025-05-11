from __future__ import annotations

import typing
import openai

from . import chatcmpl


class ZhipuAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """智谱AI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'timeout': 120,
    }
