from __future__ import annotations

import openai
import typing

from . import chatcmpl
import openai.types.chat.chat_completion as chat_completion
from .. import errors, requester
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities
import re


class PPIOChatCompletions(chatcmpl.OpenAIChatCompletions):
    """欧派云 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.ppinfra.com/v3/openai',
        'timeout': 120,
    }

    is_think: bool = False

    async def _make_msg(
            self,
            chat_completion: chat_completion.ChatCompletion,
            pipeline_config: dict[str, typing.Any] = {'trigger': {'misc': {'remove_think': False}}},
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.model_dump()
        # print(chatcmpl_message.keys(), chatcmpl_message.values())

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        reasoning_content = chatcmpl_message['reasoning_content'] if 'reasoning_content' in chatcmpl_message else None

        # deepseek的reasoner模型
        if pipeline_config['trigger'].get('misc', '').get('remove_think'):
            chatcmpl_message['content'] = re.sub(r'<think>.*?</think>', '', chatcmpl_message['content'], flags=re.DOTALL)
        else:
            if reasoning_content is not None:
                chatcmpl_message['content'] = '<think>\n' + reasoning_content + '\n</think>\n' + chatcmpl_message['content']

        message = llm_entities.Message(**chatcmpl_message)

        return message


    async def _make_msg_chunk(
            self,
            pipeline_config: dict[str, typing.Any],
            chat_completion: chat_completion.ChatCompletion,
            idx: int,
    ) -> llm_entities.MessageChunk:
        # 处理流式chunk和完整响应的差异
        # print(chat_completion.choices[0])
        if hasattr(chat_completion, 'choices'):
            # 完整响应模式
            choice = chat_completion.choices[0]
            delta = choice.delta.model_dump() if hasattr(choice, 'delta') else choice.message.model_dump()
        else:
            # 流式chunk模式
            delta = chat_completion.delta.model_dump() if hasattr(chat_completion, 'delta') else {}

        # 确保 role 字段存在且不为 None
        if 'role' not in delta or delta['role'] is None:
            delta['role'] = 'assistant'

        reasoning_content = delta['reasoning_content'] if 'reasoning_content' in delta else None

        delta['content'] = '' if delta['content'] is None else delta['content']
        # print(reasoning_content)

        # deepseek的reasoner模型
        if pipeline_config['trigger'].get('misc', '').get('remove_think'):
            if '<think>' in delta['content']:
                self.is_think = True
                delta['content'] = ''
            if rf'</think>' in delta['content']:
                self.is_think = False
                delta['content'] = ''
            if not self.is_think:
                delta['content'] = delta['content']
            else:
                delta['content'] = ''
        else:
            if reasoning_content is not None:
                delta['content'] += reasoning_content

        message = llm_entities.MessageChunk(**delta)

        return message


    async def _closure_stream(
            self,
            query: core_entities.Query,
            req_messages: list[dict],
            use_model: requester.RuntimeLLMModel,
            use_funcs: list[tools_entities.LLMFunction] = None,
            stream: bool = False,
            extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message | typing.AsyncGenerator[llm_entities.MessageChunk, None]:
        self.client.api_key = use_model.token_mgr.get_token()

        args = {}
        args['model'] = use_model.model_entity.name

        if use_funcs:
            tools = await self.ap.tool_mgr.generate_tools_for_openai(use_funcs)

            if tools:
                args['tools'] = tools

        # 设置此次请求中的messages
        messages = req_messages.copy()

        # 检查vision
        for msg in messages:
            if 'content' in msg and isinstance(msg['content'], list):
                for me in msg['content']:
                    if me['type'] == 'image_base64':
                        me['image_url'] = {'url': me['image_base64']}
                        me['type'] = 'image_url'
                        del me['image_base64']

        args['messages'] = messages

        if stream:
            current_content = ''
            args["stream"] = True
            chunk_idx = 0
            self.is_content = False
            tool_calls_map: dict[str, llm_entities.ToolCall] = {}
            pipeline_config = query.pipeline_config
            async for chunk in self._req_stream(args, extra_body=extra_args):
                # 处理流式消息
                delta_message = await self._make_msg_chunk(pipeline_config, chunk, chunk_idx)
                if delta_message.content:
                    current_content += delta_message.content
                    delta_message.content = current_content
                    # delta_message.all_content = current_content
                if delta_message.tool_calls:
                    for tool_call in delta_message.tool_calls:
                        if tool_call.id not in tool_calls_map:
                            tool_calls_map[tool_call.id] = llm_entities.ToolCall(
                                id=tool_call.id,
                                type=tool_call.type,
                                function=llm_entities.FunctionCall(
                                    name=tool_call.function.name if tool_call.function else '',
                                    arguments=''
                                ),
                            )
                        if tool_call.function and tool_call.function.arguments:
                            # 流式处理中，工具调用参数可能分多个chunk返回，需要追加而不是覆盖
                            tool_calls_map[tool_call.id].function.arguments += tool_call.function.arguments

                chunk_idx += 1
                chunk_choices = getattr(chunk, 'choices', None)
                if chunk_choices and getattr(chunk_choices[0], 'finish_reason', None):
                    delta_message.is_final = True
                    delta_message.content = current_content

                if chunk_idx % 64 == 0 or delta_message.is_final:
                    yield delta_message
