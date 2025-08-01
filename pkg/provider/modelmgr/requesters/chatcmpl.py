from __future__ import annotations

import asyncio
import typing

import openai
import openai.types.chat.chat_completion as chat_completion
import httpx

from .. import errors, requester
from ....core import entities as core_entities, app
from ... import entities as llm_entities
from ...tools import entities as tools_entities


class OpenAIChatCompletions(requester.LLMAPIRequester):
    """OpenAI ChatCompletion API 请求器"""

    client: openai.AsyncClient
    is_content: bool

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
        self.is_content = False

    async def _req(
        self,
        args: dict,
        extra_body: dict = {},
    ) -> chat_completion.ChatCompletion:
        return await self.client.chat.completions.create(**args, extra_body=extra_body)

    async def _req_stream(
        self,
        args: dict,
        extra_body: dict = {},
    ) -> chat_completion.ChatCompletion:
        async for chunk in await self.client.chat.completions.create(**args, extra_body=extra_body):
            yield chunk

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
        pipeline_config: dict[str, typing.Any] = {'trigger': {'misc': {'remove_think': False}}},
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.model_dump()
        # print(chatcmpl_message.keys(),chatcmpl_message.values())

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        reasoning_content = chatcmpl_message['reasoning_content'] if 'reasoning_content' in chatcmpl_message else None

        # deepseek的reasoner模型
        if pipeline_config['trigger'].get('misc', '').get('remove_think'):
            pass
        else:
            if reasoning_content is not None:
                chatcmpl_message['content'] = (
                    '<think>\n' + reasoning_content + '\n</think>\n' + chatcmpl_message['content']
                )

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
        # print(delta.keys(),delta.values())
        if 'role' not in delta or delta['role'] is None:
            delta['role'] = 'assistant'

        reasoning_content = delta['reasoning_content'] if 'reasoning_content' in delta else None

        delta['content'] = '' if delta['content'] is None else delta['content']
        # print(reasoning_content)

        # deepseek的reasoner模型
        if pipeline_config['trigger'].get('misc', '').get('remove_think'):
            if reasoning_content is not None:
                pass
            else:
                delta['content'] = delta['content']
        else:
            if reasoning_content is not None and idx == 0:
                delta['content'] += f'<think>\n{reasoning_content}'
            elif reasoning_content is None:
                if self.is_content:
                    delta['content'] = delta['content']
                else:
                    delta['content'] = f'\n<think>\n\n{delta["content"]}'
                    self.is_content = True
            else:
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
    ) ->llm_entities.MessageChunk:
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
            args['stream'] = True
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
                                    name=tool_call.function.name if tool_call.function else '', arguments=''
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
                # return

    async def _closure(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[tools_entities.LLMFunction] = None,
        stream: bool = False,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
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

        # 发送请求

        resp = await self._req(args, extra_body=extra_args)
        # 处理请求结果
        pipeline_config = query.pipeline_config
        message = await self._make_msg(resp, pipeline_config)

        return message

    async def invoke_llm(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.Message:
        req_messages = []  # req_messages 仅用于类内，外部同步由 query.messages 进行
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')
            if isinstance(content, list):
                # 检查 content 列表中是否每个部分都是文本
                if all(isinstance(part, dict) and part.get('type') == 'text' for part in content):
                    # 将所有文本部分合并为一个字符串
                    msg_dict['content'] = '\n'.join(part['text'] for part in content)
            req_messages.append(msg_dict)

        try:
            msg = await self._closure(
                query=query,
                req_messages=req_messages,
                use_model=model,
                use_funcs=funcs,
                extra_args=extra_args,
            )
            return msg
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

    async def invoke_llm_stream(
        self,
        query: core_entities.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[llm_entities.Message],
        funcs: typing.List[tools_entities.LLMFunction] = None,
        stream: bool = False,
        extra_args: dict[str, typing.Any] = {},
    ) -> llm_entities.MessageChunk:
        req_messages = []  # req_messages 仅用于类内，外部同步由 query.messages 进行
        for m in messages:
            msg_dict = m.dict(exclude_none=True)
            content = msg_dict.get('content')
            if isinstance(content, list):
                # 检查 content 列表中是否每个部分都是文本
                if all(isinstance(part, dict) and part.get('type') == 'text' for part in content):
                    # 将所有文本部分合并为一个字符串
                    msg_dict['content'] = '\n'.join(part['text'] for part in content)
            req_messages.append(msg_dict)

        try:
            async for item in self._closure_stream(
                query=query,
                req_messages=req_messages,
                use_model=model,
                use_funcs=funcs,
                stream=stream,
                extra_args=extra_args,
            ):
                yield item

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
