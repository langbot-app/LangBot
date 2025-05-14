from __future__ import annotations

import typing
import google.genai
from google.genai import types

from .. import errors, requester
from ....core import entities as core_entities
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class GeminiChatCompletions(requester.LLMAPIRequester):
    """Google Gemini API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://generativelanguage.googleapis.com',
        'timeout': 120,
    }

    async def initialize(self):
        """初始化 Gemini API 客户端"""
        pass

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        """调用 Gemini API 生成回复"""
        try:
            self.client = google.genai.Client(
                api_key=model.token_mgr.get_token(),
                http_options=types.HttpOptions(api_version='v1alpha'),
            )
            contents = []

            system_content = None

            for message in messages:
                role = message.role
                parts = []

                if isinstance(message.content, str):
                    parts.append(types.Part.from_text(text=message.content))
                elif isinstance(message.content, list):
                    for content in message.content:
                        if content.type == 'text':
                            parts.append(types.Part.from_text(text=content.text))
                        # elif content.type == 'image_url':
                        #     parts.append(types.Part.from_image_url(url=content.image_url))

                if role == 'system':
                    system_content = parts
                else:
                    content = types.Content(role=role, parts=parts)
                    contents.append(content)

            response = self.client.models.generate_content(
                model=model.model_entity.name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_content,
                    **extra_args,
                ),
            )

            return llm_entities.Message(
                role='assistant',
                content=response.candidates[0].content.parts[0].text,
            )

        except Exception as e:
            error_message = str(e).lower()
            if 'invalid api key' in error_message:
                raise errors.RequesterError(f'无效的 API 密钥: {str(e)}')
            elif 'not found' in error_message:
                raise errors.RequesterError(f'请求路径错误或模型无效: {str(e)}')
            elif any(keyword in error_message for keyword in ['rate limit', 'quota', 'permission denied']):
                raise errors.RequesterError(f'请求过于频繁或余额不足: {str(e)}')
            elif 'timeout' in error_message:
                raise errors.RequesterError(f'请求超时: {str(e)}')
            else:
                raise errors.RequesterError(f'Gemini API 请求错误: {str(e)}')
