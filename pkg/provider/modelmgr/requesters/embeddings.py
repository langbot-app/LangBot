from __future__ import annotations

import asyncio
import typing

import openai
import httpx

from .. import errors, requester
from ....core import entities as core_entities


class OpenAIEmbeddings(requester.LLMAPIRequester):
    """OpenAI Embeddings API 请求器"""

    name: str = "OpenAIEmbeddings"

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.openai.com/v1',
        'timeout': 120,
    }

    async def initialize(self):
        self.client = openai.AsyncClient(
            api_key='',
            base_url=self.requester_cfg['base_url'].replace(' ', ''),
            timeout=self.requester_cfg['timeout'],
            http_client=httpx.AsyncClient(trust_env=True, timeout=self.requester_cfg['timeout']),
        )

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List,
        funcs: typing.List = [],
        extra_args: dict[str, typing.Any] = {},
    ):
        """此请求器不支持 LLM 调用"""
        raise errors.RequesterError('此请求器不支持 LLM 调用')

    async def invoke_embeddings(
        self,
        query: core_entities.Query,
        model: requester.RuntimeEmbeddingsModel,
        input_text: str,
        extra_args: dict[str, typing.Any] = {},
    ) -> list[float]:
        """调用 Embeddings API"""
        self.client.api_key = model.token_mgr.get_token()

        args = {
            'model': model.model_entity.name,
            'input': input_text,
        }

        if model.model_entity.encoding_format:
            args['encoding_format'] = model.model_entity.encoding_format

        if model.model_entity.dimensions:
            args['dimensions'] = model.model_entity.dimensions

        args.update(extra_args)

        try:
            resp = await self.client.embeddings.create(**args)
            return resp.data[0].embedding
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
        except openai.BadRequestError as e:
            raise errors.RequesterError(f'请求参数错误: {e.message}')
        except openai.AuthenticationError as e:
            raise errors.RequesterError(f'无效的 api-key: {e.message}')
        except openai.NotFoundError as e:
            raise errors.RequesterError(f'请求路径错误: {e.message}')
        except openai.RateLimitError as e:
            raise errors.RequesterError(f'请求过于频繁或余额不足: {e.message}')
        except openai.APIError as e:
            raise errors.RequesterError(f'请求错误: {e.message}')
