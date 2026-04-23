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

    async def scan_models(self, api_key: str | None = None) -> dict[str, typing.Any]:
        original_base_url = self.requester_cfg.get('base_url', '')
        self.requester_cfg['base_url'] = 'https://openrouter.ai/api/v1'
        try:
            return await super().scan_models(api_key)
        finally:
            self.requester_cfg['base_url'] = original_base_url
