from __future__ import annotations

import asyncio
import os
import typing
from typing import Union, Mapping, Any, AsyncIterator
import uuid
import json
import base64

import async_lru
import ollama

from .. import entities, errors, requester
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....core import app, entities as core_entities
from ....utils import image

REQUESTER_NAME: str = "ollama-chat"


class OllamaChatCompletions(requester.LLMAPIRequester):
    """Ollama平台 ChatCompletion API请求器"""
    client: ollama.AsyncClient
    request_cfg: dict

    def __init__(self, ap: app.Application):
        super().__init__(ap)
        self.ap = ap
        self.request_cfg = self.ap.provider_cfg.data['requester'][REQUESTER_NAME]

    async def initialize(self):
        os.environ['OLLAMA_HOST'] = self.request_cfg['base-url']
        self.client = ollama.AsyncClient(
            timeout=self.request_cfg['timeout']
        )

    async def _req(self,
                   args: dict,
                   ) -> Union[Mapping[str, Any], AsyncIterator[Mapping[str, Any]]]:
        return await self.client.chat(
            **args
        )

    async def _closure(self, query: core_entities.Query, req_messages: list[dict], use_model: entities.LLMModelInfo,
                       user_funcs: list[tools_entities.LLMFunction] = None) -> (
            llm_entities.Message):
        args: Any = self.request_cfg['args'].copy()
        args["model"] = use_model.name if use_model.model_name is None else use_model.model_name

        messages: list[dict] = req_messages.copy()
        for msg in messages:
            if 'content' in msg and isinstance(msg["content"], list):
                text_content: list = []
                image_urls: list = []
                for me in msg["content"]:
                    if me["type"] == "text":
                        text_content.append(me["text"])
                    elif me["type"] == "image_base64":
                        image_urls.append(me["image_base64"])
                        
                msg["content"] = "\n".join(text_content)
                msg["images"] = [url.split(',')[1] for url in image_urls]
            if 'tool_calls' in msg:  # LangBot 内部以 str 存储 tool_calls 的参数，这里需要转换为 dict
                for tool_call in msg['tool_calls']:
                    tool_call['function']['arguments'] = json.loads(tool_call['function']['arguments'])
        args["messages"] = messages

        args["tools"] = []
        if user_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(user_funcs)
            if tools:
                args["tools"] = tools

        resp = await self._req(args)
        message: llm_entities.Message = await self._make_msg(resp)
        return message

    async def _make_msg(
            self,
            chat_completions: ollama.ChatResponse) -> llm_entities.Message:
        message: ollama.Message = chat_completions.message
        if message is None:
            raise ValueError("chat_completions must contain a 'message' field")

        ret_msg: llm_entities.Message = None

        if message.content is not None:
            ret_msg = llm_entities.Message(
                role="assistant",
                content=message.content
            )
        if message.tool_calls is not None and len(message.tool_calls) > 0:
            tool_calls: list[llm_entities.ToolCall] = []

            for tool_call in message.tool_calls:
                tool_calls.append(llm_entities.ToolCall(
                    id=uuid.uuid4().hex,
                    type="function",
                    function=llm_entities.FunctionCall(
                        name=tool_call.function.name,
                        arguments=json.dumps(tool_call.function.arguments)
                    )
                ))
            ret_msg.tool_calls = tool_calls

        return ret_msg

    async def call(
            self,
            query: core_entities.Query,
            model: entities.LLMModelInfo,
            messages: typing.List[llm_entities.Message],
            funcs: typing.List[tools_entities.LLMFunction] = None,
    ) -> llm_entities.Message:
        req_messages: list = []
        for m in messages:
            msg_dict: dict = m.dict(exclude_none=True)
            content: Any = msg_dict.get("content")
            if isinstance(content, list):
                if all(isinstance(part, dict) and part.get('type') == 'text' for part in content):
                    msg_dict["content"] = "\n".join(part["text"] for part in content)
            req_messages.append(msg_dict)
        try:
            return await self._closure(query, req_messages, model, funcs)
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
