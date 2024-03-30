from __future__ import annotations

import asyncio
import typing
import json
from typing import AsyncGenerator

import openai
import openai.types.chat.chat_completion as chat_completion
import httpx

from .. import api, entities, errors
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities


@api.requester_class("openai-chat-completions")
class OpenAIChatCompletions(api.LLMAPIRequester):
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

        if use_model.tool_call_supported:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args["tools"] = tools

        # 设置此次请求中的messages
        messages = req_messages
        args["messages"] = messages

        # 发送请求
        resp = await self._req(args)

        # 处理请求结果
        message = await self._make_msg(resp)

        return message

    async def _request(
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """请求"""

        pending_tool_calls = []

        req_messages = [  # req_messages 仅用于类内，外部同步由 query.messages 进行
            m.dict(exclude_none=True) for m in query.prompt.messages if m.content.strip() != ""
        ] + [m.dict(exclude_none=True) for m in query.messages]

        # req_messages.append({"role": "user", "content": str(query.message_chain)})

        # 首次请求
        msg = await self._closure(req_messages, query.use_model, query.use_funcs)

        yield msg

        pending_tool_calls = msg.tool_calls

        req_messages.append(msg.dict(exclude_none=True))

        # 持续请求，只要还有待处理的工具调用就继续处理调用
        while pending_tool_calls:
            for tool_call in pending_tool_calls:
                try:
                    func = tool_call.function

                    parameters = json.loads(func.arguments)

                    func_ret = await self.ap.tool_mgr.execute_func_call(
                        query, func.name, parameters
                    )

                    msg = llm_entities.Message(
                        role="tool", content=json.dumps(func_ret, ensure_ascii=False), tool_call_id=tool_call.id
                    )

                    yield msg

                    req_messages.append(msg.dict(exclude_none=True))
                except Exception as e:
                    # 出错，添加一个报错信息到 req_messages
                    err_msg = llm_entities.Message(
                        role="tool", content=f"err: {e}", tool_call_id=tool_call.id
                    )

                    yield err_msg

                    req_messages.append(
                        err_msg.dict(exclude_none=True)
                    )

            # 处理完所有调用，继续请求
            msg = await self._closure(req_messages, query.use_model, query.use_funcs)

            yield msg

            pending_tool_calls = msg.tool_calls

            req_messages.append(msg.dict(exclude_none=True))

    async def request(self, query: core_entities.Query) -> AsyncGenerator[llm_entities.Message, None]:
        try:
            async for msg in self._request(query):
                yield msg
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
            raise errors.RequesterError(f'请求过于频繁: {e.message}')
        except openai.APIError as e:
            raise errors.RequesterError(f'请求错误: {e.message}')
