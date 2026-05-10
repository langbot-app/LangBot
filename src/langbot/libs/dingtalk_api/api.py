import asyncio
import base64
import json
import logging
import os
import time
import typing
import uuid
import urllib.parse
from typing import Awaitable, Callable, Optional
import dingtalk_stream  # type: ignore
import websockets
from .EchoHandler import EchoTextHandler
from .card_callback import DingTalkCardActionHandler
from .dingtalkevent import DingTalkEvent
import httpx
import traceback


_stdout_logger = logging.getLogger('langbot.dingtalk_api')


DINGTALK_OPENAPI_BASE = 'https://api.dingtalk.com'


def _stringify_card_param_map(card_param_map: Optional[dict]) -> dict:
    """DingTalk cardParamMap only accepts string values.

    Keep callers free to pass structured values for template variables such
    as button groups or select options, then encode them once at the API
    boundary.
    """
    if not card_param_map:
        return {}
    result = {}
    for key, value in card_param_map.items():
        if value is None:
            result[key] = ''
        elif isinstance(value, str):
            result[key] = value
        else:
            result[key] = json.dumps(value, ensure_ascii=False)
    return result


class DingTalkClient:
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
        self.robot_code = robot_code
        self.access_token_expiry_time = ''
        self.markdown_card = markdown_card
        self.logger = logger
        # Legacy access_token used by the OLD oapi.dingtalk.com endpoints
        # (e.g. /media/upload, which is the only documented way to get an
        # `@xxx` media_id usable in card Avatar.imageUrl). The new v1.0
        # token doesn't work there — different auth domain.
        self.legacy_access_token = ''
        self.legacy_access_token_expiry_time: typing.Optional[float] = None
        self._stopped = False  # Flag to control the event loop

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
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    response_data = response.json()
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
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
            else:
                await self.logger.error(f'failed to get download url: {response.json()}')

        if download_url:
            return await self.download_url_to_base64(download_url)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)

            if response.status_code == 200:
                file_bytes = response.content
                mime_type = response.headers.get('Content-Type', 'application/octet-stream')
                base64_str = base64.b64encode(file_bytes).decode('utf-8')
                return f'data:{mime_type};base64,{base64_str}'
            else:
                await self.logger.error(f'failed to get files: {response.json()}')

    async def get_audio_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
                if download_url:
                    return await self.download_url_to_base64(download_url)
                else:
                    await self.logger.error(f'failed to get audio: {response.json()}')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def get_file_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
                if download_url:
                    return download_url
                else:
                    await self.logger.error(f'failed to get file: {response.json()}')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def update_incoming_message(self, message):
        """异步更新 DingTalkClient 中的 incoming_message"""
        message_data = await self.get_message(message)
        if message_data:
            event = DingTalkEvent.from_payload(message_data)
            if event:
                await self._handle_message(event)

    async def send_message(self, content: str, incoming_message, at: bool):
        if self.markdown_card:
            if at:
                self.EchoTextHandler.reply_markdown(
                    title='@' + incoming_message.sender_nick + ' ' + content,
                    text='@' + incoming_message.sender_nick + ' ' + content,
                    incoming_message=incoming_message,
                )
            else:
                self.EchoTextHandler.reply_markdown(
                    title=content,
                    text=content,
                    incoming_message=incoming_message,
                )
        else:
            self.EchoTextHandler.reply_text(content, incoming_message)

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
            'msgParam': json.dumps({'content': content}),
        }
        _stdout_logger.info(
            'DingTalk send_proactive_message_to_one request: robotCode=%s target_id=%s content_len=%d',
            robot_code,
            target_id,
            len(content),
        )
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data)
                _stdout_logger.info(
                    'DingTalk send_proactive_message_to_one response: status=%d body=%s',
                    response.status_code,
                    response.text[:500],
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
            'msgParam': json.dumps({'content': content}),
        }
        try:
            async with httpx.AsyncClient() as client:
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
        temp_card_id: str,
        incoming_message: dingtalk_stream.ChatbotMessage,
        quote_origin: bool = False,
        card_auto_layout: bool = False,
    ):
        """Create + deliver the streaming chat card for a chatbot reply.

        Replaces the old `dingtalk_stream.AICardReplier`-based path. Returns
        `(None, out_track_id)` to keep call sites compatible with the
        previous `(card_instance, card_instance_id)` shape — the first slot
        is unused now that everything is driven by out_track_id.
        """
        out_track_id = uuid.uuid4().hex
        is_group = str(incoming_message.conversation_type) == '2'
        if is_group:
            open_space_id = f'dtv1.card//IM_GROUP.{incoming_message.conversation_id}'
        else:
            open_space_id = f'dtv1.card//IM_ROBOT.{incoming_message.sender_staff_id}'

        card_param_map = {'content': ''}
        if incoming_message.message_type == 'text':
            card_param_map['query'] = incoming_message.get_text_list()[0]
        else:
            card_param_map['query'] = '...'

        await self.create_and_deliver_card(
            card_template_id=temp_card_id,
            out_track_id=out_track_id,
            open_space_id=open_space_id,
            is_group=is_group,
            card_param_map=card_param_map,
            card_data_config={'autoLayout': card_auto_layout},
        )
        return None, out_track_id

    async def send_card_message(self, card_instance, card_instance_id: str, content: str, is_final: bool):
        """Stream a single chunk into an existing card's `content` field."""
        try:
            await self.streaming_update_card(
                out_track_id=card_instance_id,
                content_key='content',
                content_value=content,
                append=False,
                finished=is_final,
                failed=False,
            )
        except Exception as e:
            if self.logger:
                self.logger.exception(e)
            await self.streaming_update_card(
                out_track_id=card_instance_id,
                content_key='content',
                content_value='',
                append=False,
                finished=is_final,
                failed=True,
            )

    async def create_and_deliver_card(
        self,
        *,
        card_template_id: str,
        out_track_id: str,
        open_space_id: str,
        is_group: bool,
        card_param_map: Optional[dict] = None,
        callback_type: str = 'STREAM',
        callback_route_key: Optional[str] = None,
        support_forward: bool = True,
        dynamic_data_source_configs: Optional[list] = None,
        card_data_config: Optional[dict] = None,
        at_user_ids: Optional[dict] = None,
        recipients: Optional[list] = None,
    ) -> bool:
        """POST /v1.0/card/instances/createAndDeliver.

        Mirrors the SDK's `async_create_and_deliver_card` shape but exposes
        the dynamic-data-source config slot so we can register a pull URL
        for variable-length button lists.
        """
        if not await self.check_access_token():
            await self.get_access_token()

        cardData: dict = {'cardParamMap': _stringify_card_param_map(card_param_map)}
        if card_data_config is not None:
            cardData['config'] = json.dumps(card_data_config)

        body: dict = {
            'cardTemplateId': card_template_id,
            'outTrackId': out_track_id,
            'cardData': cardData,
            'callbackType': callback_type,
            'openSpaceId': open_space_id,
            'imGroupOpenSpaceModel': {'supportForward': support_forward},
            'imRobotOpenSpaceModel': {'supportForward': support_forward},
        }
        if callback_type == 'HTTP' and callback_route_key:
            body['callbackRouteKey'] = callback_route_key

        if is_group:
            deliver: dict = {'robotCode': self.robot_code or self.key}
            if at_user_ids:
                deliver['atUserIds'] = at_user_ids
            if recipients is not None:
                deliver['recipients'] = recipients
            body['imGroupOpenDeliverModel'] = deliver
        else:
            body['imRobotOpenDeliverModel'] = {'spaceType': 'IM_ROBOT'}

        if dynamic_data_source_configs:
            body['openDynamicDataConfig'] = {'dynamicDataSourceConfigs': dynamic_data_source_configs}

        url = f'{DINGTALK_OPENAPI_BASE}/v1.0/card/instances/createAndDeliver'
        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }
        try:
            _stdout_logger.info(
                'DingTalk createAndDeliver request body: %s',
                json.dumps(body, ensure_ascii=False)[:1500],
            )
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=body, timeout=30.0)
                if response.status_code == 200:
                    _stdout_logger.info(
                        'DingTalk createAndDeliver response: %s',
                        response.text[:500],
                    )
                    return True
                _stdout_logger.error(
                    'DingTalk createAndDeliver failed: status=%s body=%s',
                    response.status_code,
                    response.text,
                )
                if self.logger:
                    await self.logger.error(
                        f'DingTalk createAndDeliver failed: status={response.status_code} body={response.text}'
                    )
                return False
        except Exception:
            _stdout_logger.exception('DingTalk createAndDeliver error')
            if self.logger:
                await self.logger.error(f'DingTalk createAndDeliver error: {traceback.format_exc()}')
            return False

    async def streaming_update_card(
        self,
        *,
        out_track_id: str,
        content_key: str,
        content_value: str,
        append: bool,
        finished: bool,
        failed: bool = False,
    ) -> bool:
        """PUT /v1.0/card/streaming.

        Replaces `dingtalk_stream.AICardReplier.async_streaming` — same body
        shape (outTrackId / guid / key / content / isFull / isFinalize /
        isError) per the SDK source.
        """
        if not await self.check_access_token():
            await self.get_access_token()

        body = {
            'outTrackId': out_track_id,
            'guid': uuid.uuid4().hex,
            'key': content_key,
            'content': content_value,
            'isFull': not append,
            'isFinalize': finished,
            'isError': failed,
        }
        url = f'{DINGTALK_OPENAPI_BASE}/v1.0/card/streaming'
        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(url, headers=headers, json=body, timeout=30.0)
                if response.status_code == 200:
                    return True
                if self.logger:
                    await self.logger.error(
                        f'DingTalk card streaming failed: status={response.status_code} body={response.text}'
                    )
                return False
        except Exception:
            if self.logger:
                await self.logger.error(f'DingTalk card streaming error: {traceback.format_exc()}')
            return False

    async def update_card_data(
        self,
        *,
        out_track_id: str,
        card_param_map: Optional[dict] = None,
        private_data: Optional[dict] = None,
    ) -> bool:
        """PUT /v1.0/card/instances — non-streaming card content update."""
        if not await self.check_access_token():
            await self.get_access_token()

        body: dict = {
            'outTrackId': out_track_id,
            'cardData': {'cardParamMap': _stringify_card_param_map(card_param_map)},
        }
        if private_data:
            body['privateData'] = private_data

        url = f'{DINGTALK_OPENAPI_BASE}/v1.0/card/instances'
        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }
        try:
            _stdout_logger.info(
                'DingTalk update_card_data request: out_track_id=%s body=%s',
                out_track_id,
                json.dumps(body, ensure_ascii=False)[:1500],
            )
            async with httpx.AsyncClient() as client:
                response = await client.put(url, headers=headers, json=body, timeout=30.0)
                _stdout_logger.info(
                    'DingTalk update_card_data response: status=%d body=%s',
                    response.status_code,
                    response.text[:300],
                )
                if response.status_code == 200:
                    return True
                if self.logger:
                    await self.logger.error(
                        f'DingTalk update card failed: status={response.status_code} body={response.text}'
                    )
                return False
        except Exception:
            _stdout_logger.exception('DingTalk update_card_data error')
            if self.logger:
                await self.logger.error(f'DingTalk update card error: {traceback.format_exc()}')
            return False

    async def get_legacy_access_token(self) -> Optional[str]:
        """Fetch the LEGACY (oapi.dingtalk.com) access_token. This is a
        different auth domain from the v1.0 token cached in
        ``self.access_token`` — only the legacy token authorises the
        ``/media/upload`` endpoint that returns an ``@xxx`` media_id
        consumable by card components like Avatar.imageUrl.

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
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params={'appkey': self.key, 'appsecret': self.secret}, timeout=15.0)
            data = response.json() if response.status_code == 200 else {}
            if data.get('errcode') == 0 and data.get('access_token'):
                self.legacy_access_token = data['access_token']
                expires_in = int(data.get('expires_in', 7200))
                self.legacy_access_token_expiry_time = now + expires_in - 60
                return self.legacy_access_token
            if self.logger:
                await self.logger.error(
                    f'DingTalk legacy gettoken failed: status={response.status_code} body={response.text[:200]}'
                )
        except Exception:
            _stdout_logger.exception('DingTalk legacy gettoken error')
            if self.logger:
                await self.logger.error(f'DingTalk legacy gettoken error: {traceback.format_exc()}')
        return None

    async def upload_image_media(self, file_path: str) -> Optional[str]:
        """Upload an image file to DingTalk media storage and return the
        ``@xxx`` media_id, which can be passed straight into card variables
        like Avatar.imageUrl. Endpoint:

            POST https://oapi.dingtalk.com/media/upload?access_token=…&type=image

        Returns the media_id on success, None on any failure (caller
        should handle a None gracefully — DingTalk falls back to a
        default avatar when imageUrl is empty/unknown).
        """
        if not os.path.exists(file_path):
            if self.logger:
                await self.logger.error(f'DingTalk upload_image_media: file not found {file_path}')
            return None

        token = await self.get_legacy_access_token()
        if not token:
            return None

        url = 'https://oapi.dingtalk.com/media/upload'
        try:
            with open(file_path, 'rb') as f:
                file_bytes = f.read()
            file_name = os.path.basename(file_path)
            # Best-effort content-type guess; DingTalk accepts the major image
            # mime types and otherwise infers from the bytes.
            ext = os.path.splitext(file_name)[1].lower().lstrip('.')
            mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}.get(
                ext, 'application/octet-stream'
            )
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    params={'access_token': token, 'type': 'image'},
                    files={'media': (file_name, file_bytes, mime)},
                    timeout=30.0,
                )
            data = response.json() if response.status_code == 200 else {}
            if data.get('errcode') == 0 and data.get('media_id'):
                _stdout_logger.info('DingTalk upload_image_media OK: media_id=%s', data['media_id'])
                return data['media_id']
            if self.logger:
                await self.logger.error(
                    f'DingTalk upload_image_media failed: status={response.status_code} body={response.text[:300]}'
                )
        except Exception:
            _stdout_logger.exception('DingTalk upload_image_media error')
            if self.logger:
                await self.logger.error(f'DingTalk upload_image_media error: {traceback.format_exc()}')
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
                async with websockets.connect(uri) as websocket:
                    self.client.websocket = websocket
                    keepalive_task = asyncio.create_task(self._keepalive(websocket))
                    try:
                        async for raw_message in websocket:
                            if self._stopped:
                                break
                            json_message = json.loads(raw_message)
                            asyncio.create_task(self.client.background_task(json_message))
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
        # Clear message handlers to prevent stale callbacks
        self._message_handlers = {'example': []}
