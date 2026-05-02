from __future__ import annotations

import typing

import openai

from . import chatcmpl


class QiniuChatCompletions(chatcmpl.OpenAIChatCompletions):
    """七牛云 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.qnaigc.com/v1',
        'timeout': 120,
    }

    async def scan_models(self, api_key: str | None = None) -> dict[str, typing.Any]:
        try:
            result = await super().scan_models(api_key)
        except Exception:
            return self._qiniu_fallback_scan_result()
        models = result.get('models') or []
        if not models:
            return self._qiniu_fallback_scan_result()
        return result

    def _qiniu_fallback_scan_result(self) -> dict[str, typing.Any]:
        mid = 'deepseek-v3'
        return {
            'models': [
                {
                    'id': mid,
                    'name': mid,
                    'type': 'llm',
                    'abilities': [],
                }
            ],
            'debug': {
                'request': {'method': 'GET', 'url': '', 'headers': {}},
                'response': {},
            },
        }
