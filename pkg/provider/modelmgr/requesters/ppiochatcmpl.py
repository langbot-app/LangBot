from __future__ import annotations

import openai
import typing

from . import chatcmpl
import openai.types.chat.chat_completion as chat_completion
from .. import requester
from ....core import entities as core_entities
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
        remove_think: bool,
    ) -> llm_entities.Message:
        chatcmpl_message = chat_completion.choices[0].message.model_dump()
        # print(chatcmpl_message.keys(), chatcmpl_message.values())

        # 确保 role 字段存在且不为 None
        if 'role' not in chatcmpl_message or chatcmpl_message['role'] is None:
            chatcmpl_message['role'] = 'assistant'

        reasoning_content = chatcmpl_message['reasoning_content'] if 'reasoning_content' in chatcmpl_message else None

        # deepseek的reasoner模型
        chatcmpl_message["content"] = await self._process_thinking_content(
            chatcmpl_message['content'],reasoning_content,remove_think)

        # 移除 reasoning_content 字段，避免传递给 Message
        if 'reasoning_content' in chatcmpl_message:
            del chatcmpl_message['reasoning_content']


        message = llm_entities.Message(**chatcmpl_message)

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
            content = re.sub(
                r'<think>.*?</think>', '', content, flags=re.DOTALL
            )
        else:
            if reasoning_content is not None:
                content = (
                    '<think>\n' + reasoning_content + '\n</think>\n' + content
                )
        return content

    async def _make_msg_chunk(
            self,
            delta: dict[str, typing.Any],
            idx: int,
    ) -> llm_entities.MessageChunk:
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

        message = llm_entities.MessageChunk(**delta)

        return message

    async def _closure_stream(
        self,
        query: core_entities.Query,
        req_messages: list[dict],
        use_model: requester.RuntimeLLMModel,
        use_funcs: list[tools_entities.LLMFunction] = None,
        extra_args: dict[str, typing.Any] = {},
        remove_think: bool = False,
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
        args['stream'] = True

        tool_calls_map: dict[str, llm_entities.ToolCall] = {}
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


            delta_tool_calls = None
            if delta.get('tool_calls'):
                delta_tool_calls = []
                for tool_call in delta['tool_calls']:
                    tc_id = tool_call.get('id')
                    if tc_id:
                        if tc_id not in tool_calls_map:
                            # 新的工具调用
                            tool_calls_map[tc_id] = llm_entities.ToolCall(
                                id=tc_id,
                                type=tool_call.get('type', 'function'),
                                function=llm_entities.FunctionCall(
                                    name=tool_call.get('function', {}).get('name', ''),
                                    arguments=tool_call.get('function', {}).get('arguments', ''),
                                ),
                            )
                            delta_tool_calls.append(tool_calls_map[tc_id])
                        else:
                            # 追加函数参数
                            func_args = tool_call.get('function', {}).get('arguments', '')
                            if func_args:
                                tool_calls_map[tc_id].function.arguments += func_args
                                # 返回更新后的完整工具调用
                                delta_tool_calls.append(tool_calls_map[tc_id])

            # 跳过空的第一个 chunk（只有 role 没有内容）
            if chunk_idx == 0 and not delta_content  and not delta.get('tool_calls'):
                chunk_idx += 1
                continue

                # 构建 MessageChunk - 只包含增量内容
            chunk_data = {
                'role': role,
                'content': delta_content if delta_content else None,
                'tool_calls': delta_tool_calls if delta_tool_calls else None,
                'is_final': bool(finish_reason),
            }

            # 移除 None 值
            chunk_data = {k: v for k, v in chunk_data.items() if v is not None}

            yield llm_entities.MessageChunk(**chunk_data)
            chunk_idx += 1
