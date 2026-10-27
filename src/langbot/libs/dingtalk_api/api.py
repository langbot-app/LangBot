import asyncio
import base64
import json
import logging
import os
import time
import typing
import uuid
import urllib.parse
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional
import dingtalk_stream  # type: ignore
import websockets
from .EchoHandler import EchoTextHandler
from .card_callback import DingTalkCardActionHandler
from .dingtalkevent import DingTalkEvent
from .a2ui import (
    A2UI_PROTOCOL_VERSION,
    create_text_card_messages,
    serialize_messages,
    update_text_card_messages,
)
from .thinking import visible_think_markers
import httpx
import traceback
from langbot.pkg.utils import httpclient
from langbot.pkg.utils.outbound_url import assert_safe_outbound_url


_stdout_logger = logging.getLogger('langbot.dingtalk_api')


DINGTALK_OPENAPI_BASE = 'https://api.dingtalk.com'
# Legitimate session webhooks come from DingTalk itself
# (https://oapi.dingtalk.com/robot/sendBySession?...). Anything else means the
# inbound event carried a forged destination.
DINGTALK_WEBHOOK_DOMAINS = ('dingtalk.com',)
_MAX_MEDIA_BYTES = 10 * 1024 * 1024
_MAX_GATEWAY_MESSAGE_BYTES = 1024 * 1024


def _read_local_media_limited(file_path: str) -> bytes:
    if os.path.getsize(file_path) > _MAX_MEDIA_BYTES:
        raise ValueError('DingTalk media exceeds the size limit')
    with open(file_path, 'rb') as file:
        body = file.read(_MAX_MEDIA_BYTES + 1)
    if len(body) > _MAX_MEDIA_BYTES:
        raise ValueError('DingTalk media exceeds the size limit')
    return body


async def _read_httpx_media_limited(response: httpx.Response) -> bytes:
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            if int(content_length) > _MAX_MEDIA_BYTES:
                raise ValueError('DingTalk media exceeds the size limit')
        except (TypeError, ValueError) as exc:
            if 'exceeds' in str(exc):
                raise
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > _MAX_MEDIA_BYTES:
            raise ValueError('DingTalk media exceeds the size limit')
    return bytes(body)


def is_stream_card_configured(config: dict) -> bool:
    return bool(config.get('markdown_card', True))


