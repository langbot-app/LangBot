from __future__ import annotations

import base64
import datetime
import json
import mimetypes
import os
import re
import tempfile
import traceback

import lark_oapi
from lark_oapi.api.im.v1 import (
    CreateFileRequest,
    CreateFileRequestBody,
    CreateImageRequest,
    CreateImageRequestBody,
    EventMessage,
    GetMessageResourceRequest,
    GetMessageResourceResponse,
)

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.pkg.utils import httpclient
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class LarkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def upload_image_to_lark(msg: platform_message.Image, api_client: lark_oapi.Client) -> str | None:
        image_bytes = await LarkMessageConverter._get_component_bytes(msg)
        if image_bytes is None:
            return None

        temp_file_path = ''
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(image_bytes)
                temp_file.flush()
                temp_file_path = temp_file.name

            request = (
                CreateImageRequest.builder()
                .request_body(
                    CreateImageRequestBody.builder().image_type('message').image(open(temp_file_path, 'rb')).build()
                )
                .build()
            )
            response = await api_client.im.v1.image.acreate(request)
            if not response.success():
                return None
            return response.data.image_key
        except Exception:
            traceback.print_exc()
            return None
        finally:
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    async def upload_file_to_lark(
        file_bytes: bytes,
        api_client: lark_oapi.Client,
        file_type: str,
        file_name: str = 'file',
        duration: int | None = None,
    ) -> str | None:
        temp_file_path = ''
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_file.flush()
                temp_file_path = temp_file.name

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
                return None
            return response.data.file_key
        except Exception:
            traceback.print_exc()
            return None
        finally:
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    async def _get_component_bytes(
        msg: platform_message.Image | platform_message.Voice | platform_message.File,
    ) -> bytes | None:
        if getattr(msg, 'base64', None):
            try:
                base64_data = msg.base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                return base64.b64decode(base64_data)
            except Exception:
                return None
        if getattr(msg, 'url', None):
            try:
                if str(msg.url).startswith('file://'):
                    with open(str(msg.url)[7:], 'rb') as f:
                        return f.read()
                session = httpclient.get_session()
                async with session.get(msg.url) as response:
                    if response.status == 200:
                        return await response.read()
            except Exception:
                return None
        if getattr(msg, 'path', None):
            try:
                with open(msg.path, 'rb') as f:
                    return f.read()
            except Exception:
                return None
        return None

    @staticmethod
    def _lark_file_type(file_name: str) -> str:
        ext = os.path.splitext(file_name)[1].lstrip('.').lower()
        return {
            'opus': 'opus',
            'mp4': 'mp4',
            'pdf': 'pdf',
            'doc': 'doc',
            'docx': 'doc',
            'xls': 'xls',
            'xlsx': 'xls',
            'ppt': 'ppt',
            'pptx': 'ppt',
        }.get(ext, 'stream')

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
        api_client: lark_oapi.Client,
    ) -> tuple[list[list[dict]], list[dict]]:
        message_elements: list[list[dict]] = []
        media_items: list[dict] = []
        pending_paragraph: list[dict] = []
        markdown_image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

        async def process_text_with_images(text: str) -> tuple[str, list[str]]:
            matches = list(markdown_image_pattern.finditer(text))
            if not matches:
                return text, []
            cleaned_text = text
            extracted_urls: list[str] = []
            for match in reversed(matches):
                extracted_urls.insert(0, match.group(2))
                cleaned_text = cleaned_text[: match.start()] + cleaned_text[match.end() :]
            cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
            return cleaned_text, extracted_urls

        for msg in message_chain:
            if isinstance(msg, platform_message.Source):
                continue
            if isinstance(msg, platform_message.Plain):
                cleaned_text, extracted_urls = await process_text_with_images(msg.text)
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
                for url in extracted_urls:
                    image_key = await LarkMessageConverter.upload_image_to_lark(
                        platform_message.Image(url=url), api_client
                    )
                    if image_key:
                        media_items.append({'msg_type': 'image', 'content': {'image_key': image_key}})
            elif isinstance(msg, platform_message.At):
                pending_paragraph.append({'tag': 'at', 'user_id': str(msg.target), 'style': []})
            elif isinstance(msg, platform_message.AtAll):
                pending_paragraph.append({'tag': 'at', 'user_id': 'all', 'style': []})
            elif isinstance(msg, platform_message.Image):
                image_key = await LarkMessageConverter.upload_image_to_lark(msg, api_client)
                if image_key:
                    media_items.append({'msg_type': 'image', 'content': {'image_key': image_key}})
            elif isinstance(msg, platform_message.Voice):
                data = await LarkMessageConverter._get_component_bytes(msg)
                if data:
                    duration = int(msg.length * 1000) if msg.length else None
                    file_key = await LarkMessageConverter.upload_file_to_lark(
                        data, api_client, file_type='opus', file_name='voice.opus', duration=duration
                    )
                    if file_key:
                        media_items.append({'msg_type': 'audio', 'content': {'file_key': file_key}})
            elif isinstance(msg, platform_message.File):
                data = await LarkMessageConverter._get_component_bytes(msg)
                if data:
                    file_name = msg.name or 'file'
                    file_key = await LarkMessageConverter.upload_file_to_lark(
                        data,
                        api_client,
                        file_type=LarkMessageConverter._lark_file_type(file_name),
                        file_name=file_name,
                    )
                    if file_key:
                        media_items.append({'msg_type': 'file', 'content': {'file_key': file_key}})
            elif isinstance(msg, platform_message.Quote):
                if msg.id:
                    pending_paragraph.append({'tag': 'md', 'text': f'[引用消息 {msg.id}] '})
                if msg.origin:
                    sub_elements, sub_media = await LarkMessageConverter.yiri2target(msg.origin, api_client)
                    message_elements.extend(sub_elements)
                    media_items.extend(sub_media)
            elif isinstance(msg, platform_message.Forward):
                for node in msg.node_list:
                    if node.sender_name or node.sender_id:
                        pending_paragraph.append({'tag': 'md', 'text': f'\n[{node.sender_name or node.sender_id}] '})
                    sub_elements, sub_media = await LarkMessageConverter.yiri2target(node.message_chain, api_client)
                    message_elements.extend(sub_elements)
                    media_items.extend(sub_media)

        if pending_paragraph:
            message_elements.append(pending_paragraph)

        return message_elements, media_items

    @staticmethod
    async def target2yiri(
        message: EventMessage,
        api_client: lark_oapi.Client,
    ) -> platform_message.MessageChain:
        message_content = json.loads(message.content or '{}')
        create_time = LarkMessageConverter._message_time(message)
        components: list[platform_message.MessageComponent] = [
            platform_message.Source(id=message.message_id, time=create_time)
        ]

        normalized = LarkMessageConverter._normalize_inbound_content(message, message_content)
        for ele in normalized:
            tag = ele.get('tag')
            if tag in {'text', 'md'}:
                text = ele.get('text') or ''
                if text:
                    components.append(platform_message.Plain(text=text))
            elif tag == 'at':
                user_id = ele.get('user_id') or ele.get('user_name') or ''
                display = ele.get('user_name') or user_id
                if user_id == 'all':
                    components.append(platform_message.AtAll())
                else:
                    components.append(platform_message.At(target=user_id, display=display))
            elif tag == 'img':
                image_key = ele.get('image_key') or ''
                image = await LarkMessageConverter._download_resource(
                    api_client, message.message_id, image_key, 'image'
                )
                components.append(platform_message.Image(image_id=image_key, **image))
            elif tag == 'audio':
                file_key = ele.get('file_key') or ''
                audio = await LarkMessageConverter._download_resource(api_client, message.message_id, file_key, 'file')
                components.append(
                    platform_message.Voice(
                        voice_id=file_key,
                        length=(ele.get('duration', 0) // 1000) if ele.get('duration') else None,
                        **audio,
                    )
                )
            elif tag == 'file':
                file_key = ele.get('file_key') or ''
                file_name = ele.get('file_name') or 'file'
                file_data = await LarkMessageConverter._download_resource(
                    api_client, message.message_id, file_key, 'file'
                )
                components.append(
                    platform_message.File(
                        id=file_key,
                        name=file_name,
                        size=file_data.pop('size', 0),
                        **file_data,
                    )
                )

        return platform_message.MessageChain(components)

    @staticmethod
    def _normalize_inbound_content(message: EventMessage, content: dict) -> list[dict]:
        if message.message_type == 'text':
            text = content.get('text', '')
            return LarkMessageConverter._split_text_mentions(text, getattr(message, 'mentions', []) or [])
        if message.message_type == 'post':
            post_content = content.get('content', [])
            flattened: list[dict] = []
            for ele in post_content:
                if isinstance(ele, dict):
                    flattened.append(ele)
                elif isinstance(ele, list):
                    flattened.extend(item for item in ele if isinstance(item, dict))
            return flattened
        if message.message_type == 'image':
            return [{'tag': 'img', 'image_key': content.get('image_key', ''), 'style': []}]
        if message.message_type == 'file':
            return [
                {
                    'tag': 'file',
                    'file_key': content.get('file_key', ''),
                    'file_name': content.get('file_name', 'file'),
                }
            ]
        if message.message_type == 'audio':
            return [
                {
                    'tag': 'audio',
                    'file_key': content.get('file_key', ''),
                    'duration': content.get('duration', 0),
                }
            ]
        return [{'tag': 'text', 'text': json.dumps(content, ensure_ascii=False), 'style': []}]

    @staticmethod
    def _split_text_mentions(text: str, mentions: list) -> list[dict]:
        if not text:
            return []
        mention_by_key = {getattr(m, 'key', ''): m for m in mentions}
        pattern = re.compile(r'@_user_\d+')
        result: list[dict] = []
        pos = 0
        for match in pattern.finditer(text):
            if match.start() > pos:
                result.append({'tag': 'text', 'text': text[pos : match.start()], 'style': []})
            mention = mention_by_key.get(match.group(0))
            if mention:
                result.append(
                    {
                        'tag': 'at',
                        'user_id': getattr(mention, 'id', None)
                        or getattr(mention, 'open_id', None)
                        or getattr(mention, 'user_id', None)
                        or getattr(mention, 'key', match.group(0)),
                        'user_name': getattr(mention, 'name', ''),
                        'style': [],
                    }
                )
            else:
                result.append({'tag': 'text', 'text': match.group(0), 'style': []})
            pos = match.end()
        if pos < len(text):
            result.append({'tag': 'text', 'text': text[pos:], 'style': []})
        return result

    @staticmethod
    async def _download_resource(
        api_client: lark_oapi.Client,
        message_id: str,
        file_key: str,
        resource_type: str,
    ) -> dict:
        if not file_key:
            return {}
        request = (
            GetMessageResourceRequest.builder().message_id(message_id).file_key(file_key).type(resource_type).build()
        )
        response: GetMessageResourceResponse = await api_client.im.v1.message_resource.aget(request)
        if not response.success():
            return {}
        data = response.file.read()
        content_type = response.raw.headers.get('content-type', 'application/octet-stream')
        base64_data = base64.b64encode(data).decode()
        ext = mimetypes.guess_extension(content_type.split(';')[0].strip()) or '.bin'
        temp_path = os.path.join(tempfile.gettempdir(), f'lark_{file_key}{ext}')
        with open(temp_path, 'wb') as f:
            f.write(data)
        return {
            'url': f'file://{temp_path}',
            'path': temp_path,
            'base64': f'data:{content_type};base64,{base64_data}',
            'size': len(data),
        }

    @staticmethod
    def _message_time(message: EventMessage) -> datetime.datetime:
        value = getattr(message, 'create_time', None)
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, (int, float, str)):
            try:
                timestamp = float(value)
                if timestamp > 10_000_000_000:
                    timestamp = timestamp / 1000
                return datetime.datetime.fromtimestamp(timestamp)
            except ValueError:
                pass
        return datetime.datetime.now()
