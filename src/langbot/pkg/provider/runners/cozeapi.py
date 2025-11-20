from __future__ import annotations

import typing
import json
import base64

from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.coze_server_api.client import AsyncCozeAPIClient


@runner.runner_class('coze-api')
class CozeAPIRunner(runner.RequestRunner):
    """Coze API 对话请求器"""

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.pipeline_config = pipeline_config
        self.ap = ap
        self.agent_token = pipeline_config['ai']['coze-api']['api-key']
        self.bot_id = pipeline_config['ai']['coze-api'].get('bot-id')
        self.chat_timeout = pipeline_config['ai']['coze-api'].get('timeout')
        self.auto_save_history = pipeline_config['ai']['coze-api'].get('auto_save_history')
        self.api_base = pipeline_config['ai']['coze-api'].get('api-base')

        self.coze = AsyncCozeAPIClient(self.agent_token, self.api_base)

    def _process_thinking_content(
        self,
        content: str,
    ) -> tuple[str, str]:
        """处理思维链内容

        Args:
            content: 原始内容
        Returns:
            (处理后的内容, 提取的思维链内容)
        """
        remove_think = self.pipeline_config.get('output', {}).get('misc', {}).get('remove-think', False)
        thinking_content = ''
        # 从 content 中提取 <think> 标签内容
        if content and '<think>' in content and '</think>' in content:
            import re

            think_pattern = r'<think>(.*?)</think>'
            think_matches = re.findall(think_pattern, content, re.DOTALL)
            if think_matches:
                thinking_content = '\n'.join(think_matches)
                # 移除 content 中的 <think> 标签
                content = re.sub(think_pattern, '', content, flags=re.DOTALL).strip()

        # 根据 remove_think 参数决定是否保留思维链
        if remove_think:
            return content, ''
        else:
            # 如果有思维链内容，将其以 <think> 格式添加到 content 开头
            if thinking_content:
                content = f'<think>\n{thinking_content}\n</think>\n{content}'.strip()
            return content, thinking_content

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> list[dict]:
        """预处理用户消息，转换为Coze消息格式

        Returns:
            list[dict]: Coze消息列表
        """
        messages = []

        if isinstance(query.user_message.content, list):
            # 多模态消息处理
            content_parts = []

            for ce in query.user_message.content:
                if ce.type == 'text':
                    content_parts.append({'type': 'text', 'text': ce.text})
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    file_bytes = base64.b64decode(image_b64)
                    file_id = await self._get_file_id(file_bytes)
                    content_parts.append({'type': 'image', 'file_id': file_id})
                elif ce.type == 'file':
                    # 处理文件，上传到Coze
                    file_id = await self._get_file_id(ce.file)
                    content_parts.append({'type': 'file', 'file_id': file_id})

            # 创建多模态消息
            if content_parts:
                messages.append(
                    {
                        'role': 'user',
                        'content': json.dumps(content_parts),
                        'content_type': 'object_string',
                        'meta_data': None,
                    }
                )

        elif isinstance(query.user_message.content, str):
            # 纯文本消息
            messages.append(
                {'role': 'user', 'content': query.user_message.content, 'content_type': 'text', 'meta_data': None}
            )

        return messages

    async def _get_file_id(self, file) -> str:
        """上传文件到Coze服务
        Args:
            file: 文件
        Returns:
            str: 文件ID
        """
        file_id = await self.coze.upload(file=file)
        return file_id

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手（非流式）

        注意：由于cozepy没有提供非流式API，这里使用流式API并在结束后一次性返回完整内容
        """
        user_id = f'{query.launcher_type.value}_{query.launcher_id}'

        # 预处理用户消息
        additional_messages = await self._preprocess_user_message(query)

        # 获取会话ID
        conversation_id = None

        # 收集完整内容
        full_content = ''
        full_reasoning = ''

        try:
            # 调用Coze API流式接口
            async for chunk in self.coze.chat_messages(
                bot_id=self.bot_id,
                user_id=user_id,
                additional_messages=additional_messages,
                conversation_id=conversation_id,
                timeout=self.chat_timeout,
                auto_save_history=self.auto_save_history,
                stream=True,
            ):
                self.ap.logger.debug(f'coze-chat-stream: {chunk}')

                event_type = chunk.get('event')
                data = chunk.get('data', {})
                # Removed debug print statement to avoid cluttering logs in production

                if event_type == 'conversation.message.delta':
                    # 收集内容
                    if 'content' in data:
                        full_content += data.get('content', '')

                    # 收集推理内容（如果有）
                    if 'reasoning_content' in data:
                        full_reasoning += data.get('reasoning_content', '')

                elif event_type.split('.')[-1] == 'done':  # 本地部署coze时，结束event不为done
                    # 保存会话ID
                    if 'conversation_id' in data:
                        conversation_id = data.get('conversation_id')

                elif event_type == 'error':
                    # 处理错误
                    error_msg = f'Coze API错误: {data.get("message", "未知错误")}'
                    yield provider_message.Message(
                        role='assistant',
                        content=error_msg,
                    )
                    return

            # 处理思维链内容
            content, thinking_content = self._process_thinking_content(full_content)
            if full_reasoning:
                remove_think = self.pipeline_config.get('output', {}).get('misc', {}).get('remove-think', False)
                if not remove_think:
                    content = f'<think>\n{full_reasoning}\n</think>\n{content}'.strip()

            # 一次性返回完整内容
            yield provider_message.Message(
                role='assistant',
                content=content,
            )

            # 保存会话ID
            if conversation_id and query.session.using_conversation:
                query.session.using_conversation.uuid = conversation_id

        except Exception as e:
            self.ap.logger.error(f'Coze API错误: {str(e)}')
            yield provider_message.Message(
                role='assistant',
                content=f'Coze API调用失败: {str(e)}',
            )

    async def _chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手（流式）"""
        user_id = f'{query.launcher_type.value}_{query.launcher_id}'

        # 预处理用户消息
        additional_messages = await self._preprocess_user_message(query)

        # 获取会话ID
        conversation_id = None

        start_reasoning = False
        stop_reasoning = False
        message_idx = 1
        is_final = False
        full_content = ''
        remove_think = self.pipeline_config.get('output', {}).get('misc', {}).get('remove-think', False)

        try:
            # 调用Coze API流式接口
            async for chunk in self.coze.chat_messages(
                bot_id=self.bot_id,
                user_id=user_id,
                additional_messages=additional_messages,
                conversation_id=conversation_id,
                timeout=self.chat_timeout,
                auto_save_history=self.auto_save_history,
                stream=True,
            ):
                self.ap.logger.debug(f'coze-chat-stream-chunk: {chunk}')

                event_type = chunk.get('event')
                data = chunk.get('data', {})
                content = ''

                if event_type == 'conversation.message.delta':
                    message_idx += 1
                    # 处理内容增量
                    if 'reasoning_content' in data and not remove_think:
                        reasoning_content = data.get('reasoning_content', '')
                        if reasoning_content and not start_reasoning:
                            content = '<think/>\n'
                            start_reasoning = True
                        content += reasoning_content

                    if 'content' in data:
                        if data.get('content', ''):
                            content += data.get('content', '')
                            if not stop_reasoning and start_reasoning:
                                content = f'</think>\n{content}'
                                stop_reasoning = True

                elif event_type.split('.')[-1] == 'done':  # 本地部署coze时，结束event不为done
                    # 保存会话ID
                    if 'conversation_id' in data:
                        conversation_id = data.get('conversation_id')
                        if query.session.using_conversation:
                            query.session.using_conversation.uuid = conversation_id
                    is_final = True

                elif event_type == 'error':
                    # 处理错误
                    error_msg = f'Coze API错误: {data.get("message", "未知错误")}'
                    yield provider_message.MessageChunk(role='assistant', content=error_msg, finish_reason='error')
                    return
                full_content += content
                if message_idx % 8 == 0 or is_final:
                    if full_content:
                        yield provider_message.MessageChunk(role='assistant', content=full_content, is_final=is_final)

        except Exception as e:
            self.ap.logger.error(f'Coze API流式调用错误: {str(e)}')
            yield provider_message.MessageChunk(
                role='assistant', content=f'Coze API流式调用失败: {str(e)}', finish_reason='error'
            )

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行"""
        msg_seq = 0
        if await query.adapter.is_stream_output_supported():
            async for msg in self._chat_messages_chunk(query):
                if isinstance(msg, provider_message.MessageChunk):
                    msg_seq += 1
                    msg.msg_sequence = msg_seq
                yield msg
        else:
            async for msg in self._chat_messages(query):
                yield msg