class DingTalkClient:
    _MAX_INBOUND_TASKS = 100

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        robot_name: str,
        robot_code: str,
        markdown_card: bool,
        logger: None,
        card_action_callback: Optional[Callable[[dict], Awaitable[None]]] = None,
    ):
        """初始化 WebSocket 连接并自动启动"""
        self.credential = dingtalk_stream.Credential(client_id, client_secret)
        self.client = dingtalk_stream.DingTalkStreamClient(self.credential)
        self.key = client_id
        self.secret = client_secret
        # 在 DingTalkClient 中传入自己作为参数，避免循环导入
        self.EchoTextHandler = EchoTextHandler(self)
        self.client.register_callback_handler(dingtalk_stream.chatbot.ChatbotMessage.TOPIC, self.EchoTextHandler)
        # STREAM-mode card action button click handler. Forwards parsed payload
        # to the adapter so it can resume paused Dify workflows.
        self.card_action_callback = card_action_callback
        self.card_action_handler = DingTalkCardActionHandler(self.client, self._on_card_action)
        self.client.register_callback_handler(
            dingtalk_stream.handlers.CallbackHandler.TOPIC_CARD_CALLBACK,
            self.card_action_handler,
        )
        self._message_handlers = {
            'example': [],
        }
        self.access_token = ''
        self.robot_name = robot_name
        self.robot_code = (robot_code or '').strip() or client_id
        self.access_token_expiry_time = ''
        self.markdown_card = markdown_card
        self.logger = logger
        # Attachment uploads still use the legacy oapi.dingtalk.com token.
        # The v1.0 application token does not work for that auth domain.
        self.legacy_access_token = ''
        self.legacy_access_token_expiry_time: typing.Optional[float] = None
        self._stopped = False  # Flag to control the event loop
        self._inbound_tasks: set[asyncio.Task] = set()
        self._http_client: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def _http_client_context(self):
        """Reuse one connection pool while preserving existing call structure."""

        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(event_hooks=httpclient.httpx_response_limit_hooks())
        yield self._http_client

    def _start_inbound_task(self, coro: typing.Coroutine) -> bool:
        """Start one bounded inbound callback task."""

        for task in tuple(self._inbound_tasks):
            if task.done():
                self._inbound_tasks.discard(task)
        if len(self._inbound_tasks) >= self._MAX_INBOUND_TASKS:
            coro.close()
            return False

        task = asyncio.create_task(coro)
        self._inbound_tasks.add(task)

        def done(done_task: asyncio.Task) -> None:
            self._inbound_tasks.discard(done_task)
            if not done_task.cancelled():
                done_task.exception()

        task.add_done_callback(done)
        return True

    async def _on_card_action(self, payload: dict) -> None:
        """Dispatch a parsed card-action payload to the adapter callback."""
        if self.card_action_callback is None:
            return
        try:
            await self.card_action_callback(payload)
        except Exception:
            if self.logger:
                await self.logger.error(f'DingTalk card action callback error: {traceback.format_exc()}')

    async def get_access_token(self):
        url = 'https://api.dingtalk.com/v1.0/oauth2/accessToken'
        headers = {'Content-Type': 'application/json'}
        data = {'appKey': self.key, 'appSecret': self.secret}
        async with self._http_client_context() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    response_data = await httpclient.parse_json_response(response)
                    self.access_token = response_data.get('accessToken')
                    expires_in = int(response_data.get('expireIn', 7200))
                    self.access_token_expiry_time = time.time() + expires_in - 60
            except Exception:
                await self.logger.error('failed to get access token in dingtalk')

    async def is_token_expired(self):
        """检查token是否过期"""
        if self.access_token_expiry_time is None:
            return True
        return time.time() > self.access_token_expiry_time

    async def check_access_token(self):
        if not self.access_token or await self.is_token_expired():
            return False
        return bool(self.access_token and self.access_token.strip())

    async def download_image(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = await httpclient.parse_json_response(response)
                download_url = result.get('downloadUrl')
            else:
                error_payload = await httpclient.parse_json_response(response)
                await self.logger.error(f'failed to get download url: {error_payload}')

        if download_url:
            return await self.download_url_to_base64(download_url)

    async def download_url_to_base64(self, download_url):
        async with self._http_client_context() as client:
            async with client.stream('GET', download_url) as response:
                if response.status_code == 200:
                    file_bytes = await _read_httpx_media_limited(response)
                    mime_type = response.headers.get('Content-Type', 'application/octet-stream')
                    base64_str = (await asyncio.to_thread(base64.b64encode, file_bytes)).decode('utf-8')
                    return f'data:{mime_type};base64,{base64_str}'
                error_body = await _read_httpx_media_limited(response)
                await self.logger.error(f'failed to get files: {error_body[:300]!r}')

    async def get_audio_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = await httpclient.parse_json_response(response)
                download_url = result.get('downloadUrl')
                if download_url:
                    return await self.download_url_to_base64(download_url)
                else:
                    error_payload = await httpclient.parse_json_response(response)
                    await self.logger.error(f'failed to get audio: {error_payload}')
            else:
                body = await httpclient.response_text(response)
                raise Exception(f'Error: {response.status_code}, {body}')

    async def get_file_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with self._http_client_context() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = await httpclient.parse_json_response(response)
                download_url = result.get('downloadUrl')
                if download_url:
                    return download_url
                else:
                    error_payload = await httpclient.parse_json_response(response)
                    await self.logger.error(f'failed to get file: {error_payload}')
            else:
                body = await httpclient.response_text(response)
                raise Exception(f'Error: {response.status_code}, {body}')

    async def update_incoming_message(self, message):
        """异步更新 DingTalkClient 中的 incoming_message"""
        # Resolve identity before downloading any attachments from this event.
        robot_code = getattr(message, 'robot_code', None)
        if isinstance(robot_code, str) and robot_code.strip():
            self.robot_code = robot_code.strip()
        message_data = await self.get_message(message)
        if message_data:
            event = DingTalkEvent.from_payload(message_data)
            if event:
                await self._handle_message(event)

    @staticmethod
    def _check_send_result(response):
        # HTTP 200 can still contain a rejected DingTalk message.
        data = response.json()
        if response.status_code != 200 or data.get('errcode', 0) != 0 or data.get('code'):
            raise RuntimeError(
                f'DingTalk delivery failed (HTTP {response.status_code}, '
                f'code={data.get("errcode", data.get("code", "unknown"))}): '
                f'{data.get("errmsg", data.get("message", "Unknown error"))}'
            )
        return data

    async def send_message(self, content: str, incoming_message, at: bool):
        if not content.strip():
            return {}
        content = visible_think_markers(content, self.markdown_card)
        if self.markdown_card:
            text = ('@' + incoming_message.sender_nick + ' ' if at else '') + content
            payload = {'msgtype': 'markdown', 'markdown': {'title': text[:80], 'text': text}}
        else:
            payload = {'msgtype': 'text', 'text': {'content': content}}
        payload['at'] = {'atUserIds': [incoming_message.sender_staff_id]}
        # The webhook URL arrives inside the inbound event, so verify it really
        # points at DingTalk before posting the reply (and any LLM output) to it.
        webhook_url = assert_safe_outbound_url(
            incoming_message.session_webhook,
            allowed_domains=DINGTALK_WEBHOOK_DOMAINS,
        )
        async with self._http_client_context() as client:
            response = await client.post(webhook_url, json=payload, timeout=30.0)
        return self._check_send_result(response)

    async def send_attachment(self, component, incoming_message):
        from langbot_plugin.api.entities.builtin.platform.message import Image

        is_image = isinstance(component, Image)
        name = getattr(component, 'name', '') or ('image.png' if is_image else 'file')
        name = os.path.basename(name)
        encoded = getattr(component, 'base64', None)
        if encoded:
            encoded = encoded.split(',', 1)[-1]
            if len(encoded) > 4 * ((_MAX_MEDIA_BYTES + 2) // 3):
                raise ValueError('DingTalk media exceeds the size limit')
            body = base64.b64decode(encoded, validate=True)
        elif getattr(component, 'path', None):
            body = await asyncio.to_thread(_read_local_media_limited, component.path)
        elif getattr(component, 'url', None):
            # A message component can carry an arbitrary URL. Attachments are
            # fetched from user-supplied hosts, so refuse anything that resolves
            # to loopback, a private range, or link-local metadata.
            media_url = assert_safe_outbound_url(component.url)
            async with self._http_client_context() as client:
                async with client.stream('GET', media_url, timeout=30.0) as response:
                    response.raise_for_status()
                    body = await _read_httpx_media_limited(response)
        else:
            raise ValueError('DingTalk attachment has no readable content')
        if len(body) > _MAX_MEDIA_BYTES:
            raise ValueError('DingTalk media exceeds the size limit')
        token = await self.get_legacy_access_token()
        if not token:
            raise RuntimeError('DingTalk media authentication failed')
        async with self._http_client_context() as client:
            response = await client.post(
                'https://oapi.dingtalk.com/media/upload',
                params={'access_token': token, 'type': 'image' if is_image else 'file'},
                files={'media': (name, body)},
                timeout=30.0,
            )
        uploaded = self._check_send_result(response)
        media_id = uploaded.get('media_id')
        if not media_id:
            raise RuntimeError('DingTalk media upload returned no media ID')
        if not await self.check_access_token():
            await self.get_access_token()
        params = (
            {'photoURL': media_id}
            if is_image
            else {'mediaId': media_id, 'fileName': name, 'fileType': os.path.splitext(name)[1].lstrip('.')}
        )
        payload = {
            'robotCode': self.robot_code or self.key,
            'msgKey': 'sampleImageMsg' if is_image else 'sampleFile',
            'msgParam': json.dumps(params, ensure_ascii=False),
        }
        if str(incoming_message.conversation_type) == '2':
            endpoint = 'groupMessages/send'
            payload['openConversationId'] = incoming_message.conversation_id
        else:
            endpoint = 'oToMessages/batchSend'
            payload['userIds'] = [incoming_message.sender_staff_id]
        async with self._http_client_context() as client:
            response = await client.post(
                f'{DINGTALK_OPENAPI_BASE}/v1.0/robot/{endpoint}',
                headers={'x-acs-dingtalk-access-token': self.access_token},
                json=payload,
                timeout=30.0,
            )
        return self._check_send_result(response)

    async def get_incoming_message(self):
        """获取收到的消息"""
        return await self.EchoTextHandler.get_incoming_message()

    def on_message(self, msg_type: str):
        def decorator(func: Callable[[DingTalkEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: DingTalkEvent):
        """
        处理消息事件。
        """
        # Skip message handling if stopped
        if self._stopped:
            return
        msg_type = event.conversation
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def _parse_quoted_message(self, replied_msg: dict) -> dict:
        """Parse the quoted/replied message and extract its content.

        Args:
            replied_msg: The repliedMsg object from DingTalk message

        Returns:
            A dict containing the quoted message info with keys:
            - message_id: The original message ID
            - msg_type: The message type (text, file, picture, audio, etc.)
            - content: The text content (if any)
            - file_url: The file download URL (if file type)
            - file_name: The file name (if file type)
            - picture: The picture base64 (if picture type)
            - audio: The audio base64 (if audio type)
        """
        quote_info = {
            'message_id': replied_msg.get('msgId', ''),
            'msg_type': replied_msg.get('msgType', ''),
            'sender_id': replied_msg.get('senderId', ''),
        }

        msg_type = replied_msg.get('msgType', '')
        content = replied_msg.get('content', {})

        # Handle content as string (JSON) or dict
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (json.JSONDecodeError, TypeError):
                content = {}

        if msg_type == 'text':
            # Text message
            if isinstance(content, dict):
                quote_info['content'] = content.get('content', '')
            else:
                quote_info['content'] = str(content)

        elif msg_type == 'file':
            # File message
            download_code = content.get('downloadCode')
            file_name = content.get('fileName')
            if download_code and file_name:
                try:
                    quote_info['file_url'] = await self.get_file_url(download_code)
                    quote_info['file_name'] = file_name
                except Exception as e:
                    if self.logger:
                        await self.logger.error(f'Failed to get quoted file URL: {e}')

        elif msg_type == 'picture':
            # Picture message
            download_code = content.get('downloadCode')
            if download_code:
                try:
                    quote_info['picture'] = await self.download_image(download_code)
                except Exception as e:
                    if self.logger:
                        await self.logger.error(f'Failed to download quoted image: {e}')

        elif msg_type == 'audio':
            # Audio message
            download_code = content.get('downloadCode')
            if download_code:
                try:
                    quote_info['audio'] = await self.get_audio_url(download_code)
                except Exception as e:
                    if self.logger:
                        await self.logger.error(f'Failed to get quoted audio: {e}')

        elif msg_type == 'richText':
            # Rich text message - extract text content
            rich_text = content.get('richText', [])
            texts = []
            for item in rich_text:
                if 'text' in item and item['text'] != '\n':
                    texts.append(item['text'])
            quote_info['content'] = '\n'.join(texts)

        return quote_info

    async def get_message(self, incoming_message: dingtalk_stream.chatbot.ChatbotMessage):
        try:
            # print(json.dumps(incoming_message.to_dict(), indent=4, ensure_ascii=False))
            message_data = {
                'IncomingMessage': incoming_message,
            }
            if str(incoming_message.conversation_type) == '1':
                message_data['conversation_type'] = 'FriendMessage'
            elif str(incoming_message.conversation_type) == '2':
                message_data['conversation_type'] = 'GroupMessage'

            # Check for quoted/replied message
            raw_data = incoming_message.to_dict()
            text_data = raw_data.get('text', {})
            if isinstance(text_data, dict) and text_data.get('isReplyMsg'):
                replied_msg = text_data.get('repliedMsg', {})
                if replied_msg:
                    quote_info = await self._parse_quoted_message(replied_msg)
                    message_data['QuotedMessage'] = quote_info

            if incoming_message.message_type == 'richText':
                data = incoming_message.rich_text_content.to_dict()

                # 使用统一的结构化数据格式，保持顺序
                rich_content = {
                    'Type': 'richText',
                    'Elements': [],  # 按顺序存储所有元素
                    'SimpleContent': '',  # 兼容字段：纯文本内容
                    'SimplePicture': '',  # 兼容字段：第一张图片
                }

                # 先收集所有文本和图片占位符
                text_elements = []

                # 解析富文本内容，保持原始顺序
                for item in data['richText']:
                    # 处理文本内容
                    if 'text' in item and item['text'] != '\n':
                        element = {'Type': 'text', 'Content': item['text']}
                        rich_content['Elements'].append(element)
                        text_elements.append(item['text'])

                    # 检查是否是图片元素 - 根据钉钉API的实际结构调整
                    # 钉钉富文本中的图片通常有特定标识，可能需要根据实际返回调整
                    elif item.get('type') == 'picture':
                        # 创建图片占位符
                        element = {
                            'Type': 'image_placeholder',
                        }
                        rich_content['Elements'].append(element)

                # 获取并下载所有图片
                image_list = incoming_message.get_image_list()
                if image_list:
                    new_elements = []
                    image_index = 0

                    for element in rich_content['Elements']:
                        if element['Type'] == 'image_placeholder':
                            if image_index < len(image_list) and image_list[image_index]:
                                image_url = await self.download_image(image_list[image_index])
                                new_elements.append({'Type': 'image', 'Picture': image_url})
                                image_index += 1
                            else:
                                # 如果没有对应的图片，保留占位符或跳过
                                continue
                        else:
                            new_elements.append(element)

                    rich_content['Elements'] = new_elements

                # 设置兼容字段
                all_texts = [elem['Content'] for elem in rich_content['Elements'] if elem.get('Type') == 'text']
                rich_content['SimpleContent'] = '\n'.join(all_texts) if all_texts else ''

                all_images = [elem['Picture'] for elem in rich_content['Elements'] if elem.get('Type') == 'image']
                if all_images:
                    rich_content['SimplePicture'] = all_images[0]
                    rich_content['AllImages'] = all_images  # 所有图片的列表

                # 设置原始的 content 和 picture 字段以保持兼容
                message_data['Content'] = rich_content['SimpleContent']
                message_data['Rich_Content'] = rich_content
                if all_images:
                    message_data['Picture'] = all_images[0]

            elif incoming_message.message_type == 'text':
                message_data['Content'] = incoming_message.get_text_list()[0]

                message_data['Type'] = 'text'
            elif incoming_message.message_type == 'picture':
                message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])

                message_data['Type'] = 'image'
            elif incoming_message.message_type == 'audio':
                raw_content = incoming_message.to_dict().get('content', {})
                # 兼容处理：如果 content 仍为 JSON 字符串则进行解析
                if isinstance(raw_content, str):
                    try:
                        raw_content = json.loads(raw_content)
                    except (json.JSONDecodeError, TypeError):
                        raw_content = {}

                if self.logger:
                    await self.logger.info(f'DingTalk audio raw content: {json.dumps(raw_content, ensure_ascii=False)}')

                # 提取钉钉自带的语音转写文字（Powered by Qwen）
                recognition = raw_content.get('recognition', '')
                if recognition:
                    message_data['Content'] = recognition

                download_code = raw_content.get('downloadCode')
                if download_code:
                    message_data['Audio'] = await self.get_audio_url(download_code)

                message_data['Type'] = 'audio'
            elif incoming_message.message_type == 'file':
                # 获取原始数据字典并提取嵌套的文件信息
                raw_data = incoming_message.to_dict()
                file_info = raw_data.get('content', {})

                # 兼容处理：如果 content 仍为 JSON 字符串则进行解析
                if isinstance(file_info, str):
                    try:
                        file_info = json.loads(file_info)
                    except (json.JSONDecodeError, TypeError):
                        file_info = {}

                download_code = file_info.get('downloadCode')
                file_name = file_info.get('fileName')

                if download_code and file_name:
                    # 转换 downloadCode 为可下载的真实 URL
                    message_data['File'] = await self.get_file_url(download_code)
                    message_data['Name'] = file_name
                else:
                    if self.logger:
                        await self.logger.error(f'Failed to extract file info from message content: {file_info}')
                    message_data['File'] = None
                    message_data['Name'] = None

                message_data['Type'] = 'file'

            copy_message_data = message_data.copy()
            del copy_message_data['IncomingMessage']
            # print("message_data:", json.dumps(copy_message_data, indent=4, ensure_ascii=False))
        except Exception:
            if self.logger:
                await self.logger.error(f'Error in get_message: {traceback.format_exc()}')
            else:
                traceback.print_exc()

        return message_data

    async def send_proactive_message_to_one(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        # For enterprise-internal robots, robotCode == AppKey (client_id).
        # The dedicated robot_code field is only required for scenario-group
        # robots or third-party robots; fall back to client_id when empty so
        # the common single-bot setup keeps working without manual config.
        robot_code = self.robot_code or self.key
        data = {
            'robotCode': robot_code,
            'userIds': [target_id],
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': visible_think_markers(content, False)}),
        }
        _stdout_logger.info(
            'DingTalk send_proactive_message_to_one request: robotCode=%s target_id=%s content_len=%d',
            robot_code,
            target_id,
            len(content),
        )
        try:
            async with self._http_client_context() as client:
                response = await client.post(url, headers=headers, json=data)
                response_body = await httpclient.response_text(response, max_chars=500)
                _stdout_logger.info(
                    'DingTalk send_proactive_message_to_one response: status=%d body=%s',
                    response.status_code,
                    response_body,
                )
                try:
                    body = response.json()
                except Exception:
                    body = {'text': response.text}
                if response.status_code == 200:
                    return body
                raise Exception(f'Error: {response.status_code}, {body}')
        except Exception:
            _stdout_logger.exception('DingTalk send_proactive_message_to_one error')
            await self.logger.error(f'failed to send proactive massage to person: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to person: {traceback.format_exc()}')

    async def send_proactive_message_to_group(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/groupMessages/send'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        data = {
            'robotCode': self.robot_code or self.key,
            'openConversationId': target_id,
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': visible_think_markers(content, False)}),
        }
        try:
            async with self._http_client_context() as client:
                response = await client.post(url, headers=headers, json=data)
                try:
                    body = response.json()
                except Exception:
                    body = {'text': response.text}
                if response.status_code == 200:
                    return body
                raise Exception(f'Error: {response.status_code}, {body}')
        except Exception:
            await self.logger.error(f'failed to send proactive massage to group: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to group: {traceback.format_exc()}')

    async def create_and_card(
        self,
        incoming_message: dingtalk_stream.ChatbotMessage,
        quote_origin: bool = False,
    ):
        """Create + deliver the streaming chat card for a chatbot reply.

        Returns ``(card state, out_track_id)`` for subsequent A2UI updates.
        """
        out_track_id = uuid.uuid4().hex
        surface_id = f'langbot-{out_track_id}'
        is_group = str(incoming_message.conversation_type) == '2'
        if is_group:
            open_space_id = f'dtv1.card//im_group.{incoming_message.conversation_id}'
        else:
            open_space_id = f'dtv1.card//im_robot.{incoming_message.sender_staff_id}'

        await self.create_and_deliver_ai_card(
            out_track_id=out_track_id,
            open_space_id=open_space_id,
            is_group=is_group,
            a2ui_messages=create_text_card_messages(surface_id),
            flow_status='PROCESSING',
            summary='LangBot is replying',
        )
        return {'surface_id': surface_id}, out_track_id

    async def send_card_message(self, card_instance, card_instance_id: str, content: str, is_final: bool):
        """Replace the streamed Markdown content on an A2UI card."""
        surface_id = (
            str(card_instance.get('surface_id') or '') if isinstance(card_instance, dict) else ''
        ) or f'langbot-{card_instance_id}'
        await self.update_ai_card(
            out_track_id=card_instance_id,
            a2ui_messages=update_text_card_messages(surface_id, visible_think_markers(content)),
            flow_status='FINISH' if is_final else 'PROCESSING',
        )

    @staticmethod
    def _check_ai_card_result(response) -> dict:
        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f'Invalid DingTalk AI card response (HTTP {response.status_code})') from exc
        if response.status_code != 200 or data.get('success') is not True:
            raise RuntimeError(
                f'DingTalk AI card request failed (HTTP {response.status_code}): '
                f'{data.get("message", data.get("errorMsg", data))}'
            )
        result = data.get('result') if isinstance(data.get('result'), dict) else {}
        failures = [
            item
            for item in result.get('deliverResults') or []
            if isinstance(item, dict) and item.get('success') is not True
        ]
        if failures:
            raise RuntimeError(f'DingTalk AI card delivery failed: {failures}')
        return result

    async def create_and_deliver_ai_card(
        self,
        *,
        out_track_id: str,
        open_space_id: str,
        is_group: bool,
        a2ui_messages: list[dict | str],
        flow_status: str = 'PROCESSING',
        summary: str = '',
        callback_type: str = 'STREAM',
        at_user_ids: Optional[dict] = None,
        recipients: Optional[list] = None,
        biz_context: Optional[dict] = None,
    ) -> dict:
        """Create and deliver an A2UI card as the configured robot application."""
        if not await self.check_access_token():
            await self.get_access_token()

        robot_code = self.robot_code or self.key
        body: dict = {
            'outTrackId': out_track_id,
            'openSpaceId': open_space_id,
            'protocolVersion': A2UI_PROTOCOL_VERSION,
            'flowStatus': flow_status,
            'a2uiMessages': serialize_messages(a2ui_messages),
            'summary': summary,
            'callbackType': callback_type,
        }
        if is_group:
            body['imGroupOpenSpaceModel'] = {'supportForward': False}
            deliver: dict = {'robotCode': robot_code}
            body['imGroupOpenDeliverModel'] = deliver
        else:
            body['imRobotOpenSpaceModel'] = {'supportForward': False}
            deliver = {'robotCode': robot_code}
            body['imRobotOpenDeliverModel'] = deliver
        if at_user_ids:
            deliver['atUserIds'] = at_user_ids
        if recipients is not None:
            deliver['recipients'] = recipients
        if biz_context:
            body['bizContext'] = biz_context

        url = f'{DINGTALK_OPENAPI_BASE}/v1.0/card/ai/instances/createAndDeliver'
        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }
        try:
            async with self._http_client_context() as client:
                response = await client.post(url, headers=headers, json=body, timeout=30.0)
            result = self._check_ai_card_result(response)
        except Exception as exc:
            error = RuntimeError(f'DingTalk AI card creation failed: {exc}')
            _stdout_logger.error('%s', error)
            raise error from exc
        _stdout_logger.info('DingTalk AI card created: outTrackId=%s', out_track_id)
        return result

    async def update_ai_card(
        self,
        *,
        out_track_id: str,
        a2ui_messages: list[dict | str],
        flow_status: str,
        out_update_id: Optional[str] = None,
    ) -> dict:
        """Apply an idempotent A2UI delta to an existing AI card."""
        if not await self.check_access_token():
            await self.get_access_token()

        body = {
            'outTrackId': out_track_id,
            'outUpdateId': out_update_id or uuid.uuid4().hex,
            'flowStatus': flow_status,
            'a2uiMessages': serialize_messages(a2ui_messages),
        }
        url = f'{DINGTALK_OPENAPI_BASE}/v1.0/card/ai/instances/update'
        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }
        try:
            async with self._http_client_context() as client:
                response = await client.put(url, headers=headers, json=body, timeout=30.0)
            return self._check_ai_card_result(response)
        except Exception as exc:
            error = RuntimeError(f'DingTalk AI card update failed: {exc}')
            _stdout_logger.error('%s', error)
            raise error from exc

    async def get_legacy_access_token(self) -> Optional[str]:
        """Fetch the LEGACY (oapi.dingtalk.com) access_token. This is a
        different auth domain from the v1.0 token cached in
        ``self.access_token`` — only the legacy token authorises the
        ``/media/upload`` endpoint used by attachment delivery.

        Returns the token string on success, None on failure. Caches
        with a 60s safety margin before the documented 7200s expiry.
        """
        now = time.time()
        if (
            self.legacy_access_token
            and self.legacy_access_token_expiry_time
            and now < self.legacy_access_token_expiry_time
        ):
            return self.legacy_access_token

        url = 'https://oapi.dingtalk.com/gettoken'
        try:
            async with self._http_client_context() as client:
                response = await client.get(url, params={'appkey': self.key, 'appsecret': self.secret}, timeout=15.0)
            data = await httpclient.parse_json_response(response) if response.status_code == 200 else {}
            if data.get('errcode') == 0 and data.get('access_token'):
                self.legacy_access_token = data['access_token']
                expires_in = int(data.get('expires_in', 7200))
                self.legacy_access_token_expiry_time = now + expires_in - 60
                return self.legacy_access_token
            if self.logger:
                response_body = await httpclient.response_text(response, max_chars=200)
                await self.logger.error(
                    f'DingTalk legacy gettoken failed: status={response.status_code} body={response_body}'
                )
        except Exception:
            _stdout_logger.exception('DingTalk legacy gettoken error')
            if self.logger:
                await self.logger.error(f'DingTalk legacy gettoken error: {traceback.format_exc()}')
        return None

    async def start(self):
        """启动 WebSocket 连接，监听消息"""
        self._stopped = False
        self.client.pre_start()

        while not self._stopped:
            try:
                # open_connection performs blocking network I/O in the DingTalk SDK.
                # Run it off the event loop so connection stalls do not block the
                # LangBot HTTP server and other async tasks.
                connection = await asyncio.to_thread(self.client.open_connection)

                if not connection:
                    if self.logger:
                        await self.logger.error('DingTalk: open connection failed')
                    await asyncio.sleep(10)
                    continue

                uri = '%s?ticket=%s' % (connection['endpoint'], urllib.parse.quote_plus(connection['ticket']))
                async with websockets.connect(uri, max_size=_MAX_GATEWAY_MESSAGE_BYTES) as websocket:
                    self.client.websocket = websocket
                    keepalive_task = asyncio.create_task(self._keepalive(websocket))
                    try:
                        async for raw_message in websocket:
                            if self._stopped:
                                break
                            json_message = await asyncio.to_thread(json.loads, raw_message)
                            if not self._start_inbound_task(self.client.background_task(json_message)):
                                if self.logger:
                                    await self.logger.warning(
                                        'DingTalk inbound task capacity reached; dropping message'
                                    )
                    finally:
                        keepalive_task.cancel()
                        try:
                            await keepalive_task
                        except asyncio.CancelledError:
                            pass
            except asyncio.CancelledError:
                # Properly exit when task is cancelled
                break
            except websockets.exceptions.ConnectionClosedError as e:
                if self._stopped:
                    break
                if self.logger:
                    await self.logger.error(f'DingTalk: connection closed, reconnecting... error={e}')
                await asyncio.sleep(5)
                continue
            except Exception as e:
                if self._stopped:
                    break
                if self.logger:
                    await self.logger.error(f'DingTalk: unknown exception, reconnecting... error={e}')
                await asyncio.sleep(3)
                continue

    async def _keepalive(self, ws, ping_interval=60):
        """Keep WebSocket connection alive"""
        while not self._stopped:
            await asyncio.sleep(ping_interval)
            try:
                await ws.ping()
            except websockets.exceptions.ConnectionClosed:
                break

    async def stop(self):
        """停止 WebSocket 连接"""
        self._stopped = True
        # Close WebSocket connection if exists
        if self.client.websocket:
            try:
                await self.client.websocket.close()
            except Exception:
                pass
        inbound_tasks = list(self._inbound_tasks)
        for task in inbound_tasks:
            if not task.done():
                task.cancel()
        if inbound_tasks:
            await asyncio.gather(*inbound_tasks, return_exceptions=True)
        self._inbound_tasks.clear()
        # Clear message handlers to prevent stale callbacks
        self._message_handlers = {'example': []}
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
