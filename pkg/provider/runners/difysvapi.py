from __future__ import annotations

import typing
import json
import uuid
import re
import base64


from .. import runner
from ...core import app, entities as core_entities
from .. import entities as llm_entities
from ...utils import image

from libs.dify_service_api.v1 import client, errors


@runner.runner_class('dify-service-api')
class DifyServiceAPIRunner(runner.RequestRunner):
    """Dify Service API 对话请求器"""

    dify_client: client.AsyncDifyServiceClient

    def __init__(self, ap: app.Application, pipeline_config: dict):
        self.ap = ap
        self.pipeline_config = pipeline_config

        valid_app_types = ['chat', 'agent', 'workflow']
        if self.pipeline_config['ai']['dify-service-api']['app-type'] not in valid_app_types:
            raise errors.DifyAPIError(
                f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
            )

        api_key = self.pipeline_config['ai']['dify-service-api']['api-key']

        self.dify_client = client.AsyncDifyServiceClient(
            api_key=api_key,
            base_url=self.pipeline_config['ai']['dify-service-api']['base-url'],
        )

    def _try_convert_thinking(self, resp_text: str) -> str:
        """尝试转换 Dify 的思考提示"""
        if not resp_text.startswith(
            '<details style="color:gray;background-color: #f8f8f8;padding: 8px;border-radius: 4px;" open> <summary> Thinking... </summary>'
        ):
            return resp_text

        if self.pipeline_config['ai']['dify-service-api']['thinking-convert'] == 'original':
            return resp_text

        if self.pipeline_config['ai']['dify-service-api']['thinking-convert'] == 'remove':
            return re.sub(
                r'<details style="color:gray;background-color: #f8f8f8;padding: 8px;border-radius: 4px;" open> <summary> Thinking... </summary>.*?</details>',
                '',
                resp_text,
                flags=re.DOTALL,
            )

        if self.pipeline_config['ai']['dify-service-api']['thinking-convert'] == 'plain':
            pattern = r'<details style="color:gray;background-color: #f8f8f8;padding: 8px;border-radius: 4px;" open> <summary> Thinking... </summary>(.*?)</details>'
            thinking_text = re.search(pattern, resp_text, flags=re.DOTALL)
            content_text = re.sub(pattern, '', resp_text, flags=re.DOTALL)
            return f'<think>{thinking_text.group(1)}</think>\n{content_text}'

    async def _preprocess_user_message(self, query: core_entities.Query) -> tuple[str, list[str]]:
        """预处理用户消息，提取纯文本，并将图片上传到 Dify 服务

        Returns:
            tuple[str, list[str]]: 纯文本和图片的 Dify 服务图片 ID
        """
        plain_text = ''
        image_ids = []

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    file_bytes = base64.b64decode(image_b64)
                    file = ('img.png', file_bytes, f'image/{image_format}')
                    file_upload_resp = await self.dify_client.upload_file(
                        file,
                        f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                    )
                    image_id = file_upload_resp['id']
                    image_ids.append(image_id)
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        return plain_text, image_ids

    async def _chat_messages(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''

        plain_text, image_ids = await self._preprocess_user_message(query)

        files = [
            {
                'type': 'image',
                'transfer_method': 'local_file',
                'upload_file_id': image_id,
            }
            for image_id in image_ids
        ]

        mode = 'basic'  # 标记是基础编排还是工作流编排

        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

            if chunk['event'] == 'workflow_started':
                mode = 'workflow'

            if mode == 'workflow':
                if chunk['event'] == 'node_finished':
                    if chunk['data']['node_type'] == 'answer':
                        yield llm_entities.Message(
                            role='assistant',
                            content=self._try_convert_thinking(chunk['data']['outputs']['answer']),
                        )
            elif mode == 'basic':
                if chunk['event'] == 'message':
                    basic_mode_pending_chunk += chunk['answer']
                elif chunk['event'] == 'message_end':
                    yield llm_entities.Message(
                        role='assistant',
                        content=self._try_convert_thinking(basic_mode_pending_chunk),
                    )
                    basic_mode_pending_chunk = ''

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages(
        self, query: core_entities.Query
    ) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''

        plain_text, image_ids = await self._preprocess_user_message(query)

        files = [
            {
                'type': 'image',
                'transfer_method': 'local_file',
                'upload_file_id': image_id,
            }
            for image_id in image_ids
        ]

        ignored_events = []

        inputs = {}

        inputs.update(query.variables)

        pending_agent_message = ''

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            response_mode='streaming',
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-agent-chunk: ' + str(chunk))

            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'agent_message':
                pending_agent_message += chunk['answer']
            else:
                if pending_agent_message.strip() != '':
                    pending_agent_message = pending_agent_message.replace('</details>Action:', '</details>')
                    yield llm_entities.Message(
                        role='assistant',
                        content=self._try_convert_thinking(pending_agent_message),
                    )
                pending_agent_message = ''

                if chunk['event'] == 'agent_thought':
                    if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                        continue

                    if chunk['tool']:
                        msg = llm_entities.Message(
                            role='assistant',
                            tool_calls=[
                                llm_entities.ToolCall(
                                    id=chunk['id'],
                                    type='function',
                                    function=llm_entities.FunctionCall(
                                        name=chunk['tool'],
                                        arguments=json.dumps({}),
                                    ),
                                )
                            ],
                        )
                        yield msg
                if chunk['event'] == 'message_file':
                    if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                        base_url = self.dify_client.base_url

                        if base_url.endswith('/v1'):
                            base_url = base_url[:-3]

                        image_url = base_url + chunk['url']

                        yield llm_entities.Message(
                            role='assistant',
                            content=[llm_entities.ContentElement.from_image_url(image_url)],
                        )
                if chunk['event'] == 'error':
                    raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _workflow_messages(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """调用工作流"""

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, image_ids = await self._preprocess_user_message(query)

        files = [
            {
                'type': 'image',
                'transfer_method': 'local_file',
                'upload_file_id': image_id,
            }
            for image_id in image_ids
        ]

        ignored_events = ['text_chunk', 'workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)

        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'node_started':
                if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                    continue

                msg = llm_entities.Message(
                    role='assistant',
                    content=None,
                    tool_calls=[
                        llm_entities.ToolCall(
                            id=chunk['data']['node_id'],
                            type='function',
                            function=llm_entities.FunctionCall(
                                name=chunk['data']['title'],
                                arguments=json.dumps({}),
                            ),
                        )
                    ],
                )

                yield msg

            elif chunk['event'] == 'workflow_finished':
                if chunk['data']['error']:
                    raise errors.DifyAPIError(chunk['data']['error'])

                msg = llm_entities.Message(
                    role='assistant',
                    content=chunk['data']['outputs']['summary'],
                )

                yield msg

    async def run(self, query: core_entities.Query) -> typing.AsyncGenerator[llm_entities.Message, None]:
        """运行请求"""
        if self.pipeline_config['ai']['dify-service-api']['app-type'] == 'chat':
            async for msg in self._chat_messages(query):
                yield msg
        elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
            async for msg in self._agent_chat_messages(query):
                yield msg
        elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
            async for msg in self._workflow_messages(query):
                yield msg
        else:
            raise errors.DifyAPIError(
                f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
            )
