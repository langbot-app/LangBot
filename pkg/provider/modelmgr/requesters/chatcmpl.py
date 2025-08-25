from __future__ import annotations

import asyncio
import typing

import openai
import openai.types.chat.chat_completion as chat_completion
import httpx

from .. import errors, requester
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class OpenAIChatCompletions(requester.ProviderAPIRequester):
    """OpenAI ChatCompletion API 请求器"""

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
    ):
        async for chunk in await self.client.chat.completions.create(**args, extra_body=extra_body):
            yield chunk

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
        remove_think: bool = False,
    ) -> provider_message.Message:
        chatcmpl_message = chat_completion.choices[0].message.model_dump()

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        # 处理思维链
        content = chatcmpl_message.get('content', '')
        reasoning_content = chatcmpl_message.get('reasoning_content', None)

        processed_content, _ = await self._process_thinking_content(
            content=content, reasoning_content=reasoning_content, remove_think=remove_think
        )

        chatcmpl_message['content'] = processed_content

        # 移除 reasoning_content 字段，避免传递给 Message
        if 'reasoning_content' in chatcmpl_message:
            del chatcmpl_message['reasoning_content']

        message = provider_message.Message(**chatcmpl_message)

        return message

    async def _process_thinking_content(
        self,
        content: str,
        reasoning_content: str = None,
        remove_think: bool = False,
    ) -> tuple[str, str]:
        """处理思维链内容

        Args:
            content: 原始内容
            reasoning_content: reasoning_content 字段内容
            remove_think: 是否移除思维链

        Returns:
            (处理后的内容, 提取的思维链内容)
        """
        thinking_content = ''

        # 1. 从 reasoning_content 提取思维链
        if reasoning_content:
            thinking_content = reasoning_content

        # 2. 从 content 中提取 <think> 标签内容
        if content and '<think>' in content and '</think>' in content:
            import re

            think_pattern = r'<think>(.*?)</think>'
            think_matches = re.findall(think_pattern, content, re.DOTALL)
            if think_matches:
                # 如果已有 reasoning_content，则追加
                if thinking_content:
                    thinking_content += '\n' + '\n'.join(think_matches)
                else:
                    thinking_content = '\n'.join(think_matches)
                # 移除 content 中的 <think> 标签
                content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()

        # 3. 根据 remove_think 参数决定是否保留思维链
        if remove_think:
            return content, ''
        else:
            # 如果有思维链内容，将其以 <think> 格式添加到 content 开头
            if thinking_content:
                content = f'<think>\n{thinking_content}\n</think>\n{content}'.strip()
            return content, thinking_content

    async def _closure_stream(
        self,
        query: pipeline_query.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
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
        args['stream'] = True

        # 流式处理状态
        # tool_calls_map: dict[str, provider_message.ToolCall] = {}
        chunk_idx = 0
        thinking_started = False
        thinking_ended = False
        role = 'assistant'  # 默认角色
        tool_id = ''
        tool_name = ''
        # accumulated_reasoning = ''  # 仅用于判断何时结束思维链

        async for chunk in self._req_stream(args, extra_body=extra_args):
            # 解析 chunk 数据

            if hasattr(chunk, 'choices') and chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta.model_dump() if hasattr(choice, 'delta') else {}

                finish_reason = getattr(choice, 'finish_reason', None)
            else:
                delta = {}
                finish_reason = None
            # 从第一个 chunk 获取 role，后续使用这个 role
            if 'role' in delta and delta['role']:
                role = delta['role']

            # 获取增量内容
            delta_content = delta.get('content', '')
            reasoning_content = delta.get('reasoning_content', '')

            # 处理 reasoning_content
            if reasoning_content:
                # accumulated_reasoning += reasoning_content
                # 如果设置了 remove_think，跳过 reasoning_content
                if remove_think:
                    chunk_idx += 1
                    continue

                # 第一次出现 reasoning_content，添加 <think> 开始标签
                if not thinking_started:
                    thinking_started = True
                    delta_content = '<think>\n' + reasoning_content
                else:
                    # 继续输出 reasoning_content
                    delta_content = reasoning_content
            elif thinking_started and not thinking_ended and delta_content:
                # reasoning_content 结束，normal content 开始，添加 </think> 结束标签
                thinking_ended = True
                delta_content = '\n</think>\n' + delta_content

            # 处理 content 中已有的 <think> 标签（如果需要移除）
            # if delta_content and remove_think and '<think>' in delta_content:
            #     import re
            #
            #     # 移除 <think> 标签及其内容
            #     delta_content = re.sub(r'<think>.*?</think>', '', delta_content, flags=re.DOTALL)

            # 处理工具调用增量
            # delta_tool_calls = None
            if delta.get('tool_calls'):
                for tool_call in delta['tool_calls']:
                    if tool_call['id'] and tool_call['function']['name']:
                        tool_id = tool_call['id']
                        tool_name = tool_call['function']['name']
                    else:
                        tool_call['id'] = tool_id
                        tool_call['function']['name'] = tool_name
                    if tool_call['type'] is None:
                        tool_call['type'] = 'function'

            # 跳过空的第一个 chunk（只有 role 没有内容）
            if chunk_idx == 0 and not delta_content and not reasoning_content and not delta.get('tool_calls'):
                chunk_idx += 1
                continue
            # 构建 MessageChunk - 只包含增量内容
            chunk_data = {
                'role': role,
                'content': delta_content if delta_content else None,
                'tool_calls': delta.get('tool_calls'),
                'is_final': bool(finish_reason),
            }

            # 移除 None 值
            chunk_data = {k: v for k, v in chunk_data.items() if v is not None}

            yield provider_message.MessageChunk(**chunk_data)
            chunk_idx += 1

    async def _closure(
        self,
        query: pipeline_query.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
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
        message = await self._make_msg(resp, remove_think)

        return message

    async def invoke_llm(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message:
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
                remove_think=remove_think,
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

    async def invoke_embedding(
        self,
        model: requester.RuntimeEmbeddingModel,
        input_text: list[str],
        extra_args: dict[str, typing.Any] = {},
    ) -> list[list[float]]:
        """调用 Embedding API"""
        self.client.api_key = model.token_mgr.get_token()

        args = {
            'model': model.model_entity.name,
            'input': input_text,
        }

        if model.model_entity.extra_args:
            args.update(model.model_entity.extra_args)

        args.update(extra_args)

        try:
            resp = await self.client.embeddings.create(**args)

            return [d.embedding for d in resp.data]
        except asyncio.TimeoutError:
            raise errors.RequesterError('请求超时')
        except openai.BadRequestError as e:
            raise errors.RequesterError(f'请求参数错误: {e.message}')

    async def invoke_llm_stream(
        self,
        query: pipeline_query.Query,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.MessageChunk:
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
                extra_args=extra_args,
                remove_think=remove_think,
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
