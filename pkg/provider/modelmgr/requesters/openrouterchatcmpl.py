from __future__ import annotations

import typing
import openai

from . import modelscopechatcmpl


class OpenRouterChatCompletions(modelscopechatcmpl.ModelScopeChatCompletions):
    """OpenRouter ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://openrouter.ai/api/v1',
        'timeout': 120,
    }
