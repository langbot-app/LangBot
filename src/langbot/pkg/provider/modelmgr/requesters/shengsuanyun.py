from __future__ import annotations

import openai
import typing

from . import chatcmpl
import openai.types.chat.chat_completion as chat_completion


class ShengSuanYunChatCompletions(chatcmpl.OpenAIChatCompletions):
    """胜算云(ModelSpot.AI) ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://router.shengsuanyun.com/api/v1',
        'timeout': 120,
    }

    async def _req(
        self,
        args: dict,
        extra_body: dict = {},
    ) -> chat_completion.ChatCompletion:
        return await self.client.chat.completions.create(
            **args,
            extra_body=extra_body,
            extra_headers={
                'HTTP-Referer': 'https://langbot.app',
                'X-Title': 'LangBot',
            },
        )
