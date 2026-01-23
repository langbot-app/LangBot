from __future__ import annotations

import lark_oapi
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody
import traceback
import typing
import asyncio
import re
import base64
import uuid
import json
import time
import datetime
import hashlib
from Crypto.Cipher import AES
import tempfile
import os
import mimetypes

import aiohttp
import lark_oapi.ws.exception
import quart
from lark_oapi.api.im.v1 import *
import pydantic
from lark_oapi.api.cardkit.v1 import *
from lark_oapi.api.auth.v3 import *
from lark_oapi.core.model import *

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class AESCipher(object):
    def __init__(self, key):
        self.bs = AES.block_size
        self.key = hashlib.sha256(AESCipher.str_to_bytes(key)).digest()

    @staticmethod
    def str_to_bytes(data):
        u_type = type(b''.decode('utf8'))
        if isinstance(data, u_type):
            return data.encode('utf8')
        return data

    @staticmethod
    def _unpad(s):
        return s[: -ord(s[len(s) - 1 :])]

    def decrypt(self, enc):
        iv = enc[: AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size :]))

    def decrypt_string(self, enc):
        enc = base64.b64decode(enc)
        return self.decrypt(enc).decode('utf8')


class LarkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def upload_image_to_lark(msg: platform_message.Image, api_client: lark_oapi.Client) -> typing.Optional[str]:
        """Upload an image to Lark and return the image_key, or None if upload fails."""
        image_bytes = None

        if msg.base64:
            try:
                # Remove data URL prefix if present
                base64_data = msg.base64
                if base64_data.startswith('data:'):
                    base64_data = base64_data.split(',', 1)[1]
                image_bytes = base64.b64decode(base64_data)
            except Exception as e:
                print(f'Failed to decode base64 image: {e}')
                traceback.print_exc()
                return None
        elif msg.url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(msg.url) as response:
                        if response.status == 200:
                            image_bytes = await response.read()
                        else:
                            print(f'Failed to download image from {msg.url}: HTTP {response.status}')
                            return None
            except Exception as e:
                print(f'Failed to download image from {msg.url}: {e}')
                traceback.print_exc()
                return None
        elif msg.path:
            try:
                with open(msg.path, 'rb') as f:
                    image_bytes = f.read()
            except Exception as e:
                print(f'Failed to read image from path {msg.path}: {e}')
                traceback.print_exc()
                return None

        if image_bytes is None:
            print(
                f'No image data available for Image message (url={msg.url}, base64={bool(msg.base64)}, path={msg.path})'
            )
            return None

        try:
            # Create a temporary file to store the image bytes
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_bytes)
                temp_file.flush()
                temp_file_path = temp_file.name

            try:
                # Create image request using the temporary file
                request = (
                    CreateImageRequest.builder()
                    .request_body(
                        CreateImageRequestBody.builder().image_type('message').image(open(temp_file_path, 'rb')).build()
                    )
                    .build()
                )

                response = await api_client.im.v1.image.acreate(request)

                if not response.success():
                    print(
                        f'client.im.v1.image.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}'
                    )
                    return None

                return response.data.image_key
            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)
        except Exception as e:
            print(f'Failed to upload image to Lark: {e}')
            traceback.print_exc()
            return None

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, api_client: lark_oapi.Client
    ) -> typing.Tuple[list, list]:
        """Convert message chain to Lark format.

        Returns:
            Tuple of (text_elements, image_keys):
            - text_elements: List of paragraphs for post message format
            - image_keys: List of image_key strings for separate image messages
        """
        message_elements = []
        image_keys = []
        pending_paragraph = []

        # Regex pattern to match Markdown image syntax: ![alt](url)
        markdown_image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

        async def process_text_with_images(text: str) -> typing.Tuple[str, list]:
            """Extract Markdown images from text and return cleaned text + image URLs."""
            extracted_urls = []

            # Find all Markdown images
            matches = list(markdown_image_pattern.finditer(text))
            if not matches:
                return text, []

            # Extract URLs and remove image syntax from text
            cleaned_text = text
            for match in reversed(matches):  # Reverse to maintain correct positions
                url = match.group(2)
                extracted_urls.insert(0, url)  # Insert at beginning since we're going in reverse
                # Replace image syntax with empty string or a placeholder
                cleaned_text = cleaned_text[: match.start()] + cleaned_text[match.end() :]

            # Clean up multiple consecutive newlines that might result from removing images
            cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
            cleaned_text = cleaned_text.strip()

            return cleaned_text, extracted_urls

        for msg in message_chain:
            if isinstance(msg, platform_message.Plain):
                # Ensure text is valid UTF-8
                try:
                    text = msg.text.encode('utf-8').decode('utf-8')
                except UnicodeError:
                    try:
                        text = msg.text.encode('latin1').decode('utf-8')
                    except UnicodeError:
                        text = msg.text.encode('utf-8', errors='replace').decode('utf-8')

                # Check for and extract Markdown images from text
                cleaned_text, extracted_urls = await process_text_with_images(text)

                # Add cleaned text if not empty
                if cleaned_text:
                    pending_paragraph.append({'tag': 'md', 'text': cleaned_text})

                # Process extracted image URLs
                for url in extracted_urls:
                    # Create a temporary Image message to upload
                    temp_image = platform_message.Image(url=url)
                    image_key = await LarkMessageConverter.upload_image_to_lark(temp_image, api_client)
                    if image_key:
                        image_keys.append(image_key)

            elif isinstance(msg, platform_message.At):
                pending_paragraph.append({'tag': 'at', 'user_id': msg.target, 'style': []})
            elif isinstance(msg, platform_message.AtAll):
                pending_paragraph.append({'tag': 'at', 'user_id': 'all', 'style': []})
            elif isinstance(msg, platform_message.Image):
                # Upload image and get image_key
                image_key = await LarkMessageConverter.upload_image_to_lark(msg, api_client)
                if image_key:
                    # Store image_key for separate image message
                    image_keys.append(image_key)
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    sub_elements, sub_image_keys = await LarkMessageConverter.yiri2target(
                        node.message_chain, api_client
                    )
                    message_elements.extend(sub_elements)
                    image_keys.extend(sub_image_keys)

        if pending_paragraph:
            message_elements.append(pending_paragraph)

        return message_elements, image_keys

    @staticmethod
    async def target2yiri(
        message: lark_oapi.api.im.v1.model.event_message.EventMessage,
        api_client: lark_oapi.Client,
    ) -> platform_message.MessageChain:
        message_content = json.loads(message.content)

        lb_msg_list = []

        msg_create_time = datetime.datetime.fromtimestamp(int(message.create_time) / 1000)

        lb_msg_list.append(platform_message.Source(id=message.message_id, time=msg_create_time))

        if message.message_type == 'text':
            element_list = []

            def text_element_recur(text_ele: dict) -> list[dict]:
                if text_ele['text'] == '':
                    return []

                at_pattern = re.compile(r'@_user_[\d]+')
                at_matches = at_pattern.findall(text_ele['text'])

                name_mapping = {}
                for mathc in at_matches:
                    for mention in message.mentions:
                        if mention.key == mathc:
                            name_mapping[mathc] = mention.name
                            break

                if len(name_mapping.keys()) == 0:
                    return [text_ele]

                # 只处理第一个，剩下的递归处理
                text_split = text_ele['text'].split(list(name_mapping.keys())[0])

                new_list = []

                left_text = text_split[0]
                right_text = text_split[1]

                new_list.extend(text_element_recur({'tag': 'text', 'text': left_text, 'style': []}))

                new_list.append(
                    {
                        'tag': 'at',
                        'user_id': list(name_mapping.keys())[0],
                        'user_name': name_mapping[list(name_mapping.keys())[0]],
                        'style': [],
                    }
                )

                new_list.extend(text_element_recur({'tag': 'text', 'text': right_text, 'style': []}))

                return new_list

            element_list = text_element_recur({'tag': 'text', 'text': message_content['text'], 'style': []})

            message_content = {'title': '', 'content': element_list}

        elif message.message_type == 'post':
            new_list = []

            for ele in message_content['content']:
                if type(ele) is dict:
                    new_list.append(ele)
                elif type(ele) is list:
                    new_list.extend(ele)

            message_content['content'] = new_list
        elif message.message_type == 'image':
            message_content['content'] = [{'tag': 'img', 'image_key': message_content['image_key'], 'style': []}]
        elif message.message_type == 'file':
            message_content['content'] = [
                {'tag': 'file', 'file_key': message_content['file_key'], 'file_name': message_content['file_name']}
            ]
        elif message.message_type == 'audio':
            message_content['content'] = [
                {
                    'tag': 'audio',
                    'file_key': message_content['file_key'],
                    'duration': message_content.get('duration', 0),
                }
            ]

        for ele in message_content['content']:
            if ele['tag'] == 'text':
                lb_msg_list.append(platform_message.Plain(text=ele['text']))
            elif ele['tag'] == 'at':
                lb_msg_list.append(platform_message.At(target=ele['user_name']))
            elif ele['tag'] == 'img':
                image_key = ele['image_key']

                request: GetMessageResourceRequest = (
                    GetMessageResourceRequest.builder()
                    .message_id(message.message_id)
                    .file_key(image_key)
                    .type('image')
                    .build()
                )

                response: GetMessageResourceResponse = await api_client.im.v1.message_resource.aget(request)

                if not response.success():
                    raise Exception(
                        f'client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                    )

                image_bytes = response.file.read()
                image_base64 = base64.b64encode(image_bytes).decode()

                image_format = response.raw.headers['content-type']

                lb_msg_list.append(platform_message.Image(base64=f'data:{image_format};base64,{image_base64}'))
            elif ele['tag'] == 'audio':
                file_key = ele['file_key']
                duration = ele['duration']

                # Download audio file
                request: GetMessageResourceRequest = (
                    GetMessageResourceRequest.builder()
                    .message_id(message.message_id)
                    .file_key(file_key)
                    .type('file')
                    .build()
                )

                try:
                    response: GetMessageResourceResponse = await api_client.im.v1.message_resource.aget(request)

                    if not response.success():
                        print(f'Failed to download audio: code: {response.code}, msg: {response.msg}')
                        lb_msg_list.append(platform_message.Plain(text='[Audio file download failed]'))
                        return platform_message.MessageChain(lb_msg_list)

                    # Read audio bytes
                    audio_bytes = response.file.read()
                    audio_base64 = base64.b64encode(audio_bytes).decode()

                    # Get content type from response headers
                    content_type = response.raw.headers.get('content-type', 'audio/mpeg')

                    mime_main = content_type.split(';')[0].strip()
                    ext = mimetypes.guess_extension(mime_main) or '.bin'
                    temp_dir = tempfile.gettempdir()
                    temp_file_path = os.path.join(temp_dir, f'lark_audio_{file_key}{ext}')

                    with open(temp_file_path, 'wb') as f:
                        f.write(audio_bytes)

                    # Create Voice message: prefer path/url + length, include base64 as optional data URI
                    lb_msg_list.append(
                        platform_message.Voice(
                            voice_id=file_key,
                            url=f'file://{temp_file_path}',
                            path=temp_file_path,
                            base64=f'data:{content_type};base64,{audio_base64}',
                            length=(duration // 1000) if duration else None,
                        )
                    )
                except Exception as e:
                    print(f'Error downloading audio: {e}')
                    traceback.print_exc()
                    lb_msg_list.append(platform_message.Plain(text='[Audio file download error]'))

            elif ele['tag'] == 'file':
                file_key = ele['file_key']
                file_name = ele['file_name']

                request: GetMessageResourceRequest = (
                    GetMessageResourceRequest.builder()
                    .message_id(message.message_id)
                    .file_key(file_key)
                    .type('file')
                    .build()
                )

                response: GetMessageResourceResponse = await api_client.im.v1.message_resource.aget(request)

                if not response.success():
                    raise Exception(
                        f'client.im.v1.message_resource.get failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                    )

                file_bytes = response.file.read()
                file_base64 = base64.b64encode(file_bytes).decode()

                file_format = response.raw.headers['content-type']

                file_size = len(file_bytes)

                # Determine extension from content-type if possible
                content_type = response.raw.headers.get('content-type', '')
                mime_main = content_type.split(';')[0].strip() if content_type else ''
                ext = mimetypes.guess_extension(mime_main) or ''

                # Ensure a safe filename (avoid path components)
                safe_name = os.path.basename(file_name).replace('/', '_').replace('\\', '_')
                if ext and not safe_name.lower().endswith(ext.lower()):
                    filename_with_ext = f'{safe_name}{ext}'
                else:
                    filename_with_ext = safe_name

                temp_dir = tempfile.gettempdir()
                temp_file_path = os.path.join(temp_dir, f'lark_{file_key}_{filename_with_ext}')

                with open(temp_file_path, 'wb') as f:
                    f.write(file_bytes)

                # Create File message with local path and file:// URL
                lb_msg_list.append(
                    platform_message.File(
                        id=file_key,
                        name=file_name,
                        size=file_size,
                        url=f'file://{temp_file_path}',
                        path=temp_file_path,
                        base64=f'data:{file_format};base64,{file_base64}',  # not including base64 by default to save memory; can be added if needed
                    )
                )

        return platform_message.MessageChain(lb_msg_list)


class LarkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(
        event: platform_events.MessageEvent,
    ) -> lark_oapi.im.v1.P2ImMessageReceiveV1:
        pass

    @staticmethod
    async def target2yiri(
        event: lark_oapi.im.v1.P2ImMessageReceiveV1, api_client: lark_oapi.Client
    ) -> platform_events.Event:
        message_chain = await LarkMessageConverter.target2yiri(event.event.message, api_client)

        if event.event.message.chat_type == 'p2p':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.event.sender.sender_id.open_id,
                    nickname=event.event.sender.sender_id.union_id,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
                source_platform_object=event,
            )
        elif event.event.message.chat_type == 'group':
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.event.sender.sender_id.open_id,
                    member_name=event.event.sender.sender_id.union_id,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.event.message.chat_id,
                        name='',
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
                source_platform_object=event,
            )


CARD_ID_CACHE_SIZE = 500
CARD_ID_CACHE_MAX_LIFETIME = 20 * 60  # 20分钟


class LarkAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: lark_oapi.ws.Client = pydantic.Field(exclude=True)
    api_client: lark_oapi.Client = pydantic.Field(exclude=True)

    bot_account_id: str  # 用于在流水线中识别at是否是本bot，直接以bot_name作为标识
    lark_tenant_key: str = pydantic.Field(exclude=True, default='')  # 飞书企业key

    message_converter: LarkMessageConverter = LarkMessageConverter()
    event_converter: LarkEventConverter = LarkEventConverter()
    cipher: AESCipher

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ]

    quart_app: quart.Quart = pydantic.Field(exclude=True)

    card_id_dict: dict[str, str]  # 消息id到卡片id的映射，便于创建卡片后的发送消息到指定卡片

    seq: int  # 用于在发送卡片消息中识别消息顺序，直接以seq作为标识
    bot_uuid: str = None  # 机器人UUID
    app_ticket: str = None  # 商店应用用到
    app_access_token: str = None  # 商店应用用到
    app_access_token_expire_at: int = None
    tenant_access_tokens: dict[str, dict[str, str]] = {}  # 租户access_token映射

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        quart_app = quart.Quart(__name__)

        async def on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            lb_event = await self.event_converter.target2yiri(event, self.api_client)

            await self.listeners[type(lb_event)](lb_event, self)

        def sync_on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            asyncio.create_task(on_message(event))

        event_handler = (
            lark_oapi.EventDispatcherHandler.builder('', '').register_p2_im_message_receive_v1(sync_on_message).build()
        )

        bot_account_id = config['bot_name']

        bot = lark_oapi.ws.Client(config['app_id'], config['app_secret'], event_handler=event_handler)
        api_client = self.build_api_client(config)
        cipher = AESCipher(config.get('encrypt-key', ''))
        self.request_app_ticket(api_client, config)

        super().__init__(
            config=config,
            logger=logger,
            lark_tenant_key=config.get('lark_tenant_key', ''),
            card_id_dict={},
            seq=1,
            listeners={},
            quart_app=quart_app,
            bot=bot,
            api_client=api_client,
            bot_account_id=bot_account_id,
            cipher=cipher,
            **kwargs,
        )

    def request_app_ticket(self, api_client, config):
        app_id = config['app_id']
        app_secret = config['app_secret']
        print(f'Requesting app ticket for app_id: {app_id[:3]}***{app_id[-3:]}')
        if 'isv' == config.get('app_type', 'self'):
            request: ResendAppTicketRequest = (
                ResendAppTicketRequest.builder()
                .request_body(ResendAppTicketRequestBody.builder().app_id(app_id).app_secret(app_secret).build())
                .build()
            )
            response: ResendAppTicketResponse = api_client.auth.v3.app_ticket.resend(request)
            if not response.success():
                raise Exception(
                    f'client.auth.v3.auth.app_ticket_resend failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

    def request_app_access_token(self):
        app_id = self.config['app_id']
        app_secret = self.config['app_secret']
        if 'isv' == self.config.get('app_type', 'self'):
            request: CreateAppAccessTokenRequest = (
                CreateAppAccessTokenRequest.builder()
                .request_body(
                    CreateAppAccessTokenRequestBody.builder()
                    .app_id(app_id)
                    .app_secret(app_secret)
                    .app_ticket(self.app_ticket)
                    .build()
                )
                .build()
            )
            response: CreateAppAccessTokenResponse = self.api_client.auth.v3.app_access_token.create(request)
            if not response.success():
                raise Exception(
                    f'client.auth.v3.auth.app_access_token failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )
            content = json.loads(response.raw.content)
            self.app_access_token = content['app_access_token']
            self.app_access_token_expire_at = int(time.time()) + content['expire'] - 300

    def get_app_access_token(self):
        if 'isv' != self.config.get('app_type', 'self'):
            return None
        if (
            self.app_access_token is None
            or self.app_access_token_expire_at is None
            or int(time.time()) >= self.app_access_token_expire_at
        ):
            self.request_app_access_token()
        return self.app_access_token

    def request_tenant_access_token(self, tenant_key: str):
        app_access_token = self.get_app_access_token()
        if 'isv' == self.config.get('app_type', 'self'):
            request: CreateTenantAccessTokenRequest = (
                CreateTenantAccessTokenRequest.builder()
                .request_body(
                    CreateTenantAccessTokenRequestBody.builder()
                    .app_access_token(app_access_token)
                    .tenant_key(tenant_key)
                    .build()
                )
                .build()
            )
            response: CreateTenantAccessTokenResponse = self.api_client.auth.v3.tenant_access_token.create(request)
            if not response.success():
                raise Exception(
                    f'client.auth.v3.auth.tenant_access_token failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )
            content = json.loads(response.raw.content)
            tenant_access_token = content['tenant_access_token']
            expire = content['expire']
            self.tenant_access_tokens[tenant_key] = {
                'token': tenant_access_token,
                'expire_at': int(time.time()) + expire - 300,
            }

    def get_tenant_access_token(self, tenant_key: str):
        if tenant_key is None or 'isv' != self.config.get('app_type', 'self'):
            return None
        tenant_access_token = self.tenant_access_tokens.get(tenant_key)
        if tenant_access_token is None or int(time.time()) >= tenant_access_token['expire_at']:
            self.request_tenant_access_token(tenant_key)
        return self.tenant_access_tokens.get(tenant_key)['token'] if self.tenant_access_tokens.get(tenant_key) else None

    def build_api_client(self, config):
        app_id = config['app_id']
        app_secret = config['app_secret']
        api_client = lark_oapi.Client.builder().app_id(app_id).app_secret(app_secret).build()
        if 'isv' == config.get('app_type', 'self'):
            api_client = (
                lark_oapi.Client.builder().app_id(app_id).app_secret(app_secret).app_type(lark_oapi.AppType.ISV).build()
            )
        return api_client

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def create_card_id(self, message_id):
        try:
            # self.logger.debug('飞书支持stream输出,创建卡片......')

            card_data = {
                'schema': '2.0',
                'config': {
                    'update_multi': True,
                    'streaming_mode': True,
                    'streaming_config': {
                        'print_step': {'default': 1},
                        'print_frequency_ms': {'default': 70},
                        'print_strategy': 'fast',
                    },
                },
                'body': {
                    'direction': 'vertical',
                    'padding': '12px 12px 12px 12px',
                    'elements': [
                        {
                            'tag': 'div',
                            'text': {
                                'tag': 'plain_text',
                                'content': 'LangBot',
                                'text_size': 'normal',
                                'text_align': 'left',
                                'text_color': 'default',
                            },
                            'icon': {
                                'tag': 'custom_icon',
                                'img_key': 'img_v3_02p3_05c65d5d-9bad-440a-a2fb-c89571bfd5bg',
                            },
                        },
                        {
                            'tag': 'markdown',
                            'content': '',
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 0px 0px',
                            'element_id': 'streaming_txt',
                        },
                        {
                            'tag': 'markdown',
                            'content': '',
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 0px 0px',
                        },
                        {
                            'tag': 'column_set',
                            'horizontal_spacing': '8px',
                            'horizontal_align': 'left',
                            'columns': [
                                {
                                    'tag': 'column',
                                    'width': 'weighted',
                                    'elements': [
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                        {
                                            'tag': 'markdown',
                                            'content': '',
                                            'text_align': 'left',
                                            'text_size': 'normal',
                                            'margin': '0px 0px 0px 0px',
                                        },
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '2px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                    'weight': 1,
                                }
                            ],
                            'margin': '0px 0px 0px 0px',
                        },
                        {'tag': 'hr', 'margin': '0px 0px 0px 0px'},
                        {
                            'tag': 'column_set',
                            'horizontal_spacing': '12px',
                            'horizontal_align': 'right',
                            'columns': [
                                {
                                    'tag': 'column',
                                    'width': 'weighted',
                                    'elements': [
                                        {
                                            'tag': 'markdown',
                                            'content': '<font color="grey-600">以上内容由 AI 生成，仅供参考。更多详细、准确信息可点击引用链接查看</font>',
                                            'text_align': 'left',
                                            'text_size': 'notation',
                                            'margin': '4px 0px 0px 0px',
                                            'icon': {
                                                'tag': 'standard_icon',
                                                'token': 'robot_outlined',
                                                'color': 'grey',
                                            },
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                    'weight': 1,
                                },
                                {
                                    'tag': 'column',
                                    'width': '20px',
                                    'elements': [
                                        {
                                            'tag': 'button',
                                            'text': {'tag': 'plain_text', 'content': ''},
                                            'type': 'text',
                                            'width': 'fill',
                                            'size': 'medium',
                                            'icon': {'tag': 'standard_icon', 'token': 'thumbsup_outlined'},
                                            'hover_tips': {'tag': 'plain_text', 'content': '有帮助'},
                                            'margin': '0px 0px 0px 0px',
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'direction': 'vertical',
                                    'horizontal_spacing': '8px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                },
                                {
                                    'tag': 'column',
                                    'width': '30px',
                                    'elements': [
                                        {
                                            'tag': 'button',
                                            'text': {'tag': 'plain_text', 'content': ''},
                                            'type': 'text',
                                            'width': 'default',
                                            'size': 'medium',
                                            'icon': {'tag': 'standard_icon', 'token': 'thumbdown_outlined'},
                                            'hover_tips': {'tag': 'plain_text', 'content': '无帮助'},
                                            'margin': '0px 0px 0px 0px',
                                        }
                                    ],
                                    'padding': '0px 0px 0px 0px',
                                    'vertical_spacing': '8px',
                                    'horizontal_align': 'left',
                                    'vertical_align': 'top',
                                    'margin': '0px 0px 0px 0px',
                                },
                            ],
                            'margin': '0px 0px 4px 0px',
                        },
                    ],
                },
            }
            # delay / fast 创建卡片模板，delay 延迟打印，fast 实时打印，可以自定义更好看的消息模板

            request: CreateCardRequest = (
                CreateCardRequest.builder()
                .request_body(CreateCardRequestBody.builder().type('card_json').data(json.dumps(card_data)).build())
                .build()
            )

            # 发起请求
            response: CreateCardResponse = self.api_client.cardkit.v1.card.create(request)

            # 处理失败返回
            if not response.success():
                raise Exception(
                    f'client.cardkit.v1.card.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

            self.card_id_dict[message_id] = response.data.card_id

            card_id = response.data.card_id
            return card_id

        except Exception as e:
            raise e

    async def create_message_card(self, message_id, event) -> str:
        """
        创建卡片消息。
        使用卡片消息是因为普通消息更新次数有限制，而大模型流式返回结果可能很多而超过限制，而飞书卡片没有这个限制（api免费次数有限）
        """
        # message_id = event.message_chain.message_id

        card_id = await self.create_card_id(message_id)
        content = {
            'type': 'card',
            'data': {'card_id': card_id, 'template_variable': {'content': 'Thinking...'}},
        }  # 当收到消息时发送消息模板，可添加模板变量，详情查看飞书中接口文档
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(event.message_chain.message_id)
            .request_body(
                ReplyMessageRequestBody.builder().content(json.dumps(content)).msg_type('interactive').build()
            )
            .build()
        )
        tenant_key = event.source_platform_object.header.tenant_key if event.source_platform_object else None
        app_access_token = self.get_app_access_token()
        tenant_access_token = self.get_tenant_access_token(tenant_key)
        req_opt: RequestOption = (
            RequestOption.builder()
            .app_ticket(self.app_ticket)
            .tenant_key(tenant_key)
            .app_access_token(app_access_token)
            .tenant_access_token(tenant_access_token)
            .build()
        )
        # 发起请求
        response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request, req_opt)

        # 处理失败返回
        if not response.success():
            raise Exception(
                f'client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
            )
        return True

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        # 不再需要了，因为message_id已经被包含到message_chain中
        # lark_event = await self.event_converter.yiri2target(message_source)
        text_elements, image_keys = await self.message_converter.yiri2target(message, self.api_client)

        # Send text message if there are text elements
        if text_elements:
            final_content = {
                'zh_Hans': {
                    'title': '',
                    'content': text_elements,
                },
            }
            request: ReplyMessageRequest = (
                ReplyMessageRequest.builder()
                .message_id(message_source.message_chain.message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(json.dumps(final_content))
                    .msg_type('post')
                    .reply_in_thread(False)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )

            tenant_key = (
                message_source.source_platform_object.header.tenant_key
                if message_source.source_platform_object
                else None
            )
            app_access_token = self.get_app_access_token()
            tenant_access_token = self.get_tenant_access_token(tenant_key)
            req_opt: RequestOption = (
                RequestOption.builder()
                .app_ticket(self.app_ticket)
                .tenant_key(tenant_key)
                .app_access_token(app_access_token)
                .tenant_access_token(tenant_access_token)
                .build()
            )
            response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request, req_opt)

            if not response.success():
                raise Exception(
                    f'client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

        # Send image messages separately using msg_type='image'
        for image_key in image_keys:
            image_content = json.dumps({'image_key': image_key})

            request: ReplyMessageRequest = (
                ReplyMessageRequest.builder()
                .message_id(message_source.message_chain.message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(image_content)
                    .msg_type('image')
                    .reply_in_thread(False)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )

            tenant_key = (
                message_source.source_platform_object.header.tenant_key
                if message_source.source_platform_object
                else None
            )
            app_access_token = self.get_app_access_token()
            tenant_access_token = self.get_tenant_access_token(tenant_key)
            req_opt: RequestOption = (
                RequestOption.builder()
                .app_ticket(self.app_ticket)
                .tenant_key(tenant_key)
                .app_access_token(app_access_token)
                .tenant_access_token(tenant_access_token)
                .build()
            )
            response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request, req_opt)

            if not response.success():
                raise Exception(
                    f'client.im.v1.message.reply (image) failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        """
        回复消息变成更新卡片消息
        """
        # self.seq += 1
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence
        if msg_seq % 8 == 0 or is_final:
            text_elements, image_keys = await self.message_converter.yiri2target(message, self.api_client)

            text_message = ''
            if text_elements:
                for ele in text_elements[0]:
                    if ele['tag'] == 'text':
                        text_message += ele['text']
                    elif ele['tag'] == 'md':
                        text_message += ele['text']

            # content = {
            #     'type': 'card_json',
            #     'data': {'card_id': self.card_id_dict[message_id], 'elements': {'content': text_message}},
            # }

            request: ContentCardElementRequest = (
                ContentCardElementRequest.builder()
                .card_id(self.card_id_dict[message_id])
                .element_id('streaming_txt')
                .request_body(
                    ContentCardElementRequestBody.builder()
                    # .uuid("a0d69e20-1dd1-458b-k525-dfeca4015204")
                    .content(text_message)
                    .sequence(msg_seq)
                    .build()
                )
                .build()
            )

            if is_final and bot_message.tool_calls is None:
                # self.seq = 1  # 消息回复结束之后重置seq
                self.card_id_dict.pop(message_id)  # 清理已经使用过的卡片

            tenant_key = (
                message_source.source_platform_object.header.tenant_key
                if message_source.source_platform_object
                else None
            )
            app_access_token = self.get_app_access_token()
            tenant_access_token = self.get_tenant_access_token(tenant_key)
            req_opt: RequestOption = (
                RequestOption.builder()
                .app_ticket(self.app_ticket)
                .tenant_key(tenant_key)
                .app_access_token(app_access_token)
                .tenant_access_token(tenant_access_token)
                .build()
            )
            # 发起请求
            response: ContentCardElementResponse = self.api_client.cardkit.v1.card_element.content(request, req_opt)

            # 处理失败返回
            if not response.success():
                raise Exception(
                    f'client.im.v1.message.patch failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )
                return

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners.pop(event_type)

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

    def get_event_type(self, data):
        schema = '1.0'
        if 'schema' in data:
            schema = data['schema']
        if '2.0' == schema:
            return data['header']['event_type']
        elif 'event' in data:
            return data['event']['type']
        else:
            return data['type']

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        """处理统一 webhook 请求。
        Args:
            bot_uuid: Bot 的 UUID
            path: 子路径（如果有的话）
            request: Quart Request 对象
        Returns:
            响应数据
        """
        try:
            data = await request.json

            if 'encrypt' in data:
                data = self.cipher.decrypt_string(data['encrypt'])
                data = json.loads(data)
            type = self.get_event_type(data)
            context = EventContext(data)
            if 'url_verification' == type:
                # todo 验证verification token
                return {'challenge': data.get('challenge')}
            elif 'app_ticket' == type:
                self.app_ticket = context.event['app_ticket']
            elif 'im.message.receive_v1' == type:
                try:
                    p2v1 = P2ImMessageReceiveV1()
                    p2v1.header = context.header
                    event = P2ImMessageReceiveV1Data()
                    event.message = EventMessage(context.event['message'])
                    event.sender = EventSender(context.event['sender'])
                    p2v1.event = event
                    p2v1.schema = context.schema
                    event = await self.event_converter.target2yiri(p2v1, self.api_client)
                except Exception:
                    await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')

                if event.__class__ in self.listeners:
                    await self.listeners[event.__class__](event, self)
            elif 'im.chat.member.bot.added_v1' == type:
                try:
                    bot_added_welcome_msg = self.config.get('bot_added_welcome', '')
                    if bot_added_welcome_msg:
                        final_content = {
                            'zh_Hans': {
                                'title': '',
                                'content': [[{'tag': 'md', 'text': bot_added_welcome_msg}]],
                            },
                        }
                        chat_id = context.event['chat_id']
                        request: CreateMessageRequest = (
                            CreateMessageRequest.builder()
                            .receive_id_type('chat_id')
                            .request_body(
                                CreateMessageRequestBody.builder()
                                .receive_id(chat_id)
                                .content(json.dumps(final_content))
                                .msg_type('post')
                                .uuid(str(uuid.uuid4()))
                                .build()
                            )
                            .build()
                        )
                        tenant_key = context.header.tenant_key if context.header else None
                        app_access_token = self.get_app_access_token()
                        tenant_access_token = self.get_tenant_access_token(tenant_key)
                        req_opt: RequestOption = (
                            RequestOption.builder()
                            .app_ticket(self.app_ticket)
                            .tenant_key(tenant_key)
                            .app_access_token(app_access_token)
                            .tenant_access_token(tenant_access_token)
                            .build()
                        )
                        response: CreateMessageResponse = self.api_client.im.v1.message.create(request, req_opt)

                        if not response.success():
                            raise Exception(
                                f'client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                            )
                except Exception as e:
                    print(f'im.chat.member.bot.added_v1: {e}')
                    await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')

            return {'code': 200, 'message': 'ok'}
        except Exception as e:
            print(f'Error in lark callback: {e}')
            await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')
            return {'code': 500, 'message': 'error'}

    async def run_async(self):
        enable_webhook = self.config['enable-webhook']

        if not enable_webhook:
            try:
                await self.bot._connect()
            except lark_oapi.ws.exception.ClientException as e:
                raise e
            except Exception as e:
                await self.bot._disconnect()
                if self.bot._auto_reconnect:
                    await self.bot._reconnect()
                else:
                    raise e
        else:
            # 统一 webhook 模式下，不启动独立的 Quart 应用
            # 保持运行但不启动独立端口

            async def keep_alive():
                while True:
                    await asyncio.sleep(1)

            await keep_alive()

    async def kill(self) -> bool:
        # 需要断开连接，不然旧的连接会继续运行，导致飞书消息来时会随机选择一个连接
        # 断开时lark.ws.Client的_receive_message_loop会打印error日志: receive message loop exit。然后进行重连，
        # 所以要设置_auto_reconnect=False,让其不重连。
        self.bot._auto_reconnect = False
        await self.bot._disconnect()
        return False
