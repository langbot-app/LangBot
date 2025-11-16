from __future__ import annotations

import typing
import json
import base64
import tempfile
import os

from tboxsdk.tbox import TboxClient
from tboxsdk.model.file import File, FileType

from .. import runner
from ...core import app
from ...utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import langbot_plugin.api.entities.builtin.provider.message as provider_message


class TboxAPIError(Exception):
    """TBox API 请求失败"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


@runner.runner_class('tbox-app-api')
class TboxAPIRunner(runner.RequestRunner):
    "蚂蚁百宝箱API对话请求器"

    # 运行器内部使用的配置
    app_id: str  # 蚂蚁百宝箱平台中的应用ID
    api_key: str  # 在蚂蚁百宝箱平台中申请的令牌

    def __init__(self, ap: app.Application, pipeline_config: dict):
        """初始化"""
        self.ap = ap
        self.pipeline_config = pipeline_config

        # 初始化Tbox 参数配置
        self.app_id = self.pipeline_config['ai']['tbox-app-api']['app-id']
        self.api_key = self.pipeline_config['ai']['tbox-app-api']['api-key']

        # 初始化Tbox client
        self.tbox_client = TboxClient(authorization=self.api_key)

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[str]]:
        """预处理用户消息，提取纯文本，并将图片上传到 Tbox 服务

        Returns:
            tuple[str, list[str]]: 纯文本和图片的 Tbox 文件ID
        """
        plain_text = ''
        image_ids = []

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    # 创建临时文件
                    file_bytes = base64.b64decode(image_b64)
                    try:
                        with tempfile.NamedTemporaryFile(suffix=f'.{image_format}', delete=False) as tmp_file:
                            tmp_file.write(file_bytes)
                            tmp_file_path = tmp_file.name
                        file_upload_resp = self.tbox_client.upload_file(tmp_file_path)
                        image_id = file_upload_resp.get('data', '')
                        image_ids.append(image_id)
                    finally:
                        # 清理临时文件
                        if os.path.exists(tmp_file_path):
                            os.unlink(tmp_file_path)
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        return plain_text, image_ids

    async def _agent_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """TBox 智能体对话请求"""

        plain_text, image_ids = await self._preprocess_user_message(query)
        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')

        try:
            is_stream = await query.adapter.is_stream_output_supported()
        except AttributeError:
            is_stream = False

        # 获取Tbox的conversation_id
        conversation_id = query.session.using_conversation.uuid or None

        files = None
        if image_ids:
            files = [File(file_id=image_id, type=FileType.IMAGE) for image_id in image_ids]

        # 发送对话请求
        response = self.tbox_client.chat(
            app_id=self.app_id,  # Tbox中智能体应用的ID
            user_id=query.bot_uuid,  # 用户ID
            query=plain_text,  # 用户输入的文本信息
            stream=is_stream,  # 是否流式输出
            conversation_id=conversation_id,  # 会话ID，为None时Tbox会自动创建一个新会话
            files=files,  # 图片内容
        )

        if is_stream:
            # 解析Tbox流式输出内容，并发送给上游
            for chunk in self._process_stream_message(response, query, remove_think):
                yield chunk
        else:
            message = self._process_non_stream_message(response, query, remove_think)
            yield provider_message.Message(
                role='assistant',
                content=message,
            )

    def _process_non_stream_message(self, response: typing.Dict, query: pipeline_query.Query, remove_think: bool):
        if response.get('errorCode') != '0':
            raise TboxAPIError(f'Tbox API 请求失败: {response.get("errorMsg", "")}')
        payload = response.get('data', {})
        conversation_id = payload.get('conversationId', '')
        query.session.using_conversation.uuid = conversation_id
        thinking_content = payload.get('reasoningContent', [])
        result = ''
        if thinking_content and not remove_think:
            result += f'<think>\n{thinking_content[0].get("text", "")}\n</think>\n'
        content = payload.get('result', [])
        if content:
            result += content[0].get('chunk', '')
        return result

    def _process_stream_message(
        self, response: typing.Generator[dict], query: pipeline_query.Query, remove_think: bool
    ):
        idx_msg = 0
        pending_content = ''
        conversation_id = None
        think_start = False
        think_end = False
        for chunk in response:
            if chunk.get('type', '') == 'chunk':
                """
                Tbox返回的消息内容chunk结构
                {'lane': 'default', 'payload': {'conversationId': '20250918tBI947065406', 'messageId': '20250918TB1f53230954', 'text': '️'}, 'type': 'chunk'}
                """
                # 如果包含思考过程，拼接</think>
                if think_start and not think_end:
                    pending_content += '\n</think>\n'
                    think_end = True

                payload = chunk.get('payload', {})
                if not conversation_id:
                    conversation_id = payload.get('conversationId')
                    query.session.using_conversation.uuid = conversation_id
                if payload.get('text'):
                    idx_msg += 1
                    pending_content += payload.get('text')
            elif chunk.get('type', '') == 'thinking' and not remove_think:
                """
                Tbox返回的思考过程chunk结构
                {'payload': '{"ext_data":{"text":"日期"},"event":"flow.node.llm.thinking","entity":{"node_type":"text-completion","execute_id":"6","group_id":0,"parent_execute_id":"6","node_name":"模型推理","node_id":"TC_5u6gl0"}}', 'type': 'thinking'}
                """
                payload = json.loads(chunk.get('payload', '{}'))
                if payload.get('ext_data', {}).get('text'):
                    idx_msg += 1
                    content = payload.get('ext_data', {}).get('text')
                    if not think_start:
                        think_start = True
                        pending_content += f'<think>\n{content}'
                    else:
                        pending_content += content
            elif chunk.get('type', '') == 'error':
                raise TboxAPIError(
                    f'Tbox API 请求失败: status_code={chunk.get("status_code")} message={chunk.get("message")} request_id={chunk.get("request_id")} '
                )

            if idx_msg % 8 == 0:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=pending_content,
                    is_final=False,
                )

        # Tbox不返回END事件，默认发一个最终消息
        yield provider_message.MessageChunk(
            role='assistant',
            content=pending_content,
            is_final=True,
        )

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行"""
        msg_seq = 0
        async for msg in self._agent_messages(query):
            if isinstance(msg, provider_message.MessageChunk):
                msg_seq += 1
                msg.msg_sequence = msg_seq
            yield msg
