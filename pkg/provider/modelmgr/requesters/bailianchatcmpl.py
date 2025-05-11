from __future__ import annotations

import typing
import openai

from . import modelscopechatcmpl


class BailianChatCompletions(modelscopechatcmpl.ModelScopeChatCompletions):
    """阿里云百炼大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'timeout': 120,
    }
