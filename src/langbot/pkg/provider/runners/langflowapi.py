from __future__ import annotations

import typing
import json
import httpx
import uuid
import traceback

from .. import runner
from ...core import app
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


@runner.runner_class('langflow-api')
class LangflowAPIRunner(runner.RequestRunner):
    """Langflow API 对话请求器"""

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config

    async def _build_request_payload(self, query: pipeline_query.Query) -> dict:
        """构建请求负载

        Args:
            query: 用户查询对象

        Returns:
            dict: 请求负载
        """
        # 获取用户消息文本
        user_message_text = ''
        if isinstance(query.user_message.content, str):
            user_message_text = query.user_message.content
        elif isinstance(query.user_message.content, list):
            for item in query.user_message.content:
                if item.type == 'text':
                    user_message_text += item.text

        # 从配置中获取 input_type 和 output_type，如果未配置则使用默认值
        input_type = self.pipeline_config['ai']['langflow-api'].get('input_type', 'chat')
        output_type = self.pipeline_config['ai']['langflow-api'].get('output_type', 'chat')

        # 构建基本负载
        payload = {
            'output_type': output_type,
            'input_type': input_type,
            'input_value': user_message_text,
            'session_id': str(uuid.uuid4()),
        }

        # 如果配置中有tweaks，则添加到负载中
        tweaks = json.loads(self.pipeline_config['ai']['langflow-api'].get('tweaks'))
        if tweaks:
            payload['tweaks'] = tweaks

        return payload

    async def run(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message | provider_message.MessageChunk, None]:
        """运行请求

        Args:
            query: 用户查询对象

        Yields:
            Message: 回复消息
        """
        # 检查是否支持流式输出
        is_stream = False
        try:
            is_stream = await query.adapter.is_stream_output_supported()
        except AttributeError:
            is_stream = False

        # 从配置中获取API参数
        base_url = self.pipeline_config['ai']['langflow-api']['base-url']
        api_key = self.pipeline_config['ai']['langflow-api']['api-key']
        flow_id = self.pipeline_config['ai']['langflow-api']['flow-id']

        # 构建API URL
        url = f'{base_url.rstrip("/")}/api/v1/run/{flow_id}'

        # 构建请求负载
        payload = await self._build_request_payload(query)

        # 设置请求头
        headers = {'Content-Type': 'application/json', 'x-api-key': api_key}

        # 发送请求
        async with httpx.AsyncClient() as client:
            if is_stream:
                # 流式请求
                async with client.stream('POST', url, json=payload, headers=headers, timeout=120.0) as response:
                    print(response)
                    response.raise_for_status()

                    accumulated_content = ''
                    message_count = 0

                    async for line in response.aiter_lines():
                        data_str = line

                        if data_str.startswith('data: '):
                            data_str = data_str[6:]  # 移除 "data: " 前缀

                        try:
                            data = json.loads(data_str)

                            # 提取消息内容
                            message_text = ''
                            if 'outputs' in data and len(data['outputs']) > 0:
                                output = data['outputs'][0]
                                if 'outputs' in output and len(output['outputs']) > 0:
                                    inner_output = output['outputs'][0]
                                    if 'outputs' in inner_output and 'message' in inner_output['outputs']:
                                        message_data = inner_output['outputs']['message']
                                        if 'message' in message_data:
                                            message_text = message_data['message']

                            # 如果没有找到消息，尝试其他可能的路径
                            if not message_text and 'messages' in data:
                                messages = data['messages']
                                if messages and len(messages) > 0:
                                    message_text = messages[0].get('message', '')

                            if message_text:
                                # 更新累积内容
                                accumulated_content = message_text
                                message_count += 1

                                # 每8条消息或有新内容时生成一个chunk
                                if message_count % 8 == 0 or len(message_text) > 0:
                                    yield provider_message.MessageChunk(
                                        role='assistant', content=accumulated_content, is_final=False
                                    )
                        except json.JSONDecodeError:
                            # 如果不是JSON，跳过这一行
                            traceback.print_exc()
                            continue

                    # 发送最终消息
                    yield provider_message.MessageChunk(role='assistant', content=accumulated_content, is_final=True)
            else:
                # 非流式请求
                response = await client.post(url, json=payload, headers=headers, timeout=120.0)
                response.raise_for_status()

                # 解析响应
                response_data = response.json()

                # 提取消息内容
                # 根据Langflow API文档，响应结构可能在outputs[0].outputs[0].outputs.message.message中
                message_text = ''
                if 'outputs' in response_data and len(response_data['outputs']) > 0:
                    output = response_data['outputs'][0]
                    if 'outputs' in output and len(output['outputs']) > 0:
                        inner_output = output['outputs'][0]
                        if 'outputs' in inner_output and 'message' in inner_output['outputs']:
                            message_data = inner_output['outputs']['message']
                            if 'message' in message_data:
                                message_text = message_data['message']

                # 如果没有找到消息，尝试其他可能的路径
                if not message_text and 'messages' in response_data:
                    messages = response_data['messages']
                    if messages and len(messages) > 0:
                        message_text = messages[0].get('message', '')

                # 如果仍然没有找到消息，返回完整响应的字符串表示
                if not message_text:
                    message_text = json.dumps(response_data, ensure_ascii=False, indent=2)

                # 生成回复消息
                if is_stream:
                    yield provider_message.MessageChunk(role='assistant', content=message_text, is_final=True)
                else:
                    reply_message = provider_message.Message(role='assistant', content=message_text)
                    yield reply_message
