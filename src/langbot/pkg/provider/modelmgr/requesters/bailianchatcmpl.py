from __future__ import annotations

import typing
import dashscope
import openai

from . import modelscopechatcmpl
from .. import requester
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class BailianChatCompletions(modelscopechatcmpl.ModelScopeChatCompletions):
    """阿里云百炼大模型平台 ChatCompletion API 请求器"""

    client: openai.AsyncClient

    default_config: dict[str, typing.Any] = {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
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

        is_use_dashscope_call = False  # 是否使用阿里原生库调用
        is_enable_multi_model = True  # 是否支持多轮对话
        use_time_num = 0  # 模型已调用次数，防止存在多文件时重复调用
        use_time_ids = []  # 已调用的ID列表
        message_id = 0  # 记录消息序号

        for msg in messages:
            # print(msg)
            if 'content' in msg and isinstance(msg['content'], list):
                for me in msg['content']:
                    if me['type'] == 'image_base64':
                        me['image_url'] = {'url': me['image_base64']}
                        me['type'] = 'image_url'
                        del me['image_base64']
                    elif me['type'] == 'file_url' and '.' in me.get('file_name', ''):
                        # 1. 视频文件推理
                        # https://bailian.console.aliyun.com/?tab=doc#/doc/?type=model&url=2845871
                        file_type = me.get('file_name').lower().split('.')[-1]
                        if file_type in ['mp4', 'avi', 'mkv', 'mov', 'flv', 'wmv']:
                            me['type'] = 'video_url'
                            me['video_url'] = {'url': me['file_url']}
                            del me['file_url']
                            del me['file_name']
                            use_time_num += 1
                            use_time_ids.append(message_id)
                            is_enable_multi_model = False
                        # 2. 语音文件识别, 无法通过openai的audio字段传递，暂时不支持
                        # https://bailian.console.aliyun.com/?tab=doc#/doc/?type=model&url=2979031
                        elif file_type in [
                            'aac',
                            'amr',
                            'aiff',
                            'flac',
                            'm4a',
                            'mp3',
                            'mpeg',
                            'ogg',
                            'opus',
                            'wav',
                            'webm',
                            'wma',
                        ]:
                            me['audio'] = me['file_url']
                            me['type'] = 'audio'
                            del me['file_url']
                            del me['type']
                            del me['file_name']
                            is_use_dashscope_call = True
                            use_time_num += 1
                            use_time_ids.append(message_id)
                            is_enable_multi_model = False
            message_id += 1

        # 使用列表推导式，保留不在 use_time_ids[:-1] 中的元素，仅保留最后一个多媒体消息
        if not is_enable_multi_model and use_time_num > 1:
            messages = [msg for idx, msg in enumerate(messages) if idx not in use_time_ids[:-1]]

        if not is_enable_multi_model:
            messages = [msg for msg in messages if 'resp_message_id' not in msg]

        args['messages'] = messages
        args['stream'] = True

        # 流式处理状态
        # tool_calls_map: dict[str, provider_message.ToolCall] = {}
        chunk_idx = 0
        thinking_started = False
        thinking_ended = False
        role = 'assistant'  # 默认角色

        if is_use_dashscope_call:
            response = dashscope.MultiModalConversation.call(
                # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key = "sk-xxx"
                api_key=use_model.token_mgr.get_token(),
                model=use_model.model_entity.name,
                messages=messages,
                result_format='message',
                asr_options={
                    # "language": "zh", # 可选，若已知音频的语种，可通过该参数指定待识别语种，以提升识别准确率
                    'enable_lid': True,
                    'enable_itn': False,
                },
                stream=True,
            )
            content_length_list = []
            previous_length = 0  # 记录上一次的内容长度
            for res in response:
                chunk = res['output']
                # 解析 chunk 数据
                if hasattr(chunk, 'choices') and chunk.choices:
                    choice = chunk.choices[0]
                    delta_content = choice['message'].content[0]['text']
                    finish_reason = choice['finish_reason']
                    content_length_list.append(len(delta_content))
                else:
                    delta_content = ''
                    finish_reason = None

                # 跳过空的第一个 chunk（只有 role 没有内容）
                if chunk_idx == 0 and not delta_content:
                    chunk_idx += 1
                    continue

                # 检查 content_length_list 是否有足够的数据
                if len(content_length_list) >= 2:
                    now_content = delta_content[previous_length : content_length_list[-1]]
                    previous_length = content_length_list[-1]  # 更新上一次的长度
                else:
                    now_content = delta_content  # 第一次循环时直接使用 delta_content
                    previous_length = len(delta_content)  # 更新上一次的长度

                # 构建 MessageChunk - 只包含增量内容
                chunk_data = {
                    'role': role,
                    'content': now_content if now_content else None,
                    'is_final': bool(finish_reason) and finish_reason != 'null',
                }

                # 移除 None 值
                chunk_data = {k: v for k, v in chunk_data.items() if v is not None}
                yield provider_message.MessageChunk(**chunk_data)
                chunk_idx += 1
        else:
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

                # 处理工具调用增量
                if delta.get('tool_calls'):
                    for tool_call in delta['tool_calls']:
                        if tool_call['id'] != '':
                            tool_id = tool_call['id']
                        if tool_call['function']['name'] is not None:
                            tool_name = tool_call['function']['name']

                        if tool_call['type'] is None:
                            tool_call['type'] = 'function'
                        tool_call['id'] = tool_id
                        tool_call['function']['name'] = tool_name
                        tool_call['function']['arguments'] = (
                            '' if tool_call['function']['arguments'] is None else tool_call['function']['arguments']
                        )

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
                # return
