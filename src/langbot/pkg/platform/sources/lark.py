from __future__ import annotations

import lark_oapi
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody, CreateFileRequest, CreateFileRequestBody
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

from langbot.pkg.utils import httpclient
from langbot.pkg.platform import custom_events
import lark_oapi.ws.exception
import quart
from lark_oapi.api.im.v1 import *
import pydantic
from lark_oapi.api.cardkit.v1 import *
from lark_oapi.api.auth.v3 import *
from lark_oapi.api.contact.v3 import GetUserRequest, GetUserResponse
from lark_oapi.core.model import *

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.provider.session as provider_session
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
                session = httpclient.get_session()
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
    async def upload_file_to_lark(
        file_bytes: bytes,
        api_client: lark_oapi.Client,
        file_type: str,
        file_name: str = 'file',
        duration: typing.Optional[int] = None,
    ) -> typing.Optional[str]:
        """Upload a file to Lark and return the file_key, or None if upload fails.

        Args:
            file_bytes: Raw file bytes.
            api_client: Lark API client.
            file_type: Lark file type, e.g. 'opus', 'mp4', 'pdf', 'doc', etc.
            file_name: Display name for the file.
            duration: Duration in milliseconds (for audio files).
        """
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name

            try:
                body_builder = (
                    CreateFileRequestBody.builder()
                    .file_type(file_type)
                    .file_name(file_name)
                    .file(open(temp_file_path, 'rb'))
                )
                if duration is not None:
                    body_builder = body_builder.duration(duration)

                request = CreateFileRequest.builder().request_body(body_builder.build()).build()

                response = await api_client.im.v1.file.acreate(request)

                if not response.success():
                    print(
                        f'client.im.v1.file.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}'
                    )
                    return None

                return response.data.file_key
            finally:
                os.unlink(temp_file_path)
        except Exception as e:
            print(f'Failed to upload file to Lark: {e}')
            traceback.print_exc()
            return None

    @staticmethod
    async def _get_media_bytes(
        msg: typing.Union[platform_message.Voice, platform_message.File],
    ) -> typing.Optional[bytes]:
        """Get bytes from a Voice or File message (base64, url, or path)."""
        data = None

        if msg.base64:
            try:
                base64_str = msg.base64
                if ',' in base64_str:
                    base64_str = base64_str.split(',', 1)[1]
                data = base64.b64decode(base64_str)
            except Exception:
                pass
        elif msg.url:
            try:
                session = httpclient.get_session()
                async with session.get(msg.url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
            except Exception:
                pass
        elif msg.path:
            try:
                with open(msg.path, 'rb') as f:
                    data = f.read()
            except Exception:
                pass

        return data

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain, api_client: lark_oapi.Client
    ) -> typing.Tuple[list, list]:
        """Convert message chain to Lark format.

        Returns:
            Tuple of (text_elements, image_keys):
            - text_elements: List of paragraphs for post message format
            - media_items: List of dicts with 'msg_type' and 'content' for separate media messages
        """
        message_elements = []
        media_items = []
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

                # Split by blank lines to create separate paragraphs for Lark post format.
                # Lark truncates md elements at the first \n\n, so we must use the
                # post format's native paragraph structure instead.
                if cleaned_text:
                    segments = re.split(r'\n\s*\n', cleaned_text)
                    for i, segment in enumerate(segments):
                        segment = segment.strip()
                        if not segment:
                            continue
                        if i > 0 and pending_paragraph:
                            message_elements.append(pending_paragraph)
                            pending_paragraph = []
                        pending_paragraph.append({'tag': 'md', 'text': segment})

                # Process extracted image URLs
                for url in extracted_urls:
                    temp_image = platform_message.Image(url=url)
                    image_key = await LarkMessageConverter.upload_image_to_lark(temp_image, api_client)
                    if image_key:
                        media_items.append({'msg_type': 'image', 'content': {'image_key': image_key}})

            elif isinstance(msg, platform_message.At):
                pending_paragraph.append({'tag': 'at', 'user_id': msg.target, 'style': []})
            elif isinstance(msg, platform_message.AtAll):
                pending_paragraph.append({'tag': 'at', 'user_id': 'all', 'style': []})
            elif isinstance(msg, platform_message.Image):
                image_key = await LarkMessageConverter.upload_image_to_lark(msg, api_client)
                if image_key:
                    media_items.append({'msg_type': 'image', 'content': {'image_key': image_key}})
            elif isinstance(msg, platform_message.Voice):
                data = await LarkMessageConverter._get_media_bytes(msg)
                if data:
                    duration = int(msg.length * 1000) if msg.length else None
                    file_key = await LarkMessageConverter.upload_file_to_lark(
                        data, api_client, file_type='opus', file_name='voice.opus', duration=duration
                    )
                    if file_key:
                        media_items.append({'msg_type': 'audio', 'content': {'file_key': file_key}})
            elif isinstance(msg, platform_message.File):
                data = await LarkMessageConverter._get_media_bytes(msg)
                if data:
                    file_name = msg.name or 'file'
                    # Guess file_type from extension
                    ext = os.path.splitext(file_name)[1].lstrip('.').lower() if file_name else ''
                    file_type_map = {
                        'opus': 'opus',
                        'mp4': 'mp4',
                        'pdf': 'pdf',
                        'doc': 'doc',
                        'docx': 'doc',
                        'xls': 'xls',
                        'xlsx': 'xls',
                        'ppt': 'ppt',
                        'pptx': 'ppt',
                    }
                    file_type = file_type_map.get(ext, 'stream')
                    file_key = await LarkMessageConverter.upload_file_to_lark(
                        data, api_client, file_type=file_type, file_name=file_name
                    )
                    if file_key:
                        media_items.append({'msg_type': 'file', 'content': {'file_key': file_key}})
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    sub_elements, sub_media = await LarkMessageConverter.yiri2target(node.message_chain, api_client)
                    message_elements.extend(sub_elements)
                    media_items.extend(sub_media)

        if pending_paragraph:
            message_elements.append(pending_paragraph)

        return message_elements, media_items

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
        event: lark_oapi.im.v1.P2ImMessageReceiveV1,
        api_client: lark_oapi.Client,
        adapter: LarkAdapter | None = None,
    ) -> platform_events.Event:
        message_chain = await LarkMessageConverter.target2yiri(event.event.message, api_client)
        sender_id = event.event.sender.sender_id
        sender_open_id = getattr(sender_id, 'open_id', '')
        sender_union_id = getattr(sender_id, 'union_id', '')
        sender_user_id = getattr(sender_id, 'user_id', '')
        sender_primary_id = sender_open_id or sender_user_id or sender_union_id
        sender_name = sender_union_id or sender_user_id or sender_open_id

        if adapter is not None:
            resolved_name = await adapter.resolve_event_sender_name(event)
            if resolved_name:
                sender_name = resolved_name

        if event.event.message.chat_type == 'p2p':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=sender_primary_id,
                    nickname=sender_name,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.event.message.create_time,
                source_platform_object=event,
            )
        elif event.event.message.chat_type == 'group':
            group_id = event.event.message.chat_id
            group_name = ''
            if adapter is not None:
                resolved_group_name = await adapter.resolve_chat_name(group_id, event)
                if resolved_group_name:
                    group_name = resolved_group_name

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_primary_id,
                    member_name=sender_name,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=group_id,
                        name=group_name,
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
USER_NAME_CACHE_SIZE = 2000
USER_NAME_CACHE_MAX_LIFETIME = 24 * 60 * 60  # 24小时
CHAT_NAME_CACHE_SIZE = 1000
CHAT_NAME_CACHE_MAX_LIFETIME = 24 * 60 * 60  # 24小时
MESSAGE_RECALL_CACHE_SIZE = 4000
MESSAGE_RECALL_CACHE_MAX_LIFETIME = 24 * 60 * 60


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
    user_name_cache: dict[str, dict[str, typing.Any]] = {}
    chat_name_cache: dict[str, dict[str, typing.Any]] = {}
    message_recall_cache: dict[str, dict[str, typing.Any]] = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        quart_app = quart.Quart(__name__)

        async def on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            lb_event = await self.event_converter.target2yiri(event, self.api_client, self)
            self._cache_message_for_recall(lb_event)

            if lb_event.__class__ in self.listeners:
                await self.listeners[lb_event.__class__](lb_event, self)

        async def on_message_recalled(event: lark_oapi.im.v1.P2ImMessageRecalledV1):
            recalled_event = self._build_recalled_platform_event(event)
            if recalled_event is None:
                return

            if recalled_event.__class__ in self.listeners:
                await self.listeners[recalled_event.__class__](recalled_event, self)

        def sync_on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            asyncio.create_task(on_message(event))

        def sync_on_message_recalled(event: lark_oapi.im.v1.P2ImMessageRecalledV1):
            asyncio.create_task(on_message_recalled(event))

        event_handler = (
            lark_oapi.EventDispatcherHandler.builder('', '')
            .register_p2_im_message_receive_v1(sync_on_message)
            .register_p2_im_message_recalled_v1(sync_on_message_recalled)
            .build()
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
            user_name_cache={},
            chat_name_cache={},
            message_recall_cache={},
            **kwargs,
        )

    @staticmethod
    def _get_chat_id_from_source_event(message_event: platform_events.MessageEvent) -> str:
        source_obj = getattr(message_event, 'source_platform_object', None)
        if source_obj is None:
            return ''

        try:
            return str(source_obj.event.message.chat_id).strip()
        except Exception:
            return ''

    def _cleanup_message_recall_cache(self) -> None:
        now_ts = time.time()
        expired_keys = [
            key
            for key, item in self.message_recall_cache.items()
            if now_ts - float(item.get('created_at', now_ts)) > MESSAGE_RECALL_CACHE_MAX_LIFETIME
        ]
        for key in expired_keys:
            self.message_recall_cache.pop(key, None)

        if len(self.message_recall_cache) <= MESSAGE_RECALL_CACHE_SIZE:
            return

        sorted_items = sorted(
            self.message_recall_cache.items(),
            key=lambda kv: float(kv[1].get('created_at', now_ts)),
        )
        overflow_count = len(self.message_recall_cache) - MESSAGE_RECALL_CACHE_SIZE
        for key, _ in sorted_items[:overflow_count]:
            self.message_recall_cache.pop(key, None)

    def _cache_message_for_recall(self, message_event: platform_events.Event) -> None:
        if not isinstance(message_event, (platform_events.FriendMessage, platform_events.GroupMessage)):
            return

        message_id = str(message_event.message_chain.message_id).strip()
        if not message_id or message_id == '-1':
            return

        if isinstance(message_event, platform_events.GroupMessage):
            launcher_type = provider_session.LauncherTypes.GROUP
            launcher_id = message_event.group.id
            sender_id = message_event.sender.id
            chat_id = str(message_event.group.id)
        else:
            launcher_type = provider_session.LauncherTypes.PERSON
            launcher_id = message_event.sender.id
            sender_id = message_event.sender.id
            chat_id = self._get_chat_id_from_source_event(message_event)

        self.message_recall_cache[message_id] = {
            'created_at': time.time(),
            'launcher_type': launcher_type,
            'launcher_id': str(launcher_id),
            'sender_id': str(sender_id),
            'chat_id': chat_id,
            'message_event': message_event,
        }
        self._cleanup_message_recall_cache()

    @staticmethod
    def _parse_recall_time(recall_time_raw: typing.Any) -> datetime.datetime:
        recall_time_text = str(recall_time_raw or '').strip()
        if not recall_time_text:
            return datetime.datetime.now()

        try:
            ts = float(recall_time_text)
            if ts > 1e12:
                ts = ts / 1000.0
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            pass

        try:
            return datetime.datetime.fromisoformat(recall_time_text)
        except Exception:
            return datetime.datetime.now()

    def _build_recalled_platform_event(
        self, recalled_event: lark_oapi.api.im.v1.P2ImMessageRecalledV1
    ) -> custom_events.MessageRecalled | None:
        event_data = getattr(recalled_event, 'event', None)
        if event_data is None:
            return None

        message_id = str(getattr(event_data, 'message_id', '')).strip()
        if not message_id:
            return None

        chat_id = str(getattr(event_data, 'chat_id', '')).strip()
        cached = self.message_recall_cache.pop(message_id, None)
        if cached is None and chat_id:
            fallback_candidates = [
                item
                for item in self.message_recall_cache.values()
                if str(item.get('chat_id', '')).strip() == chat_id
            ]
            if fallback_candidates:
                cached = max(fallback_candidates, key=lambda item: float(item.get('created_at', 0.0)))
        if cached is None:
            return None

        recall_time = str(getattr(event_data, 'recall_time', '')).strip()
        recall_type = str(getattr(event_data, 'recall_type', '')).strip()
        chat_id = chat_id or str(cached.get('chat_id', '')).strip()
        recall_dt = self._parse_recall_time(recall_time)
        recall_chain = platform_message.MessageChain([platform_message.Source(id=message_id, time=recall_dt)])

        launcher_type = cached.get('launcher_type')
        if not isinstance(launcher_type, provider_session.LauncherTypes):
            return None

        original_event = cached.get('message_event')
        if not isinstance(original_event, platform_events.MessageEvent):
            return None

        return custom_events.MessageRecalled(
            message_id=message_id,
            chat_id=chat_id,
            recall_time=recall_time,
            recall_type=recall_type,
            launcher_type=launcher_type,
            launcher_id=str(cached.get('launcher_id', '')),
            sender_id=str(cached.get('sender_id', '')),
            message_event=original_event,
            message_chain=recall_chain,
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

    def _get_cached_user_name(self, id_type: str, id_value: str) -> str | None:
        cache_key = f'{id_type}:{id_value}'
        cache_item = self.user_name_cache.get(cache_key)
        if cache_item is None:
            return None

        expire_at = cache_item.get('expire_at', 0)
        if int(time.time()) >= expire_at:
            self.user_name_cache.pop(cache_key, None)
            return None

        cached_name = cache_item.get('name')
        if isinstance(cached_name, str) and cached_name:
            return cached_name
        return None

    def _set_cached_user_name(self, id_map: dict[str, str], user_name: str):
        if not user_name:
            return

        # Avoid unbounded memory growth when running for a long time.
        if len(self.user_name_cache) > USER_NAME_CACHE_SIZE:
            self.user_name_cache.clear()

        expire_at = int(time.time()) + USER_NAME_CACHE_MAX_LIFETIME
        for id_type, id_value in id_map.items():
            if not isinstance(id_value, str) or not id_value:
                continue
            self.user_name_cache[f'{id_type}:{id_value}'] = {
                'name': user_name,
                'expire_at': expire_at,
            }

    def _get_cached_chat_name(self, chat_id: str) -> str | None:
        cache_item = self.chat_name_cache.get(chat_id)
        if cache_item is None:
            return None

        expire_at = cache_item.get('expire_at', 0)
        if int(time.time()) >= expire_at:
            self.chat_name_cache.pop(chat_id, None)
            return None

        cached_name = cache_item.get('name')
        if isinstance(cached_name, str) and cached_name:
            return cached_name
        return None

    def _set_cached_chat_name(self, chat_id: str, chat_name: str):
        if not chat_id or not chat_name:
            return

        if len(self.chat_name_cache) > CHAT_NAME_CACHE_SIZE:
            self.chat_name_cache.clear()

        self.chat_name_cache[chat_id] = {
            'name': chat_name,
            'expire_at': int(time.time()) + CHAT_NAME_CACHE_MAX_LIFETIME,
        }

    def _build_request_option(self, tenant_key: str | None) -> RequestOption:
        app_access_token = self.get_app_access_token()
        tenant_access_token = self.get_tenant_access_token(tenant_key)
        return (
            RequestOption.builder()
            .app_ticket(self.app_ticket)
            .tenant_key(tenant_key)
            .app_access_token(app_access_token)
            .tenant_access_token(tenant_access_token)
            .build()
        )

    async def resolve_event_sender_name(self, event: lark_oapi.im.v1.P2ImMessageReceiveV1) -> str | None:
        sender = getattr(getattr(event, 'event', None), 'sender', None)
        sender_id = getattr(sender, 'sender_id', None)
        if sender_id is None:
            return None

        id_map: dict[str, str] = {}
        for id_type in ('open_id', 'user_id', 'union_id'):
            value = getattr(sender_id, id_type, None)
            if isinstance(value, str) and value:
                id_map[id_type] = value

        if not id_map:
            return None

        for id_type in ('open_id', 'user_id', 'union_id'):
            id_value = id_map.get(id_type)
            if not id_value:
                continue
            cached_name = self._get_cached_user_name(id_type, id_value)
            if cached_name:
                return cached_name

        tenant_key = getattr(getattr(event, 'header', None), 'tenant_key', None)
        if not tenant_key:
            tenant_key = self.lark_tenant_key or self.config.get('lark_tenant_key') or None

        req_opt = self._build_request_option(tenant_key)

        for query_id_type in ('open_id', 'user_id', 'union_id'):
            query_id = id_map.get(query_id_type)
            if not query_id:
                continue

            try:
                request: GetUserRequest = (
                    GetUserRequest.builder().user_id_type(query_id_type).user_id(str(query_id)).build()
                )
                response: GetUserResponse = self.api_client.contact.v3.user.get(request, req_opt)

                if not response.success():
                    continue

                user = response.data.user if response.data else None
                if user is None:
                    continue

                user_name = (getattr(user, 'name', None) or getattr(user, 'nickname', None) or '').strip()
                if not user_name:
                    continue

                resolved_id_map = {
                    'open_id': getattr(user, 'open_id', None) or id_map.get('open_id', ''),
                    'user_id': getattr(user, 'user_id', None) or id_map.get('user_id', ''),
                    'union_id': getattr(user, 'union_id', None) or id_map.get('union_id', ''),
                }
                self._set_cached_user_name(resolved_id_map, user_name)
                return user_name
            except Exception:
                continue

        return None

    async def resolve_chat_name(self, chat_id: str, event: lark_oapi.im.v1.P2ImMessageReceiveV1 | None = None) -> str | None:
        if not chat_id:
            return None

        cached_name = self._get_cached_chat_name(chat_id)
        if cached_name:
            return cached_name

        tenant_key = None
        if event is not None:
            tenant_key = getattr(getattr(event, 'header', None), 'tenant_key', None)
        if not tenant_key:
            tenant_key = self.lark_tenant_key or self.config.get('lark_tenant_key') or None

        req_opt = self._build_request_option(tenant_key)

        try:
            request: GetChatRequest = GetChatRequest.builder().chat_id(str(chat_id)).build()
            response: GetChatResponse = self.api_client.im.v1.chat.get(request, req_opt)
            if not response.success():
                return None

            chat = response.data.chat if response.data else None
            chat_name = (getattr(chat, 'name', None) or '').strip() if chat else ''
            if not chat_name:
                return None

            self._set_cached_chat_name(chat_id, chat_name)
            return chat_name
        except Exception:
            return None

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        # Map generic target types used by plugin/runtime to Lark receive_id_type.
        receive_id_type_map = {
            'person': 'open_id',
            'friend': 'open_id',
            'user': 'open_id',
            'group': 'chat_id',
            'chat': 'chat_id',
            'open_id': 'open_id',
            'chat_id': 'chat_id',
            'user_id': 'user_id',
            'union_id': 'union_id',
            'email': 'email',
        }

        receive_id_type = receive_id_type_map.get(str(target_type).lower())
        if receive_id_type is None:
            raise ValueError(
                f'Unsupported target_type for Lark proactive messaging: {target_type}. '
                f'Supported values: {", ".join(receive_id_type_map.keys())}'
            )

        # Build Lark message payloads with the same converter used by reply paths.
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)

        tenant_key = self.lark_tenant_key or self.config.get('lark_tenant_key') or None
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

        async def send_create_message(msg_type: str, content_payload: dict) -> None:
            request: CreateMessageRequest = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(str(target_id))
                    .content(json.dumps(content_payload))
                    .msg_type(msg_type)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )

            # Use sync SDK call here for compatibility with current lark-oapi usage in this adapter.
            response: CreateMessageResponse = self.api_client.im.v1.message.create(request, req_opt)
            if not response.success():
                raise Exception(
                    f'client.im.v1.message.create ({msg_type}) failed, code: {response.code}, '
                    f'msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n'
                    f'{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

        # Send text payload first.
        if text_elements:
            needs_post = any(ele['tag'] == 'at' for paragraph in text_elements for ele in paragraph)
            if needs_post:
                await send_create_message(
                    'post',
                    {
                        'zh_Hans': {
                            'title': '',
                            'content': text_elements,
                        },
                    },
                )
            else:
                text_parts = []
                for paragraph in text_elements:
                    para_text = ''.join(ele.get('text', '') for ele in paragraph)
                    if para_text:
                        text_parts.append(para_text)
                await send_create_message('text', {'text': '\n\n'.join(text_parts)})

        # Send each media payload separately.
        for media in media_items:
            await send_create_message(media['msg_type'], media['content'])

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
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)

        # Send text message if there are text elements
        if text_elements:
            # Determine msg_type based on content: use 'post' if at mentions
            # are present (requires post paragraph structure), otherwise 'text'
            needs_post = any(ele['tag'] == 'at' for paragraph in text_elements for ele in paragraph)

            if needs_post:
                msg_type = 'post'
                final_content = json.dumps(
                    {
                        'zh_Hans': {
                            'title': '',
                            'content': text_elements,
                        },
                    }
                )
            else:
                msg_type = 'text'
                parts = []
                for paragraph in text_elements:
                    para_text = ''.join(ele.get('text', '') for ele in paragraph)
                    if para_text:
                        parts.append(para_text)
                final_content = json.dumps({'text': '\n\n'.join(parts)})

            request: ReplyMessageRequest = (
                ReplyMessageRequest.builder()
                .message_id(message_source.message_chain.message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(final_content)
                    .msg_type(msg_type)
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

        # Send media messages separately (image, audio, file, etc.)
        for media in media_items:
            request: ReplyMessageRequest = (
                ReplyMessageRequest.builder()
                .message_id(message_source.message_chain.message_id)
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(json.dumps(media['content']))
                    .msg_type(media['msg_type'])
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
                    f'client.im.v1.message.reply ({media["msg_type"]}) failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
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
            text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)

            text_message = ''
            if text_elements:
                parts = []
                for paragraph in text_elements:
                    para_text = ''.join(ele['text'] for ele in paragraph if ele['tag'] in ('text', 'md'))
                    if para_text:
                        parts.append(para_text)
                text_message = '\n\n'.join(parts)

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

            # Send media messages when streaming is done
            if is_final and media_items:
                for media in media_items:
                    media_request: ReplyMessageRequest = (
                        ReplyMessageRequest.builder()
                        .message_id(message_source.message_chain.message_id)
                        .request_body(
                            ReplyMessageRequestBody.builder()
                            .content(json.dumps(media['content']))
                            .msg_type(media['msg_type'])
                            .reply_in_thread(False)
                            .uuid(str(uuid.uuid4()))
                            .build()
                        )
                        .build()
                    )
                    media_response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(
                        media_request, req_opt
                    )
                    if not media_response.success():
                        raise Exception(
                            f'client.im.v1.message.reply ({media["msg_type"]}) failed, code: {media_response.code}, msg: {media_response.msg}, log_id: {media_response.get_log_id()}'
                        )

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
                event = None
                try:
                    p2v1 = P2ImMessageReceiveV1()
                    p2v1.header = context.header
                    event = P2ImMessageReceiveV1Data()
                    event.message = EventMessage(context.event['message'])
                    event.sender = EventSender(context.event['sender'])
                    p2v1.event = event
                    p2v1.schema = context.schema
                    event = await self.event_converter.target2yiri(p2v1, self.api_client, self)
                    self._cache_message_for_recall(event)
                except Exception:
                    await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')

                if event is not None and event.__class__ in self.listeners:
                    await self.listeners[event.__class__](event, self)
            elif 'im.message.recalled_v1' == type:
                try:
                    recalled_event = P2ImMessageRecalledV1()
                    recalled_event.header = context.header
                    recalled_data = P2ImMessageRecalledV1Data()
                    recalled_data.message_id = context.event.get('message_id')
                    recalled_data.chat_id = context.event.get('chat_id')
                    recalled_data.recall_time = context.event.get('recall_time')
                    recalled_data.recall_type = context.event.get('recall_type')
                    recalled_event.event = recalled_data
                    recalled_event.schema = context.schema

                    event = self._build_recalled_platform_event(recalled_event)
                    if event is not None and event.__class__ in self.listeners:
                        await self.listeners[event.__class__](event, self)
                except Exception:
                    await self.logger.error(f'Error in lark callback: {traceback.format_exc()}')
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
