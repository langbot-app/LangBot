from __future__ import annotations

import asyncio
import typing
import json
import base64
from typing import AsyncGenerator

import openai
import openai.types.chat.chat_completion as chat_completion
import httpx
import aiohttp

from .. import api, entities, errors
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....utils import image


@api.requester_class("openai-chat-completions")
class OpenAIChatCompletions(api.LLMAPIRequester):
    """OpenAI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    cached_image_oss_url: dict[str, str] = {}
    """缓存的OSS服务的图片URL
    
    key: 前文message中的原图片URL（QQ图片）
    value: OSS服务的图片URL
    """

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.cached_image_oss_url = {}

        self.requester_cfg = self.ap.provider_cfg.data['requester']['openai-chat-completions']

    async def initialize(self):

        self.client = openai.AsyncClient(
            api_key="",
            base_url=self.requester_cfg['base-url'],
            timeout=self.requester_cfg['timeout'],
            http_client=httpx.AsyncClient(
                proxies=self.ap.proxy_mgr.get_forward_proxies()
            )
        )

    async def _req(
        self,
        args: dict,
    ) -> chat_completion.ChatCompletion:
        self.ap.logger.debug(f"req chat_completion with args {args}")
        return await self.client.chat.completions.create(**args)

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.dict()

        message = llm_entities.Message(**chatcmpl_message)

        return message

    async def _closure(
        self,
        req_messages: list[dict],
        use_model: entities.LLMModelInfo,
        use_funcs: list[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        self.client.api_key = use_model.token_mgr.get_token()

        args = self.requester_cfg['args'].copy()
        args["model"] = use_model.name if use_model.model_name is None else use_model.model_name

        if use_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args["tools"] = tools

        # 设置此次请求中的messages
        messages = req_messages.copy()

        # 检查vision
        if self.ap.oss_mgr.available():
            for msg in messages:
                if 'content' in msg and isinstance(msg["content"], list):
                    for me in msg["content"]:
                        if me["type"] == "image_url":
                            # me["image_url"]['url'] = await self.get_oss_url(me["image_url"]['url'])
                            me["image_url"]['url'] = await self.get_base64_str(me["image_url"]['url'])

        args["messages"] = messages

        # 发送请求
        resp = await self._req(args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message
    
    async def call(
        self,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        req_messages = [  # req_messages 仅用于类内，外部同步由 query.messages 进行
            m.dict(exclude_none=True) for m in messages
        ]

        try:
            return await self._closure(req_messages, model, funcs)
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
        except openai.BadRequestError as e:
            if 'context_length_exceeded' in e.message:
                raise errors.RequesterError(f'上文过长，请重置会话: {e.message}')
            else:
                raise errors.RequesterError(f'请求参数错误: {e.message}')
        except openai.AuthenticationError as e:
            raise errors.RequesterError(f'无效的 api-key: {e.message}')
        except openai.NotFoundError as e:
            raise errors.RequesterError(f'请求路径错误: {e.message}')
        except openai.RateLimitError as e:
            raise errors.RequesterError(f'请求过于频繁或余额不足: {e.message}')
        except openai.APIError as e:
            raise errors.RequesterError(f'请求错误: {e.message}')

    async def get_oss_url(
        self,
        original_url: str,
    ) -> str:

        if original_url in self.cached_image_oss_url:
            return self.cached_image_oss_url[original_url]

        oss_url = await self.ap.oss_mgr.upload_url_image(original_url)

        self.cached_image_oss_url[original_url] = oss_url

        return oss_url

    async def get_base64_str(
        self,
        original_url: str,
    ) -> str:
        
        base64_image = await image.qq_image_url_to_base64(original_url)

        return f"data:image/jpeg;base64,{base64_image}"
