from __future__ import annotations

import typing

from . import chatcmpl

import uuid

from .. import requester
import langbot_plugin.api.entities.builtin.provider.message as provider_message
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool


class GeminiChatCompletions(chatcmpl.OpenAIChatCompletions):
    """Google Gemini API 请求器"""

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'timeout': 120,
    }

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
                    if tool_call['id'] == '' and tool_id == '':
                        tool_id = str(uuid.uuid4())
                    if tool_call['function']['name']:
                        tool_name = tool_call['function']['name']
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
