from __future__ import annotations

import asyncio
import os
import typing
from typing import Union, Mapping, Any, AsyncIterator
import uuid
import json

import ollama

from .. import errors, requester
from ... import entities as llm_entities
from ...tools import entities as tools_entities
from ....core import entities as core_entities

REQUESTER_NAME: str = 'ollama-chat'


class OllamaChatCompletions(requester.LLMAPIRequester):
    """Ollama平台 ChatCompletion API请求器"""

    client: ollama.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'http://127.0.0.1:11434',
        'timeout': 120,
    }

    async def initialize(self):
        os.environ['OLLAMA_HOST'] = self.requester_cfg['base_url']
        self.client = ollama.AsyncClient(timeout=self.requester_cfg['timeout'])

    async def _req(
        self,
        args: dict,
    ) -> Union[Mapping[str, Any], AsyncIterator[Mapping[str, Any]]]:
        return await self.client.chat(**args)

    async def _closure(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        user_funcs: list[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        args = extra_args.copy()
        args['model'] = use_model.model_entity.name

        messages: list[dict] = req_messages.copy()
        for msg in messages:
            if 'content' in msg and isinstance(msg['content'], list):
                text_content: list = []
                image_urls: list = []
                for me in msg['content']:
                    if me['type'] == 'text':
                        text_content.append(me['text'])
                    elif me['type'] == 'image_base64':
                        image_urls.append(me['image_base64'])

                msg['content'] = '\n'.join(text_content)
                msg['images'] = [url.split(',')[1] for url in image_urls]
            if 'tool_calls' in msg:  # LangBot 内部以 str 存储 tool_calls 的参数，这里需要转换为 dict
                for tool_call in msg['tool_calls']:
                    tool_call['function']['arguments'] = json.loads(tool_call['function']['arguments'])
        args['messages'] = messages

        args['tools'] = []
        if user_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(user_funcs)
            if tools:
                args['tools'] = tools

        resp = await self._req(args)
        message: llm_entities.Message = await self._make_msg(resp)
        return message

    async def _make_msg(self, chat_completions: ollama.ChatResponse) -> llm_entities.Message:
        message: ollama.Message = chat_completions.message
        if message is None:
            raise ValueError("chat_completions must contain a 'message' field")

        ret_msg: llm_entities.Message = None

        if message.content is not None:
            ret_msg = llm_entities.Message(role='assistant', content=message.content)
        if message.tool_calls is not None and len(message.tool_calls) > 0:
            tool_calls: list[llm_entities.ToolCall] = []

            for tool_call in message.tool_calls:
                tool_calls.append(
                    llm_entities.ToolCall(
                        id=uuid.uuid4().hex,
                        type='function',
                        function=llm_entities.FunctionCall(
                            name=tool_call.function.name,
                            arguments=json.dumps(tool_call.function.arguments),
                        ),
                    )
                )
            ret_msg.tool_calls = tool_calls

        return ret_msg

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        req_messages: list = []
        for m in messages:
            msg_dict: dict = m.dict(exclude_none=True)
            content: Any = msg_dict.get('content')
            if isinstance(content, list):
                if all(isinstance(part, dict) and part.get('type') == 'text' for part in content):
                    msg_dict['content'] = '\n'.join(part['text'] for part in content)
            req_messages.append(msg_dict)
        try:
            return await self._closure(
                query=query,
                req_messages=req_messages,
                use_model=model,
                use_funcs=funcs,
                extra_args=extra_args,
            )
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
