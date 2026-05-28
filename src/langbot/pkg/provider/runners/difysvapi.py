from __future__ import annotations

import typing
import json
import time
import uuid
import base64
import mimetypes


from langbot.pkg.provider import runner
from langbot.pkg.core import app
import langbot_plugin.api.entities.builtin.provider.message as provider_message
from langbot.pkg.utils import image
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot.libs.dify_service_api.v1 import client, errors
import httpx


# Module-level store for paused-workflow form state, keyed by session key
# (launcher_type_value + "_" + launcher_id). Keeps state out of the SDK
# Conversation type, which may not accept arbitrary attribute assignment.
_PENDING_FORMS: dict[str, dict[str, typing.Any]] = {}
_PENDING_FORM_DEFAULT_TTL = 30 * 60  # 30 minutes safety cap


def _session_key_from_query(query: pipeline_query.Query) -> str:
    return f'{query.session.launcher_type.value}_{query.session.launcher_id}'


def _prune_pending_forms(now: float | None = None) -> None:
    if now is None:
        now = time.time()
    expired = [key for key, data in _PENDING_FORMS.items() if data.get('_expires_at', 0) <= now]
    for key in expired:
        _PENDING_FORMS.pop(key, None)


def _set_pending_form(session_key: str, form_data: dict[str, typing.Any]) -> None:
    _prune_pending_forms()
    stored = dict(form_data)
    expiration_time = stored.get('expiration_time')
    try:
        expiration_ts = float(expiration_time) if expiration_time is not None else 0.0
    except (TypeError, ValueError):
        expiration_ts = 0.0
    stored['_expires_at'] = expiration_ts or (time.time() + _PENDING_FORM_DEFAULT_TTL)
    _PENDING_FORMS[session_key] = stored


def _get_pending_form(session_key: str) -> dict[str, typing.Any] | None:
    _prune_pending_forms()
    return _PENDING_FORMS.get(session_key)


