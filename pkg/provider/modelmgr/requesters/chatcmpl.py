from __future__ import annotations

import asyncio
import typing
import json
import base64
from typing import AsyncGenerator

import openai
import openai.types.chat.chat_completion as chat_completion
import openai.types.chat.chat_completion_message_tool_call as chat_completion_message_tool_call
import httpx
import aiohttp
import async_lru

from .. import entities, errors, requester
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....utils import image


class OpenAIChatCompletions(requester.LLMAPIRequester):
    """OpenAI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    requester_cfg: dict

    def __init__(self, ap: app.Application):
        self.ap = ap

        self.requester_cfg = self.ap.provider_cfg.data['requester']['openai-chat-completions']

    async def initialize(self):

        self.client = openai.AsyncClient(
            api_key="",
            base_url=self.requester_cfg['base-url'],
            timeout=self.requester_cfg['timeout'],
            http_client=httpx.AsyncClient(
                trust_env=True,
                timeout=self.requester_cfg['timeout']
            )
        )

    async def _req(
        self,
        args: dict,
    ) -> chat_completion.ChatCompletion:
        return await self.client.chat.completions.create(**args)

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.dict()

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        message = llm_entities.Message(**chatcmpl_message)

        return message

    async def _closure(
        self,
        query: core_entities.Query,
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
        for msg in messages:
            if 'content' in msg and isinstance(msg["content"], list):
                for me in msg["content"]:
                    if me["type"] == "image_base64":
                        me["image_url"] = {
                            "url": me["image_base64"]
                        }
                        me["type"] = "image_url"
                        del me["image_base64"]

        args["messages"] = messages

        # 发送请求
        resp = await self._req(args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message
    
    async def call(
        self,
        query: core_entities.Query,
        model: entities.LLMModelInfo,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        req_messages = []  # req_messages 仅用于类内，外部同步由 query.messages 进行
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get("content")
            if isinstance(content, list):
                # 检查 content 列表中是否每个部分都是文本
                if all(isinstance(part, dict) and part.get("type") == "text" for part in content):
                    # 将所有文本部分合并为一个字符串
                    msg_dict["content"] = "\n".join(part["text"] for part in content)
            req_messages.append(msg_dict)

        try:
            return await self._closure(query=query, req_messages=req_messages, use_model=model, use_funcs=funcs)
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
