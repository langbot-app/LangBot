from __future__ import annotations

import typing
import json
import uuid
import base64


from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.dify_service_api.v1 import client, errors


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
        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')
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

        # 3. 根据 remove_think 参数决定是否保留思维链
        if remove_think:
            return content, ''
        else:
            # 如果有思维链内容，将其以 <think> 格式添加到 content 开头
            if thinking_content:
                content = f'<think>\n{thinking_content}\n</think>\n{content}'.strip()
            return content, thinking_content

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[str]]:
        """预处理用户消息，提取纯文本，并将图片上传到 Dify 服务

        Returns:
            tuple[str, list[str]]: 纯文本和图片的 Dify 服务图片 ID
        """
        plain_text = ''
        file_ids = []

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
                    file_ids.append(image_id)
                # elif ce.type == "file_url":
                #     file_bytes = base64.b64decode(ce.file_url)
                #     file_upload_resp = await self.dify_client.upload_file(
                #         file_bytes,
                #         f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                #     )
                #     file_id = file_upload_resp['id']
                #     file_ids.append(file_id)
        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content
        # plain_text = "When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image." if file_ids and not plain_text else plain_text
        # plain_text = "The user message type cannot be parsed." if not file_ids and not plain_text else plain_text
        # plain_text = plain_text if plain_text else "When the file content is readable, please read the content of this file. When the file is an image, describe the content of this image."
        # print(self.pipeline_config['ai'])
        plain_text = plain_text if plain_text else self.pipeline_config['ai']['dify-service-api']['base-prompt']

        return plain_text, file_ids

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''
        query.variables['conversation_id'] = cov_id

        plain_text, image_ids = await self._preprocess_user_message(query)

        files = [
            {
                'type': 'image',
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
                        content, _ = self._process_thinking_content(chunk['data']['outputs']['answer'])

                        yield provider_message.Message(
                            role='assistant',
                            content=content,
                        )
            elif mode == 'basic':
                if chunk['event'] == 'message':
                    basic_mode_pending_chunk += chunk['answer']
                elif chunk['event'] == 'message_end':
                    content, _ = self._process_thinking_content(basic_mode_pending_chunk)
                    yield provider_message.Message(
                        role='assistant',
                        content=content,
                    )
                    basic_mode_pending_chunk = ''

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''
        query.variables['conversation_id'] = cov_id

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

            if chunk['event'] == 'agent_message' or chunk['event'] == 'message':
                pending_agent_message += chunk['answer']
            else:
                if pending_agent_message.strip() != '':
                    pending_agent_message = pending_agent_message.replace('</details>Action:', '</details>')
                    content, _ = self._process_thinking_content(pending_agent_message)
                    yield provider_message.Message(
                        role='assistant',
                        content=content,
                    )
                pending_agent_message = ''

                if chunk['event'] == 'agent_thought':
                    if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                        continue

                    if chunk['tool']:
                        msg = provider_message.Message(
                            role='assistant',
                            tool_calls=[
                                provider_message.ToolCall(
                                    id=chunk['id'],
                                    type='function',
                                    function=provider_message.FunctionCall(
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

                        yield provider_message.Message(
                            role='assistant',
                            content=[provider_message.ContentElement.from_image_url(image_url)],
                        )
                if chunk['event'] == 'error':
                    raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _workflow_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
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

                msg = provider_message.Message(
                    role='assistant',
                    content=None,
                    tool_calls=[
                        provider_message.ToolCall(
                            id=chunk['data']['node_id'],
                            type='function',
                            function=provider_message.FunctionCall(
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
                content, _ = self._process_thinking_content(chunk['data']['outputs']['summary'])

                msg = provider_message.Message(
                    role='assistant',
                    content=content,
                )

                yield msg

    async def _chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''
        query.variables['conversation_id'] = cov_id

        plain_text, image_ids = await self._preprocess_user_message(query)

        files = [
            {
                'type': 'image',
                'transfer_method': 'local_file',
                'upload_file_id': image_id,
            }
            for image_id in image_ids
        ]

        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)
        message_idx = 0

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        is_final = False
        think_start = False
        think_end = False

        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')

        async for chunk in self.dify_client.chat_messages(
            inputs=inputs,
            query=plain_text,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            conversation_id=cov_id,
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-chat-chunk: ' + str(chunk))

            # if chunk['event'] == 'workflow_started':
            #     mode = 'workflow'
            # if mode == 'workflow':
            # elif mode == 'basic':
            # 因为都只是返回的 message也没有工具调用什么的，暂时不分类
            if chunk['event'] == 'message':
                message_idx += 1
                if remove_think:
                    if '<think>' in chunk['answer'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['answer'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['answer'])
                        basic_mode_pending_chunk += content
                        think_end = True
                    elif think_end:
                        basic_mode_pending_chunk += chunk['answer']
                    if think_start:
                        continue

                else:
                    basic_mode_pending_chunk += chunk['answer']

            if chunk['event'] == 'message_end':
                is_final = True

            if is_final or message_idx % 8 == 0:
                # content, _ = self._process_thinking_content(basic_mode_pending_chunk)
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=basic_mode_pending_chunk,
                    is_final=is_final,
                )

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or ''
        query.variables['conversation_id'] = cov_id

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
        message_idx = 0
        is_final = False
        think_start = False
        think_end = False

        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')

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
                message_idx += 1
                if remove_think:
                    if '<think>' in chunk['answer'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['answer'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['answer'])
                        pending_agent_message += content
                        think_end = True
                    elif think_end or not think_start:
                        pending_agent_message += chunk['answer']
                    if think_start:
                        continue

                else:
                    pending_agent_message += chunk['answer']
            elif chunk['event'] == 'message_end':
                is_final = True
            else:
                if chunk['event'] == 'agent_thought':
                    if chunk['tool'] != '' and chunk['observation'] != '':  # 工具调用结果，跳过
                        continue
                    message_idx += 1
                    if chunk['tool']:
                        msg = provider_message.MessageChunk(
                            role='assistant',
                            tool_calls=[
                                provider_message.ToolCall(
                                    id=chunk['id'],
                                    type='function',
                                    function=provider_message.FunctionCall(
                                        name=chunk['tool'],
                                        arguments=json.dumps({}),
                                    ),
                                )
                            ],
                        )
                        yield msg
                if chunk['event'] == 'message_file':
                    message_idx += 1
                    if chunk['type'] == 'image' and chunk['belongs_to'] == 'assistant':
                        base_url = self.dify_client.base_url

                        if base_url.endswith('/v1'):
                            base_url = base_url[:-3]

                        image_url = base_url + chunk['url']

                        yield provider_message.MessageChunk(
                            role='assistant',
                            content=[provider_message.ContentElement.from_image_url(image_url)],
                            is_final=is_final,
                        )

                if chunk['event'] == 'error':
                    raise errors.DifyAPIError('dify 服务错误: ' + chunk['message'])
            if message_idx % 8 == 0 or is_final:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=pending_agent_message,
                    is_final=is_final,
                )

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _workflow_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
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

        ignored_events = ['workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)
        messsage_idx = 0
        is_final = False
        think_start = False
        think_end = False
        workflow_contents = ''

        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')
        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                continue
            if chunk['event'] == 'workflow_finished':
                is_final = True
                if chunk['data']['error']:
                    raise errors.DifyAPIError(chunk['data']['error'])

            if chunk['event'] == 'text_chunk':
                messsage_idx += 1
                if remove_think:
                    if '<think>' in chunk['data']['text'] and not think_start:
                        think_start = True
                        continue
                    if '</think>' in chunk['data']['text'] and not think_end:
                        import re

                        content = re.sub(r'^\n</think>', '', chunk['data']['text'])
                        workflow_contents += content
                        think_end = True
                    elif think_end:
                        workflow_contents += chunk['data']['text']
                    if think_start:
                        continue

                else:
                    workflow_contents += chunk['data']['text']

            if chunk['event'] == 'node_started':
                if chunk['data']['node_type'] == 'start' or chunk['data']['node_type'] == 'end':
                    continue
                messsage_idx += 1
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=None,
                    tool_calls=[
                        provider_message.ToolCall(
                            id=chunk['data']['node_id'],
                            type='function',
                            function=provider_message.FunctionCall(
                                name=chunk['data']['title'],
                                arguments=json.dumps({}),
                            ),
                        )
                    ],
                )

                yield msg

            if messsage_idx % 8 == 0 or is_final:
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=workflow_contents,
                    is_final=is_final,
                )

    async def run(self, query: pipeline_query.Query) -> typing.AsyncGenerator[provider_message.Message, None]:
        """运行请求"""
        if await query.adapter.is_stream_output_supported():
            msg_idx = 0
            if self.pipeline_config['ai']['dify-service-api']['app-type'] == 'chat':
                async for msg in self._chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'agent':
                async for msg in self._agent_chat_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            elif self.pipeline_config['ai']['dify-service-api']['app-type'] == 'workflow':
                async for msg in self._workflow_messages_chunk(query):
                    msg_idx += 1
                    msg.msg_sequence = msg_idx
                    yield msg
            else:
                raise errors.DifyAPIError(
                    f'不支持的 Dify 应用类型: {self.pipeline_config["ai"]["dify-service-api"]["app-type"]}'
                )
        else:
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