def _clear_pending_form(session_key: str) -> None:
    _PENDING_FORMS.pop(session_key, None)


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

    def _extract_dify_text_output(self, value: typing.Any) -> str:
        """Extract text content from Dify output payload."""
        if value is None:
            return ''
        if isinstance(value, dict):
            content = value.get('content')
            if isinstance(content, str):
                return content
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ''
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return value
            if isinstance(parsed, dict) and isinstance(parsed.get('content'), str):
                return parsed['content']
            return value
        return str(value)

    async def _preprocess_user_message(self, query: pipeline_query.Query) -> tuple[str, list[dict]]:
        """预处理用户消息，提取纯文本，并将图片/文件上传到 Dify 服务

        Returns:
            tuple[str, list[dict]]: 纯文本和上传后的文件描述（包含 type 与 id）
        """
        plain_text = ''
        upload_files: list[dict] = []
        user_tag = f'{query.session.launcher_type.value}_{query.session.launcher_id}'

        async def upload_file_bytes(file_name: str, file_bytes: bytes, content_type: str) -> str:
            file_name = file_name or 'file'
            content_type = content_type or 'application/octet-stream'
            file = (file_name, file_bytes, content_type)
            resp = await self.dify_client.upload_file(file, user_tag)
            return resp['id']

        async def download_file(file_url: str) -> tuple[bytes, str]:
            """Download file from url (supports data url)."""

            async with httpx.AsyncClient() as client_session:
                resp = await client_session.get(file_url)
                resp.raise_for_status()
                content_type = (
                    resp.headers.get('content-type') or mimetypes.guess_type(file_url)[0] or 'application/octet-stream'
                )
                return resp.content, content_type

        def _detect_file_type(content_type: str) -> str:
            """Map MIME to dify file type."""
            if content_type and content_type.startswith('image/'):
                return 'image'
            if content_type and content_type.startswith('audio/'):
                return 'audio'
            if content_type and content_type.startswith('video/'):
                return 'video'
            return 'document'

        if isinstance(query.user_message.content, list):
            for ce in query.user_message.content:
                if ce.type == 'text':
                    plain_text += ce.text
                elif ce.type == 'image_base64':
                    image_b64, image_format = await image.extract_b64_and_format(ce.image_base64)
                    file_bytes = base64.b64decode(image_b64)
                    image_id = await upload_file_bytes(f'img.{image_format}', file_bytes, f'image/{image_format}')
                    upload_files.append({'type': 'image', 'id': image_id})
                elif ce.type == 'file_url':
                    file_url = getattr(ce, 'file_url', None)
                    file_name = getattr(ce, 'file_name', None) or 'file'
                    try:
                        file_bytes, content_type = await download_file(file_url)
                        file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                        file_type = _detect_file_type(content_type)
                        upload_files.append({'type': file_type, 'id': file_id})
                    except Exception as e:
                        self.ap.logger.warning(f'dify file upload failed: {e}')
                elif ce.type == 'file_base64':
                    file_name = getattr(ce, 'file_name', None) or 'file'

                    header, b64_data = ce.file_base64.split(',', 1)
                    content_type = 'application/octet-stream'
                    if ';' in header:
                        content_type = header.split(';')[0][5:] or content_type
                    file_bytes = base64.b64decode(b64_data)
                    file_id = await upload_file_bytes(file_name, file_bytes, content_type)
                    file_type = _detect_file_type(content_type)
                    upload_files.append({'type': file_type, 'id': file_id})

        elif isinstance(query.user_message.content, str):
            plain_text = query.user_message.content

        plain_text = plain_text if plain_text else self.pipeline_config['ai']['dify-service-api']['base-prompt']

        return plain_text, upload_files

    async def _chat_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
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
                        answer = self._extract_dify_text_output(chunk['data']['outputs'].get('answer'))
                        content, _ = self._process_thinking_content(answer)

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
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
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
                        # 检查URL是否已经是完整的连接
                        if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                            image_url = chunk['url']
                        else:
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

    async def _submit_workflow_form_blocking(
        self, form_action: dict
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """Submit human input to resume a paused Dify workflow (non-streaming)."""

        form_token = form_action['form_token']
        workflow_run_id = form_action['workflow_run_id']
        user = form_action['user']
        action_id = form_action.get('action_id', '')
        inputs = form_action.get('inputs', {})

        async for chunk in self.dify_client.workflow_submit(
            form_token=form_token,
            workflow_run_id=workflow_run_id,
            inputs=inputs,
            user=user,
            action=action_id,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-submit-chunk: ' + str(chunk))

            if chunk['event'] == 'workflow_finished':
                if chunk['data'].get('error'):
                    raise errors.DifyAPIError(chunk['data']['error'])
                content, _ = self._process_thinking_content(chunk['data']['outputs']['summary'])
                yield provider_message.Message(
                    role='assistant',
                    content=content,
                )

    def _merge_pending_form_action(self, form_action: dict | None, pending_form: dict | None) -> dict | None:
        """Backfill resume fields from the pending form stored on the conversation."""
        if not form_action:
            return None

        merged_action = dict(form_action)
        if pending_form:
            merged_action.setdefault('form_token', pending_form.get('form_token', ''))
            merged_action.setdefault('workflow_run_id', pending_form.get('workflow_run_id', ''))
            merged_action.setdefault('inputs', pending_form.get('inputs', {}))
            merged_action.setdefault('user', pending_form.get('user', ''))

            # Resolve clicked action's display title from the stored actions list
            if 'action_title' not in merged_action:
                clicked_id = merged_action.get('action_id', '')
                for action in pending_form.get('actions', []):
                    if str(action.get('id', '')) == str(clicked_id):
                        merged_action['action_title'] = action.get('title', clicked_id)
                        break

        return merged_action

    def _match_pending_form_action(self, user_text: str, pending_form: dict | None) -> dict | None:
        """Match plain text replies against pending Dify form actions."""
        if not pending_form:
            return None

        normalized_text = user_text.strip().lower()
        if not normalized_text:
            return None

        for action in pending_form.get('actions', []):
            titles = {
                str(action.get('title', '')).strip().lower(),
                str(action.get('id', '')).strip().lower(),
            }
            if normalized_text in titles:
                return {
                    'form_token': pending_form.get('form_token', ''),
                    'workflow_run_id': pending_form.get('workflow_run_id', ''),
                    'action_id': action.get('id', ''),
                    'action_title': action.get('title', action.get('id', '')),
                    'inputs': pending_form.get('inputs', {}),
                    'user': pending_form.get('user', ''),
                }

        return None

    async def _workflow_messages(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.Message, None]:
        """调用工作流"""

        # Check if this is a form action resume (button click or text match)
        form_action = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)
        pending_form = _get_pending_form(session_key)

        if form_action:
            form_action = self._merge_pending_form_action(form_action, pending_form)
            _clear_pending_form(session_key)
        elif pending_form:
            form_action = self._match_pending_form_action(str(query.message_chain), pending_form)
            if form_action:
                _clear_pending_form(session_key)

        if form_action:
            async for msg in self._submit_workflow_form_blocking(form_action):
                yield msg
            return

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        ignored_events = ['text_chunk', 'workflow_started']

        inputs = {  # these variables are legacy variables, we need to keep them for compatibility
            'langbot_user_message_text': plain_text,
            'langbot_session_id': query.variables['session_id'],
            'langbot_conversation_id': query.variables['conversation_id'],
            'langbot_msg_create_time': query.variables['msg_create_time'],
        }

        inputs.update(query.variables)
        human_input_yielded = False

        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                continue

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                workflow_run_id = chunk['data'].get('workflow_run_id', '')
                for reason in reasons:
                    if reason.get('TYPE') == 'human_input_required':
                        form_content = reason.get('form_content', '')
                        actions = reason.get('actions', [])
                        node_title = reason.get('node_title', '')

                        _set_pending_form(
                            _session_key_from_query(query),
                            {
                                'workflow_run_id': workflow_run_id,
                                'form_id': reason.get('form_id'),
                                'form_token': reason.get('form_token'),
                                'node_id': reason.get('node_id'),
                                'node_title': node_title,
                                'form_content': form_content,
                                'inputs': reason.get('inputs', {}),
                                'actions': actions,
                                'expiration_time': reason.get('expiration_time'),
                                'user': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                            },
                        )

                        query.variables['_dify_form_render'] = {
                            'form_content': form_content,
                            'actions': actions,
                            'node_title': node_title,
                        }

                        action_lines = '\n'.join(f'- [{a.get("title", a.get("id", ""))}]' for a in actions)
                        display_text = f'[Human Input Required] {node_title}\n{form_content}\n{action_lines}'

                        human_input_yielded = True
                        yield provider_message.Message(
                            role='assistant',
                            content=display_text,
                        )

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
                if human_input_yielded:
                    break
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
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
        ]

        mode = 'basic'
        basic_mode_pending_chunk = ''

        inputs = {}

        inputs.update(query.variables)
        message_idx = 0

        chunk = None  # 初始化chunk变量，防止在没有响应时引用错误

        is_final = False
        think_start = False
        think_end = False
        yielded_final = False

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

            if chunk['event'] == 'workflow_started':
                mode = 'workflow'
            elif chunk['event'] in ('node_started', 'node_finished', 'workflow_finished'):
                # Some Dify deployments may omit workflow_started in streamed chunks.
                mode = 'workflow'

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
            elif chunk['event'] == 'workflow_finished':
                is_final = True
                if chunk['data'].get('error'):
                    raise errors.DifyAPIError(chunk['data']['error'])

            if mode == 'workflow' and chunk['event'] == 'node_finished':
                if chunk['data'].get('node_type') == 'answer':
                    answer = self._extract_dify_text_output(chunk['data'].get('outputs', {}).get('answer'))
                    if answer:
                        basic_mode_pending_chunk = answer

            if (
                not yielded_final
                and (is_final or message_idx % 8 == 0)
                and (basic_mode_pending_chunk != '' or is_final)
            ):
                # content, _ = self._process_thinking_content(basic_mode_pending_chunk)
                yield provider_message.MessageChunk(
                    role='assistant',
                    content=basic_mode_pending_chunk,
                    is_final=is_final,
                )
                if is_final:
                    yielded_final = True

        if chunk is None:
            raise errors.DifyAPIError('Dify API 没有返回任何响应，请检查网络连接和API配置')

        query.session.using_conversation.uuid = chunk['conversation_id']

    async def _agent_chat_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用聊天助手"""
        cov_id = query.session.using_conversation.uuid or None
        query.variables['conversation_id'] = cov_id

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
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
                    if think_start and not think_end:
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
                        # 检查URL是否已经是完整的连接
                        if chunk['url'].startswith('http://') or chunk['url'].startswith('https://'):
                            image_url = chunk['url']
                        else:
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

    async def _submit_workflow_form(
        self, form_action: dict
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """Submit human input to resume a paused Dify workflow."""

        form_token = form_action['form_token']
        workflow_run_id = form_action['workflow_run_id']
        user = form_action['user']
        action_id = form_action.get('action_id', '')
        action_title = form_action.get('action_title', '') or action_id
        inputs = form_action.get('inputs', {})

        messsage_idx = 0
        is_final = False
        think_start = False
        think_end = False
        workflow_contents = ''
        repause_form_data: dict | None = None

        remove_think = self.pipeline_config['output'].get('misc', {}).get('remove-think')
        async for chunk in self.dify_client.workflow_submit(
            form_token=form_token,
            workflow_run_id=workflow_run_id,
            inputs=inputs,
            user=user,
            action=action_id,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-submit-chunk: ' + str(chunk))

            yield_this_iteration = False

            if chunk['event'] == 'workflow_finished':
                is_final = True
                yield_this_iteration = True
                if chunk['data'].get('error'):
                    raise errors.DifyAPIError(chunk['data']['error'])

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                new_run_id = chunk['data'].get('workflow_run_id', workflow_run_id)
                for reason in reasons:
                    if reason.get('TYPE') != 'human_input_required':
                        continue
                    form_content = reason.get('form_content', '')
                    actions = reason.get('actions', [])
                    node_title = reason.get('node_title', '')
                    raw_inputs = reason.get('inputs', {})

                    _set_pending_form(
                        user,
                        {
                            'workflow_run_id': new_run_id,
                            'form_id': reason.get('form_id'),
                            'form_token': reason.get('form_token'),
                            'node_id': reason.get('node_id'),
                            'node_title': node_title,
                            'form_content': form_content,
                            'inputs': raw_inputs if isinstance(raw_inputs, dict) else {},
                            'actions': actions,
                            'expiration_time': reason.get('expiration_time'),
                            'user': user,
                        },
                    )

                    repause_form_data = {
                        'form_content': form_content,
                        'actions': actions,
                        'node_title': node_title,
                        'workflow_run_id': new_run_id,
                        'form_token': reason.get('form_token', ''),
                    }
                    is_final = True
                    yield_this_iteration = True
                    break

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
                if messsage_idx % 8 == 0:
                    yield_this_iteration = True

            if yield_this_iteration:
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=workflow_contents,
                    is_final=is_final,
                )
                msg._resume_from_form = True
                if action_title:
                    msg._resume_action_title = action_title
                if is_final and repause_form_data:
                    msg._form_data = repause_form_data
                    msg._open_new_card = True
                yield msg
                if is_final:
                    return

    async def _workflow_messages_chunk(
        self, query: pipeline_query.Query
    ) -> typing.AsyncGenerator[provider_message.MessageChunk, None]:
        """调用工作流"""

        # Check if this is a form action resume (button click or text match)
        form_action = query.variables.get('_dify_form_action')
        session_key = _session_key_from_query(query)
        pending_form = _get_pending_form(session_key)

        if form_action:
            form_action = self._merge_pending_form_action(form_action, pending_form)
            _clear_pending_form(session_key)
        elif pending_form:
            form_action = self._match_pending_form_action(str(query.message_chain), pending_form)
            if form_action:
                _clear_pending_form(session_key)

        if form_action:
            # Resume paused workflow via submit endpoint
            async for msg in self._submit_workflow_form(form_action):
                yield msg
            return

        if not query.session.using_conversation.uuid:
            query.session.using_conversation.uuid = str(uuid.uuid4())

        query.variables['conversation_id'] = query.session.using_conversation.uuid

        plain_text, upload_files = await self._preprocess_user_message(query)

        files = [
            {
                'type': f['type'],
                'transfer_method': 'local_file',
                'upload_file_id': f['id'],
            }
            for f in upload_files
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
        workflow_run_id = ''
        human_input_yielded = False

        # Saved form data to attach to the final MessageChunk so the adapter
        # can detect it when is_final=True and render buttons.
        pending_form_data = None
        display_text = ''

        remove_think = self.pipeline_config['output'].get('misc', '').get('remove-think')
        async for chunk in self.dify_client.workflow_run(
            inputs=inputs,
            user=f'{query.session.launcher_type.value}_{query.session.launcher_id}',
            files=files,
            timeout=120,
        ):
            self.ap.logger.debug('dify-workflow-chunk: ' + str(chunk))
            if chunk['event'] in ignored_events:
                if chunk['event'] == 'workflow_started':
                    workflow_run_id = chunk['data'].get('workflow_run_id', '')
                continue

            if chunk['event'] == 'workflow_paused':
                reasons = chunk['data'].get('reasons', [])
                workflow_run_id = chunk['data'].get('workflow_run_id', workflow_run_id)
                for reason in reasons:
                    if reason.get('TYPE') == 'human_input_required':
                        form_content = reason.get('form_content', '')
                        actions = reason.get('actions', [])
                        node_title = reason.get('node_title', '')

                        # Persist form state in module-level store keyed by session
                        raw_inputs = reason.get('inputs', {})
                        _set_pending_form(
                            _session_key_from_query(query),
                            {
                                'workflow_run_id': workflow_run_id,
                                'form_id': reason.get('form_id'),
                                'form_token': reason.get('form_token'),
                                'node_id': reason.get('node_id'),
                                'node_title': node_title,
                                'form_content': form_content,
                                'inputs': raw_inputs if isinstance(raw_inputs, dict) else {},
                                'actions': actions,
                                'expiration_time': reason.get('expiration_time'),
                                'user': f'{query.session.launcher_type.value}_{query.session.launcher_id}',
                            },
                        )

                        # Pass form render metadata to downstream stages
                        query.variables['_dify_form_render'] = {
                            'form_content': form_content,
                            'actions': actions,
                            'node_title': node_title,
                        }

                        action_lines = '\n'.join(f'- [{a.get("title", a.get("id", ""))}]' for a in actions)
                        display_text = f'[Human Input Required] {node_title}\n{form_content}\n{action_lines}'
                        workflow_contents += display_text + '\n'

                        # Save form data to attach to the final chunk later.
                        # We do NOT yield here — the form content will be sent
                        # as the final MessageChunk (with is_final=True and
                        # _form_data) so the adapter can update the card and
                        # add buttons in one pass.
                        pending_form_data = {
                            'form_content': form_content,
                            'actions': actions,
                            'node_title': node_title,
                            'workflow_run_id': workflow_run_id,
                            'form_token': reason.get('form_token', ''),
                        }
                        human_input_yielded = True

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
                final_content = workflow_contents if workflow_contents.strip() else ''
                msg = provider_message.MessageChunk(
                    role='assistant',
                    content=final_content,
                    is_final=is_final,
                )
                # Attach form data to the final chunk for the adapter
                if is_final and pending_form_data:
                    msg._form_data = pending_form_data
                    pending_form_data = None
                yield msg

        # If the stream ended after workflow_paused without a
        # workflow_finished event, yield a final chunk so the adapter
        # can update the card and add buttons.
        if human_input_yielded and not is_final:
            msg = provider_message.MessageChunk(
                role='assistant',
                content=workflow_contents or display_text,
                is_final=True,
            )
            msg._form_data = pending_form_data
            yield msg

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
