from __future__ import annotations

import openai
import typing

from . import chatcmpl
from .. import requester
import openai.types.chat.chat_completion as chat_completion
import re
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool


class JieKouAIChatCompletions(chatcmpl.OpenAIChatCompletions):
    """接口 AI ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://api.jiekou.ai/openai',
        'timeout': 120,
    }

    is_think: bool = False

    async def _make_msg(
        self,
        chat_completion: chat_completion.ChatCompletion,
        remove_think: bool,
    ) -> provider_message.Message:
        chatcmpl_message = chat_completion.choices[0].message.model_dump()
        # print(chatcmpl_message.keys(), chatcmpl_message.values())

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        reasoning_content = chatcmpl_message['reasoning_content'] if 'reasoning_content' in chatcmpl_message else None

        # deepseek的reasoner模型
        chatcmpl_message['content'] = await self._process_thinking_content(
            chatcmpl_message['content'], reasoning_content, remove_think
        )

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
            处理后的内容
        """
        if remove_think:
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        else:
            if reasoning_content is not None:
                content = '<think>\n' + reasoning_content + '\n</think>\n' + content
        return content

    async def _make_msg_chunk(
        self,
        delta: dict[str, typing.Any],
        idx: int,
    ) -> provider_message.MessageChunk:
        # 处理流式chunk和完整响应的差异
        # print(chat_completion.choices[0])

        # 确保 role 字段存在且不为 None
        if 'role' not in delta or delta['role'] is None:
            delta['role'] = 'assistant'

        reasoning_content = delta['reasoning_content'] if 'reasoning_content' in delta else None

        delta['content'] = '' if delta['content'] is None else delta['content']
        # print(reasoning_content)

        # deepseek的reasoner模型

        if reasoning_content is not None:
            delta['content'] += reasoning_content

        message = provider_message.MessageChunk(**delta)

        return message

    async def _closure_stream(
        self,
        query: pipeline_query.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
    ) -> provider_message.Message | typing.AsyncGenerator[provider_message.MessageChunk, None]:
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

        # tool_calls_map: dict[str, provider_message.ToolCall] = {}
        chunk_idx = 0
        thinking_started = False
        thinking_ended = False
        role = 'assistant'  # 默认角色
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
            # reasoning_content = delta.get('reasoning_content', '')

            if remove_think:
                if delta['content'] is not None:
                    if '<think>' in delta['content'] and not thinking_started and not thinking_ended:
                        thinking_started = True
                        continue
                    elif delta['content'] == r'</think>' and not thinking_ended:
                        thinking_ended = True
                        continue
                    elif thinking_ended and delta['content'] == '\n\n' and thinking_started:
                        thinking_started = False
                        continue
                    elif thinking_started and not thinking_ended:
                        continue

            # delta_tool_calls = None
            if delta.get('tool_calls'):
                for tool_call in delta['tool_calls']:
                    if tool_call['id'] and tool_call['function']['name']:
                        tool_id = tool_call['id']
                        tool_name = tool_call['function']['name']

                    if tool_call['id'] is None:
                        tool_call['id'] = tool_id
                    if tool_call['function']['name'] is None:
                        tool_call['function']['name'] = tool_name
                    if tool_call['function']['arguments'] is None:
                        tool_call['function']['arguments'] = ''
                    if tool_call['type'] is None:
                        tool_call['type'] = 'function'

            # 跳过空的第一个 chunk（只有 role 没有内容）
            if chunk_idx == 0 and not delta_content and not delta.get('tool_calls'):
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
