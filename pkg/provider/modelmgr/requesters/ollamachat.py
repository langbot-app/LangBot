from __future__ import annotations

import asyncio
import os
import typing
from typing import Union, Mapping, Any, AsyncIterator

import async_lru
import ollama

from .. import entities, errors, requester
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....core import app
from ....utils import image

REQUESTER_NAME: str = "ollama-chat"


@requester.requester_class(REQUESTER_NAME)
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

    async def _closure(self, req_messages: list[dict], use_model: entities.LLMModelInfo,
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
                    elif me["type"] == "image_url":
                        image_url = await self.get_base64_str(me["image_url"]['url'])
                        image_urls.append(image_url)
                msg["content"] = "\n".join(text_content)
                msg["images"] = [url.split(',')[1] for url in image_urls]
        args["messages"] = messages

        resp: Mapping[str, Any] | AsyncIterator[Mapping[str, Any]] = await self._req(args)
        message: llm_entities.Message = await self._make_msg(resp)
        return message

    async def _make_msg(
            self,
            chat_completions: Union[Mapping[str, Any], AsyncIterator[Mapping[str, Any]]]) -> llm_entities.Message:
        message: Any = chat_completions.pop('message', None)
        if message is None:
            raise ValueError("chat_completions must contain a 'message' field")

        message.update(chat_completions)
        ret_msg: llm_entities.Message = llm_entities.Message(**message)
        return ret_msg

    async def call(
            self,
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
            return await self._closure(req_messages, model)
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')

    @async_lru.alru_cache(maxsize=128)
    async def get_base64_str(
            self,
            original_url: str,
    ) -> str:
        base64_image, image_format = await image.qq_image_url_to_base64(original_url)
        return f"data:image/{image_format};base64,{base64_image}"
