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
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def _lark_form_component_name(prefix: str, field_name: str, index: int) -> str:
    safe_name = re.sub(r'[^A-Za-z0-9_]', '_', field_name)[:8] or 'field'
    digest = hashlib.sha1(field_name.encode('utf-8')).hexdigest()[:6]
    return f'{prefix}_{index}_{safe_name}_{digest}'[:32]


def _dify_field_name(field: dict) -> str:
    return str(field.get('output_variable_name') or field.get('name') or field.get('id') or '').strip()


def _dify_field_type(field: dict) -> str:
    return str(field.get('type') or 'text').strip().lower()


def _dify_select_options(field: dict) -> list[str]:
    source = field.get('option_source') or {}
    value = source.get('value') if isinstance(source, dict) else None
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [part.strip() for part in value.splitlines() if part.strip()]
    options = field.get('options')
    if isinstance(options, list):
        result: list[str] = []
        for item in options:
            if isinstance(item, dict):
                result.append(str(item.get('label') or item.get('value') or ''))
            else:
                result.append(str(item))
        return [item for item in result if item]
    return []


def _dify_default_value(field: dict) -> str:
    default = field.get('default')
    if isinstance(default, dict):
        value = default.get('value') if default.get('type') == 'constant' or 'value' in default else ''
    else:
        value = default
    return '' if value is None else str(value)


def _lark_clean_form_content(form_content: str, input_defs: list[dict]) -> str:
    field_names = {_dify_field_name(field) for field in input_defs if _dify_field_name(field)}
    kept_lines: list[str] = []
    for line in (form_content or '').splitlines():
        placeholder = re.fullmatch(r'\s*\{\{#\$output\.([^#{}]+)#\}\}\s*', line)
        if placeholder and placeholder.group(1) in field_names:
            continue
        kept_lines.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept_lines).strip())


def _lark_form_input_defs(form_data: dict) -> list[dict]:
    return list(form_data.get('all_input_defs') or form_data.get('input_defs') or [])


def _lark_current_input_defs(form_data: dict) -> list[dict]:
    """Return only the field that belongs to the current interactive step."""
    if form_data.get('_action_select_only'):
        return []
    input_defs = list(form_data.get('input_defs') or [])
    current_field = str(form_data.get('_current_input_field') or '').strip()
    if not current_field:
        return input_defs
    return [field for field in input_defs if _dify_field_name(field) == current_field]


def _lark_should_update_stream_element(
    *,
    resume_from: bool,
    form_data: dict | None,
    msg_seq: int,
    is_final: bool,
) -> bool:
    """Return whether the still-open streaming element should be updated."""
    return not resume_from and not form_data and (msg_seq % 8 == 0 or is_final)


def _lark_display_input_value(field: dict, value: typing.Any) -> str:
    field_type = _dify_field_type(field)
    if field_type == 'file':
        if isinstance(value, dict):
            return value.get('url') or value.get('upload_file_id') or '1 file'
        return str(value)
    if field_type == 'file-list':
        if isinstance(value, list):
            return f'{len(value)} file(s)'
        return str(value)
    if isinstance(value, dict):
        if 'value' in value and value.get('value') not in (None, ''):
            return str(value.get('value'))
        text = value.get('text')
        if isinstance(text, dict):
            content = text.get('content')
            if content not in (None, ''):
                return str(content)
        if text not in (None, ''):
            return str(text)
    if isinstance(value, list):
        return ', '.join(_lark_display_input_value(field, item) for item in value if item not in (None, ''))
    return str(value)


def _lark_visible_form_content(form_data: dict) -> str:
    """Return stage content with completed values interleaved for final actions."""
    source_content = form_data.get('form_content') or ''
    if form_data.get('_action_select_only'):
        source_content = form_data.get('raw_form_content') or source_content

        fields = {
            _dify_field_name(field): field for field in _lark_form_input_defs(form_data) if _dify_field_name(field)
        }
        inputs = form_data.get('inputs') or {}

        def replace_placeholder(match: re.Match[str]) -> str:
            field_name = match.group(1).strip()
            field = fields.get(field_name)
            if not field or inputs.get(field_name) in (None, '', []):
                return ''
            lines = _lark_completed_input_lines(
                {
                    'input_defs': [field],
                    'inputs': {field_name: inputs[field_name]},
                }
            )
            return lines[0] if lines else ''

        source_content = re.sub(
            r'\{\{#\$output\.([^#{}]+)#\}\}',
            replace_placeholder,
            str(source_content),
        )
    return _lark_clean_form_content(
        str(source_content),
        _lark_form_input_defs(form_data),
    )


def _lark_completed_input_lines(form_data: dict) -> list[str]:
    inputs = form_data.get('inputs') or {}
    if not isinstance(inputs, dict):
        return []

    lines: list[str] = []
    for field in _lark_form_input_defs(form_data):
        field_name = _dify_field_name(field)
        if not field_name:
            continue
        value = inputs.get(field_name)
        if value in (None, '', []):
            continue
        display_value = _lark_display_input_value(field, value)
        lines.append(f'✅ {field_name}：{display_value}')
    return lines


def _lark_mapping_from_value(value: typing.Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _lark_action_attr(action: typing.Any, name: str) -> typing.Any:
    if isinstance(action, dict):
        return action.get(name)
    return getattr(action, name, None)


def _lark_extract_action_form_inputs(action: typing.Any, action_value_obj: dict) -> dict:
    input_name_map = action_value_obj.get('input_name_map', {})
    if not isinstance(input_name_map, dict):
        input_name_map = {}

    form_value = _lark_mapping_from_value(_lark_action_attr(action, 'form_value'))
    if not form_value:
        for key in ('form_value', 'formValue', 'form_values', 'formValues'):
            form_value = _lark_mapping_from_value(action_value_obj.get(key))
            if form_value:
                break

    if not form_value:
        action_name = _lark_action_attr(action, 'name')
        input_value = _lark_action_attr(action, 'input_value')
        option_value = _lark_action_attr(action, 'option')
        if action_name and input_value not in (None, ''):
            form_value = {action_name: input_value}
        elif action_name and option_value not in (None, ''):
            form_value = {action_name: option_value}

    form_inputs = {}
    for component_name, value in form_value.items():
        field_name = input_name_map.get(component_name)
        if not field_name and isinstance(component_name, str) and '.' in component_name:
            field_name = input_name_map.get(component_name.rsplit('.', 1)[-1], component_name)
        if not field_name:
            field_name = component_name
        if field_name and value not in (None, '', []):
            form_inputs[str(field_name)] = value
    return form_inputs


class NonBlockingLarkWSClient(lark_oapi.ws.Client):
    """Keep the SDK's synchronous connection lookup off LangBot's event loop.

    lark-oapi performs ``requests.post`` inside its async ``_connect`` method.
    A stalled TLS handshake therefore freezes Quart and every other adapter in
    the process. Pre-fetch the URL in a worker thread, then let the SDK finish
    the WebSocket setup on the main loop with the already-resolved URL.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._langbot_connect_lock = asyncio.Lock()

    async def _connect(self) -> None:
        async with self._langbot_connect_lock:
            if self._conn is not None:
                return

            conn_url = await asyncio.to_thread(self._get_conn_url)
            original_get_conn_url = self._get_conn_url
            self._get_conn_url = lambda: conn_url
            try:
                await super()._connect()
            finally:
                self._get_conn_url = original_get_conn_url


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
    _processed_thread_quote_cache: typing.ClassVar[dict[str, float]] = {}
    _processed_thread_quote_cache_max_size: typing.ClassVar[int] = 4096
    _processed_thread_quote_cache_ttl_seconds: typing.ClassVar[int] = 86400

    @classmethod
    def _prune_processed_thread_quote_cache(cls, now: typing.Optional[float] = None) -> None:
        if now is None:
            now = time.time()

        expire_before = now - cls._processed_thread_quote_cache_ttl_seconds
        while cls._processed_thread_quote_cache:
            oldest_key, oldest_ts = next(iter(cls._processed_thread_quote_cache.items()))
            if oldest_ts >= expire_before:
                break
            cls._processed_thread_quote_cache.pop(oldest_key, None)

        while len(cls._processed_thread_quote_cache) > cls._processed_thread_quote_cache_max_size:
            oldest_key = next(iter(cls._processed_thread_quote_cache))
            cls._processed_thread_quote_cache.pop(oldest_key, None)

    @classmethod
    def _mark_thread_quote_processed(cls, thread_id: str) -> None:
        now = time.time()
        cls._prune_processed_thread_quote_cache(now)
        cls._processed_thread_quote_cache[thread_id] = now

    @classmethod
    def _extract_quote_message_id(cls, message: EventMessage) -> typing.Optional[str]:
        """
        Extract the message ID to quote from the given message.

        Rules:
        - First thread reply in a topic: return parent_id and mark topic as processed
        - Follow-up thread replies in the same topic: return None
        - Non-thread message: return parent_id if valid (non-empty, different from message_id)

        Thread reply state is kept in a bounded TTL cache to avoid unbounded memory growth.
        """
        parent_id = getattr(message, 'parent_id', None)
        if not parent_id:
            return None

        message_id = getattr(message, 'message_id', None)
        if parent_id == message_id:
            return None

        thread_id = getattr(message, 'thread_id', None)
        if thread_id:
            cls._prune_processed_thread_quote_cache()
            if thread_id in cls._processed_thread_quote_cache:
                return None
            cls._mark_thread_quote_processed(thread_id)

        return parent_id

    @staticmethod
    def _build_event_message_from_message_item(message_item: Message) -> typing.Optional[EventMessage]:
        """
        Build EventMessage from SDK typed Message item.

        Returns None if body or content is missing.
        """
        body = getattr(message_item, 'body', None)
        if not body:
            return None

        content = getattr(body, 'content', None)
        if not content:
            return None

        event_data = {
            'message_id': message_item.message_id,
            'message_type': message_item.msg_type,
            'content': content,
            'create_time': message_item.create_time,
            'mentions': getattr(message_item, 'mentions', []) or [],
        }

        # Preserve thread-related fields
        if hasattr(message_item, 'parent_id') and message_item.parent_id:
            event_data['parent_id'] = message_item.parent_id
        if hasattr(message_item, 'root_id') and message_item.root_id:
            event_data['root_id'] = message_item.root_id
        if hasattr(message_item, 'thread_id') and message_item.thread_id:
            event_data['thread_id'] = message_item.thread_id
        if hasattr(message_item, 'chat_id') and message_item.chat_id:
            event_data['chat_id'] = message_item.chat_id

        return EventMessage(event_data)

    @staticmethod
    async def _fetch_quoted_message(
        quote_message_id: str,
        api_client: lark_oapi.Client,
    ) -> typing.Optional[platform_message.MessageChain]:
        """
        Fetch the quoted message and convert to MessageChain.

        Returns None if:
        - API call fails
        - Response items is empty
        - Message item normalization fails
        """
        request = GetMessageRequest.builder().message_id(quote_message_id).build()
        response = await api_client.im.v1.message.aget(request)

        if not response.success():
            return None

        items = getattr(response.data, 'items', None)
        if not items:
            return None

        message_item = items[0]
        event_message = LarkEventConverter._build_event_message_from_message_item(message_item)
        if event_message is None:
            return None

        quote_chain = await LarkMessageConverter.target2yiri(event_message, api_client)
        return quote_chain

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

        # Check for quote/reply message
        # Extract files/images/voice from quote and add them as top-level components
        # so that plugins like FileReader can process them the same way as direct messages
        quote_message_id = LarkEventConverter._extract_quote_message_id(event.event.message)
        if quote_message_id:
            quote_chain = await LarkEventConverter._fetch_quoted_message(quote_message_id, api_client)
            if quote_chain:
                # Filter out Source component from quoted chain, keep only content
                quote_components = [comp for comp in quote_chain if not isinstance(comp, platform_message.Source)]

                # Add quoted content as top-level components instead of wrapping in Quote
                for comp in quote_components:
                    if isinstance(comp, platform_message.File):
                        # Add file as top-level component (same as direct message)
                        message_chain.append(comp)
                    elif isinstance(comp, platform_message.Image):
                        # Add image as top-level component
                        message_chain.append(comp)
                    elif isinstance(comp, platform_message.Voice):
                        # Add voice as top-level component
                        message_chain.append(comp)
                    elif isinstance(comp, platform_message.Plain):
                        # Add text with context prefix
                        message_chain.append(platform_message.Plain(text=f'[引用消息] {comp.text}'))

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
    ap: typing.Any = pydantic.Field(exclude=True, default=None)

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

    # Monitoring message ID mapping for feedback correlation
    # Temp: user Lark message ID → monitoring_message_id (populated by on_monitoring_message_created, consumed by create_message_card)
    pending_monitoring_msg: dict[str, str]
    # Final: reply Lark message ID → (monitoring_message_id, timestamp) (used by feedback callbacks)
    reply_to_monitoring_msg: dict[str, tuple[str, float]]
    reply_message_card_ids: dict[str, str]
    card_sequence_dict: dict[str, int]
    # card_id → set of source message ids registered against it (for cleanup)
    card_id_to_source_ids: dict[str, set[str]]
    # card_id → current streaming_txt content cache (needed for full aupdate during resume transition)
    card_streaming_text: dict[str, str]
    # card_id → pre-pause streaming_txt text (captured when resume first chunk arrives)
    card_pre_pause_text: dict[str, str]
    # card_id → form_content captured when the form is first shown (for resume notice)
    card_form_content: dict[str, str]
    # card_id → input_defs / inputs captured for the selected-action notice
    card_form_input_defs: dict[str, list[dict]]
    card_form_inputs: dict[str, dict]
    # set of card_ids that have already transitioned from "buttons visible" to "resume layout"
    card_resume_transitioned: set[str]
    _MONITORING_MAPPING_TTL = 600  # 10 minutes

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

        def schedule_on_app_loop(coro):
            """Run a coroutine on the application event loop from sync callbacks."""
            return asyncio.run_coroutine_threadsafe(coro, self.ap.event_loop)

        def sync_on_card_action(event):
            try:
                action_value_raw = getattr(getattr(event.event, 'action', None), 'value', {})
                # Parse JSON string values (from form action buttons)
                action_value_obj = _lark_mapping_from_value(action_value_raw)
                action_value = action_value_obj.get('feedback', '') if isinstance(action_value_obj, dict) else ''

                # Handle Dify form action button clicks
                if isinstance(action_value_obj, dict) and action_value_obj.get('form_action'):
                    form_token = action_value_obj.get('form_token', '')
                    workflow_run_id = action_value_obj.get('workflow_run_id', '')
                    action_id = action_value_obj.get('action_id', '')
                    session_key = action_value_obj.get('session_key', '')
                    action = getattr(event.event, 'action', None)
                    form_inputs = _lark_extract_action_form_inputs(action, action_value_obj)

                    if session_key.startswith('group_') or session_key.startswith('g:'):
                        launcher_type = provider_session.LauncherTypes.GROUP
                        launcher_id = (
                            session_key.split(':', 1)[1]
                            if session_key.startswith('g:')
                            else session_key[len('group_') :]
                        )
                    else:
                        launcher_type = provider_session.LauncherTypes.PERSON
                        launcher_id = (
                            session_key.split(':', 1)[1]
                            if session_key.startswith('p:')
                            else session_key[len('person_') :]
                        )

                    # Find the bot entity to get bot_uuid and pipeline_uuid
                    bot_uuid = ''
                    pipeline_uuid = action_value_obj.get('pipeline_uuid') or None
                    for bot in self.ap.platform_mgr.bots:
                        if bot.adapter is self:
                            bot_uuid = bot.bot_entity.uuid
                            pipeline_uuid = pipeline_uuid or bot.bot_entity.use_pipeline_uuid
                            break

                    form_action_data = {
                        'form_token': form_token,
                        'workflow_run_id': workflow_run_id,
                        'action_id': action_id,
                        'user': f'{launcher_type.value}_{launcher_id}',
                        'inputs': form_inputs,
                    }
                    if action_value_obj.get('_input_progress'):
                        form_action_data['_input_progress'] = True

                    context = getattr(event.event, 'context', None)
                    open_message_id = getattr(context, 'open_message_id', None)
                    if open_message_id and form_inputs:
                        card_id = self.reply_message_card_ids.get(str(open_message_id))
                    else:
                        card_id = None
                    if not card_id:
                        card_id = str(action_value_obj.get('card_id') or '')
                    if card_id and form_inputs:
                        cached_inputs = dict(self.card_form_inputs.get(card_id) or {})
                        cached_inputs.update(form_inputs)
                        self.card_form_inputs[card_id] = cached_inputs
                        if self.ap is not None:
                            self.ap.logger.info(
                                f'Lark form action inputs cached: card_id={card_id} '
                                f'open_message_id={open_message_id} keys={list(form_inputs.keys())}'
                            )
                    source_time = datetime.datetime.now()
                    event_time = source_time.timestamp()
                    action_text = action_value_obj.get('action_id', 'confirm')
                    message_chain = platform_message.MessageChain(
                        [platform_message.Plain(text=f'[Form Action: {action_text}]')]
                    )
                    if open_message_id:
                        message_chain.insert(
                            0,
                            platform_message.Source(
                                id=open_message_id,
                                time=source_time,
                            ),
                        )

                    operator = getattr(event.event, 'operator', None)
                    user_id = (
                        getattr(operator, 'open_id', None) or getattr(operator, 'user_id', None) or str(launcher_id)
                    )

                    if launcher_type == provider_session.LauncherTypes.GROUP:
                        synthetic_event = platform_events.GroupMessage(
                            sender=platform_entities.GroupMember(
                                id=user_id,
                                member_name='',
                                permission=platform_entities.Permission.Member,
                                group=platform_entities.Group(
                                    id=launcher_id,
                                    name='',
                                    permission=platform_entities.Permission.Member,
                                ),
                            ),
                            message_chain=message_chain,
                            time=event_time,
                            source_platform_object=event,
                        )
                    else:
                        synthetic_event = platform_events.FriendMessage(
                            sender=platform_entities.Friend(
                                id=user_id,
                                nickname='',
                                remark='',
                            ),
                            message_chain=message_chain,
                            time=event_time,
                            source_platform_object=event,
                        )

                    async def add_form_action_query():
                        await self.ap.query_pool.add_query(
                            bot_uuid=bot_uuid,
                            launcher_type=launcher_type,
                            launcher_id=launcher_id,
                            sender_id=user_id,
                            message_event=synthetic_event,
                            message_chain=message_chain,
                            adapter=self,
                            pipeline_uuid=pipeline_uuid,
                            variables={
                                '_dify_form_action': form_action_data,
                                '_routed_by_rule': True,
                            },
                        )

                    schedule_on_app_loop(add_form_action_query())

                    from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

                    return P2CardActionTriggerResponse({'toast': {'type': 'success', 'content': '操作成功'}})

                if action_value == '有帮助':
                    feedback_type = 1
                elif action_value == '无帮助':
                    feedback_type = 2
                else:
                    from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

                    return P2CardActionTriggerResponse({'toast': {'type': 'success', 'content': '操作成功'}})

                operator = getattr(event.event, 'operator', None)
                context = getattr(event.event, 'context', None)

                user_id = getattr(operator, 'open_id', None) or getattr(operator, 'user_id', None)
                open_chat_id = getattr(context, 'open_chat_id', None)
                open_message_id = getattr(context, 'open_message_id', None)

                if open_chat_id:
                    session_id = f'group_{open_chat_id}'
                elif user_id:
                    session_id = f'person_{user_id}'
                else:
                    session_id = None

                # Resolve monitoring message ID from reply message mapping
                monitoring_msg_id = None
                if open_message_id and open_message_id in self.reply_to_monitoring_msg:
                    monitoring_msg_id = self.reply_to_monitoring_msg[open_message_id][0]

                feedback_event = platform_events.FeedbackEvent(
                    feedback_id=getattr(event.header, 'event_id', str(uuid.uuid4())),
                    feedback_type=feedback_type,
                    feedback_content=action_value,
                    user_id=user_id,
                    session_id=session_id,
                    message_id=open_message_id,
                    stream_id=monitoring_msg_id,
                    source_platform_object=event,
                )

                if platform_events.FeedbackEvent in self.listeners:
                    schedule_on_app_loop(self.listeners[platform_events.FeedbackEvent](feedback_event, self))

                from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

                return P2CardActionTriggerResponse({'toast': {'type': 'success', 'content': '感谢您的反馈'}})
            except Exception:
                traceback.print_exc()
                schedule_on_app_loop(self.logger.error(f'Error in lark card action callback: {traceback.format_exc()}'))
                from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

                return P2CardActionTriggerResponse({'toast': {'type': 'error', 'content': '反馈处理失败'}})

        event_handler = (
            lark_oapi.EventDispatcherHandler.builder('', '')
            .register_p2_im_message_receive_v1(sync_on_message)
            .register_p2_card_action_trigger(sync_on_card_action)
            .build()
        )

        bot_account_id = config['bot_name']

        domain = self._resolve_domain(config)
        bot = NonBlockingLarkWSClient(
            config['app_id'], config['app_secret'], event_handler=event_handler, domain=domain
        )
        api_client = self.build_api_client(config)
        cipher = AESCipher(config.get('encrypt-key', ''))
        self.request_app_ticket(api_client, config)

        super().__init__(
            config=config,
            logger=logger,
            lark_tenant_key=config.get('lark_tenant_key', ''),
            card_id_dict={},
            pending_monitoring_msg={},
            reply_to_monitoring_msg={},
            reply_message_card_ids={},
            card_sequence_dict={},
            card_id_to_source_ids={},
            card_streaming_text={},
            card_pre_pause_text={},
            card_form_content={},
            card_form_input_defs={},
            card_form_inputs={},
            card_resume_transitioned=set(),
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

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str | None:
        """
        Get topic-scoped launcher_id for thread-aware session isolation.

        For group thread messages, returns "{group_id}_{thread_id}"
        to ensure conversation context stays stable per topic.

        Returns None for non-thread messages or P2P messages.
        """
        source_event = getattr(event.source_platform_object, 'event', None)
        if not source_event:
            return None

        message = getattr(source_event, 'message', None)
        if not message:
            return None

        thread_id = getattr(message, 'thread_id', None)
        if not thread_id:
            return None

        if isinstance(event, platform_events.GroupMessage):
            return f'{event.group.id}_{thread_id}'

        return None

    @staticmethod
    def _resolve_domain(config) -> str:
        domain = config.get('domain', lark_oapi.FEISHU_DOMAIN)
        if domain == 'custom':
            domain = config.get('custom_domain', '')
            if not domain:
                raise ValueError('Custom domain is required when domain is set to "custom"')
        return domain.rstrip('/')

    def build_api_client(self, config):
        app_id = config['app_id']
        app_secret = config['app_secret']
        domain = self._resolve_domain(config)
        api_client = lark_oapi.Client.builder().app_id(app_id).app_secret(app_secret).domain(domain).build()
        if 'isv' == config.get('app_type', 'self'):
            api_client = (
                lark_oapi.Client.builder()
                .app_id(app_id)
                .app_secret(app_secret)
                .app_type(lark_oapi.AppType.ISV)
                .domain(domain)
                .build()
            )
        return api_client

    @staticmethod
    def _has_markdown_table(text_elements: list) -> bool:
        """Check if text elements contain markdown table syntax (|...|).

        A markdown table requires:
        - At least one line with pipe characters (|)
        - A separator line with pipes and dashes (|---|)
        """
        # Regex to detect markdown table: lines with pipes and separator lines with dashes
        table_pattern = re.compile(r'^\s*\|.+\|\s*$', re.MULTILINE)
        separator_pattern = re.compile(r'^\s*\|\s*-+(\s*\|\s*-+)*\s*\|\s*$', re.MULTILINE)

        for paragraph in text_elements:
            for ele in paragraph:
                if ele.get('tag') == 'md':
                    text = ele.get('text', '')
                    # Quick check: if has pipes and separator line, it's likely a table
                    if '|' in text and table_pattern.search(text) and separator_pattern.search(text):
                        return True
        return False

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)

        # Map standard target_type to Feishu receive_id_type
        if target_type == 'person':
            receive_id_type = 'open_id'
        elif target_type == 'group':
            receive_id_type = 'chat_id'
        else:
            receive_id_type = target_type

        # Send text message if there are text elements
        if text_elements:
            # Use 'post' format if: has @mentions OR has markdown tables
            has_at = any(ele['tag'] == 'at' for paragraph in text_elements for ele in paragraph)
            has_table = self._has_markdown_table(text_elements)
            needs_post = has_at or has_table

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

            request: CreateMessageRequest = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(target_id)
                    .content(final_content)
                    .msg_type(msg_type)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )

            app_access_token = self.get_app_access_token()
            req_opt: RequestOption = (
                RequestOption.builder().app_ticket(self.app_ticket).app_access_token(app_access_token).build()
            )
            response: CreateMessageResponse = self.api_client.im.v1.message.create(request, req_opt)

            if not response.success():
                raise Exception(
                    f'client.im.v1.message.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

        # Send media messages separately (image, audio, file, etc.)
        for media in media_items:
            request: CreateMessageRequest = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(target_id)
                    .content(json.dumps(media['content']))
                    .msg_type(media['msg_type'])
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )

            app_access_token = self.get_app_access_token()
            req_opt: RequestOption = (
                RequestOption.builder().app_ticket(self.app_ticket).app_access_token(app_access_token).build()
            )
            response: CreateMessageResponse = self.api_client.im.v1.message.create(request, req_opt)

            if not response.success():
                raise Exception(
                    f'client.im.v1.message.create ({media["msg_type"]}) failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}, resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                )

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def on_monitoring_message_created(self, query, monitoring_message_id: str):
        """Called by pipeline after monitoring message is created, to map user message ID to monitoring message ID."""
        try:
            user_msg_id = query.message_event.message_chain.message_id
            if user_msg_id:
                self.pending_monitoring_msg[user_msg_id] = monitoring_message_id
        except Exception as e:
            await self.logger.debug(f'Failed to map message to monitoring message: {e}')

    def _cleanup_monitoring_mapping(self):
        """Remove entries older than TTL from the reply-to-monitoring mapping."""
        now = time.time()
        expired = [k for k, (_, ts) in self.reply_to_monitoring_msg.items() if now - ts > self._MONITORING_MAPPING_TTL]
        for k in expired:
            del self.reply_to_monitoring_msg[k]

    def _next_card_sequence(self, card_id: str, suggested: int = 1) -> int:
        """Return the next strictly increasing sequence for a card update."""
        current = self.card_sequence_dict.get(card_id, 0)
        next_seq = max(current + 1, suggested)
        self.card_sequence_dict[card_id] = next_seq
        return next_seq

    def _register_card_for_source(self, card_id: str, *source_ids: str) -> None:
        """Register a card_id under one or more source message ids."""
        bucket = self.card_id_to_source_ids.setdefault(card_id, set())
        for sid in source_ids:
            if not sid:
                continue
            self.reply_message_card_ids[sid] = card_id
            bucket.add(sid)

    def _drop_card_state(self, card_id: str) -> None:
        """Pop all per-card state for the given card_id."""
        if not card_id:
            return
        for sid in self.card_id_to_source_ids.pop(card_id, set()):
            self.reply_message_card_ids.pop(sid, None)
        self.card_sequence_dict.pop(card_id, None)
        self.card_streaming_text.pop(card_id, None)
        self.card_pre_pause_text.pop(card_id, None)
        self.card_form_content.pop(card_id, None)
        self.card_form_input_defs.pop(card_id, None)
        self.card_form_inputs.pop(card_id, None)
        self.card_resume_transitioned.discard(card_id)

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
                                            'behaviors': [{'type': 'callback', 'value': {'feedback': '有帮助'}}],
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
                                            'behaviors': [{'type': 'callback', 'value': {'feedback': '无帮助'}}],
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
            self.card_sequence_dict[card_id] = 0
            return card_id

        except Exception as e:
            raise e

    async def create_message_card(self, message_id, event) -> str:
        """
        创建卡片消息。
        使用卡片消息是因为普通消息更新次数有限制，而大模型流式返回结果可能很多而超过限制，而飞书卡片没有这个限制（api免费次数有限）
        """
        # message_id = event.message_chain.message_id

        source_message_id = str(event.message_chain.message_id)
        existing_card_id = self.reply_message_card_ids.get(source_message_id)
        if existing_card_id:
            self.card_id_dict[message_id] = existing_card_id
            return True

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

        # Transfer monitoring message mapping: user msg ID → reply msg ID
        try:
            user_msg_id = event.message_chain.message_id
            reply_msg_id = getattr(response.data, 'message_id', None)
            monitoring_msg_id = self.pending_monitoring_msg.pop(user_msg_id, None)
            # Register the card under both the user-incoming msg id (so a
            # second reply_message_first_chunk for the same user message
            # reuses this card) AND the bot-reply msg id (so a synthetic
            # event from a form-button callback — whose Source.id equals
            # the bot's card message id — hits the same card and renders
            # the resume content into it).
            if reply_msg_id:
                self._register_card_for_source(card_id, str(user_msg_id), str(reply_msg_id))
            else:
                self._register_card_for_source(card_id, str(user_msg_id))
            if reply_msg_id and monitoring_msg_id:
                self.reply_to_monitoring_msg[reply_msg_id] = (monitoring_msg_id, time.time())
                self._cleanup_monitoring_mapping()
        except Exception as e:
            asyncio.create_task(self.logger.debug(f'Failed to transfer monitoring mapping in create_message_card: {e}'))

        return True

    async def _open_new_form_card(
        self,
        message_id: str,
        message_source: platform_events.MessageEvent,
        form_data: dict,
    ) -> str | None:
        """Spawn a fresh card to host a re-paused human-input prompt.

        Creates a new card_id (rebinding ``self.card_id_dict[message_id]``),
        replies it to the current incoming message so it appears as the next
        step in the chat, registers the new reply_msg_id so subsequent button
        callbacks resolve back to it, and renders the prompt + buttons on it.

        Returns the new card_id, or ``None`` if creation failed (caller is
        responsible for falling back to in-place update so the workflow
        remains continuable).
        """
        source_message_id = getattr(message_source.message_chain, 'message_id', None)
        if not source_message_id:
            await self.logger.error('Cannot open new form card: source message_id missing')
            return None

        try:
            new_card_id = await self.create_card_id(message_id)
        except Exception:
            await self.logger.error(f'Failed to create new form card: {traceback.format_exc()}')
            return None

        tenant_key = (
            message_source.source_platform_object.header.tenant_key if message_source.source_platform_object else None
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

        content = {
            'type': 'card',
            'data': {'card_id': new_card_id, 'template_variable': {'content': ''}},
        }
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(str(source_message_id))
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(json.dumps(content))
                .msg_type('interactive')
                .uuid(str(uuid.uuid4()))
                .build()
            )
            .build()
        )

        try:
            response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(request, req_opt)
        except Exception:
            await self.logger.error(f'Failed to send new form card: {traceback.format_exc()}')
            return None

        if not response.success():
            await self.logger.error(
                f'Failed to send new form card: code={response.code}, msg={response.msg}, '
                f'log_id={response.get_log_id()}'
            )
            return None

        reply_msg_id = getattr(response.data, 'message_id', None)
        if reply_msg_id:
            self._register_card_for_source(new_card_id, str(source_message_id), str(reply_msg_id))

        sequence = self._next_card_sequence(new_card_id, 1)
        await self._update_card_layout(
            card_id=new_card_id,
            message_source=message_source,
            text_message='',
            sequence=sequence,
            form_data=form_data,
            show_form_prompt=True,
        )
        return new_card_id

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
            # Use 'post' format if: has @mentions OR has markdown tables
            has_at = any(ele['tag'] == 'at' for paragraph in text_elements for ele in paragraph)
            has_table = self._has_markdown_table(text_elements)
            needs_post = has_at or has_table

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
        keep_stream: bool = False,
    ):
        """
        回复消息变成更新卡片消息

        Supports Dify form-action resume:  when the runner yields a chunk with
        ``_resume_from_form=True``, the card transitions from buttons to a
        grey selection notice and a new ``streaming_txt_resume`` element is added
        for subsequent resume chunks to stream into.

        When ``_open_new_card=True`` on the final chunk, the existing card is
        left as-is and the pipeline will create a new card (with fresh form
        buttons) for the re-pause.
        """
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence

        form_data = getattr(bot_message, '_form_data', None)
        resume_from = getattr(bot_message, '_resume_from_form', False)
        action_title = getattr(bot_message, '_resume_action_title', '')
        resume_node_title = getattr(bot_message, '_resume_node_title', '')
        open_new_card = getattr(bot_message, '_open_new_card', False)

        # ── decide whether this chunk needs a card update ────────────────────
        card_id = self.card_id_dict.get(message_id)
        if not card_id:
            return

        if action_title:
            # Build the selected notice with node_title, form_content, and action
            notice_parts = []
            if resume_node_title:
                notice_parts.append(f'**{resume_node_title}**')
            stored_form_content = self.card_form_content.get(card_id, '')
            if stored_form_content:
                notice_parts.append(stored_form_content)
            completed_lines = _lark_completed_input_lines(
                {
                    'input_defs': self.card_form_input_defs.get(card_id, []),
                    'inputs': self.card_form_inputs.get(card_id, {}),
                }
            )
            if completed_lines and not all(line in stored_form_content for line in completed_lines):
                notice_parts.append('---\n' + '\n'.join(completed_lines))
            notice_parts.append(f'---\n✅ {action_title}')
            selected_notice = '\n\n'.join(notice_parts)
        else:
            selected_notice = ''

        # ── convert message chain → text ─────────────────────────────────────
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)

        text_message = ''
        if text_elements:
            parts = []
            for paragraph in text_elements:
                para_text = ''.join(ele['text'] for ele in paragraph if ele['tag'] in ('text', 'md'))
                if para_text:
                    parts.append(para_text)
            text_message = '\n\n'.join(parts)

        tenant_key = (
            message_source.source_platform_object.header.tenant_key if message_source.source_platform_object else None
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

        card_sequence = self._next_card_sequence(card_id, msg_seq)

        # ── RESUME: first chunk after button click ───────────────────────────
        if resume_from and card_id not in self.card_resume_transitioned:
            # Transition the card from the form state into resume mode.
            # Preserve the text that was shown before the pause, and seed the
            # resume placeholder with the current resume content if we already
            # have any on the first yielded chunk.
            pre_pause_text = self.card_pre_pause_text.get(card_id) or self.card_streaming_text.get(card_id, '')
            initial_resume_text = text_message or '\u200b'
            await self._update_card_layout(
                card_id=card_id,
                message_source=message_source,
                text_message=pre_pause_text,
                sequence=card_sequence,
                form_data=None,
                notice_text=selected_notice,
                resume_placeholder_text=initial_resume_text,
            )
            self.card_resume_transitioned.add(card_id)
            self.card_pre_pause_text[card_id] = pre_pause_text
            self.card_streaming_text[card_id] = text_message
            if not is_final:
                return

        # ── RESUME: subsequent chunks → full card update ─────────────────────
        if resume_from and card_id in self.card_resume_transitioned:
            cached = self.card_streaming_text.get(card_id, '')
            if text_message != cached:
                self.card_streaming_text[card_id] = text_message
                pre_pause_text = self.card_pre_pause_text.get(card_id, '')
                await self._update_card_layout(
                    card_id=card_id,
                    message_source=message_source,
                    text_message=pre_pause_text,
                    sequence=card_sequence,
                    form_data=None,
                    notice_text=selected_notice,
                    resume_placeholder_text=text_message,
                )
            if not is_final:
                return

        # ── NORMAL streaming (non-resume): update streaming_txt in-place ──────
        if _lark_should_update_stream_element(
            resume_from=resume_from,
            form_data=form_data,
            msg_seq=msg_seq,
            is_final=is_final,
        ):
            cached = self.card_streaming_text.get(card_id)
            if text_message != cached:
                self.card_streaming_text[card_id] = text_message
                request: ContentCardElementRequest = (
                    ContentCardElementRequest.builder()
                    .card_id(card_id)
                    .element_id('streaming_txt')
                    .request_body(
                        ContentCardElementRequestBody.builder().content(text_message).sequence(card_sequence).build()
                    )
                    .build()
                )
                response: ContentCardElementResponse = await self.api_client.cardkit.v1.card_element.acontent(
                    request, req_opt
                )
                if not response.success():
                    raise Exception(
                        f'client.cardkit.v1.card_element.acontent failed, code: {response.code}, '
                        f'msg: {response.msg}, log_id: {response.get_log_id()}, '
                        f'resp: \n{json.dumps(json.loads(response.raw.content), indent=4, ensure_ascii=False)}'
                    )

        # ── FINAL chunk: full card layout update ─────────────────────────────
        if is_final:
            final_seq = self._next_card_sequence(card_id, card_sequence + 1)
            pre_pause = self.card_pre_pause_text.get(card_id, text_message)
            resume_cached = self.card_streaming_text.get(card_id, '')
            if form_data:
                if open_new_card:
                    # The old card has already been laid out into resume mode
                    # by the resume-transition block above (notice + resume
                    # placeholder). Finalise it as a frozen step snapshot and
                    # spawn a brand-new card to host the next human-input
                    # prompt — each step stays visible as its own card in the
                    # chat history.
                    new_card_id = await self._open_new_form_card(message_id, message_source, form_data)
                    if new_card_id is None:
                        # Fallback: keep the existing in-place behaviour so the
                        # workflow remains continuable even if creating the
                        # new card failed.
                        await self._update_card_layout(
                            card_id=card_id,
                            message_source=message_source,
                            text_message=pre_pause,
                            sequence=final_seq,
                            form_data=form_data,
                            resume_placeholder_text=resume_cached,
                            show_form_prompt=True,
                        )
                        self.card_streaming_text.pop(card_id, None)
                        self.card_pre_pause_text.pop(card_id, None)
                        self.card_form_content.pop(card_id, None)
                        self.card_form_input_defs.pop(card_id, None)
                        self.card_form_inputs.pop(card_id, None)
                    else:
                        # The old card is now a frozen snapshot; let go of its
                        # streaming-side state but keep its source registrations
                        # intact (no _drop_card_state) so historical button
                        # callbacks aimed at it can still be matched if needed.
                        self.card_streaming_text.pop(card_id, None)
                        self.card_pre_pause_text.pop(card_id, None)
                        self.card_form_content.pop(card_id, None)
                        self.card_form_input_defs.pop(card_id, None)
                        self.card_form_inputs.pop(card_id, None)
                        self.card_resume_transitioned.discard(card_id)
                else:
                    # Initial pause path: render prompt + buttons in place on
                    # the current card.
                    await self._update_card_layout(
                        card_id=card_id,
                        message_source=message_source,
                        text_message=text_message,
                        sequence=final_seq,
                        form_data=form_data,
                        show_form_prompt=True,
                    )
                    # Preserve the pre-pause text so the main content can be
                    # restored when the user clicks a button and the card
                    # transitions to resume mode.
                    self.card_pre_pause_text[card_id] = self.card_streaming_text.get(card_id, '')
                    self.card_streaming_text[card_id] = ''
                    # Store cleaned form state for the resume notice.
                    self.card_form_content[card_id] = _lark_visible_form_content(form_data)
                    self.card_form_input_defs[card_id] = _lark_form_input_defs(form_data)
                    self.card_form_inputs[card_id] = dict(form_data.get('inputs') or {})
            else:
                # Normal finish: keep pre-pause + resume content visible,
                # remove buttons/notice, drop the resume placeholder.
                await self._update_card_layout(
                    card_id=card_id,
                    message_source=message_source,
                    text_message=pre_pause,
                    sequence=final_seq,
                    form_data=None,
                    notice_text=selected_notice if resume_from else '',
                    resume_placeholder_text=resume_cached,
                )
                self._drop_card_state(card_id)
            self.card_id_dict.pop(message_id, None)

        # ── media (images / files) appended at the end ───────────────────────
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

    async def _add_form_buttons_to_card(
        self,
        card_id: str,
        message_source: platform_events.MessageEvent,
        form_data: dict,
        text_message: str = '',
        sequence: int = 1,
    ):
        """Update the entire card to include form action buttons.

        Uses card.aupdate to replace the card JSON with a template that
        includes the streaming text content plus interactive buttons.
        """
        await self._update_card_layout(
            card_id=card_id,
            message_source=message_source,
            text_message=text_message,
            sequence=sequence,
            form_data=form_data,
        )

    async def _remove_form_buttons_from_card(
        self,
        card_id: str,
        message_source: platform_events.MessageEvent,
        text_message: str = '',
        sequence: int = 1,
    ):
        """Replace the human-input card layout with the plain final layout."""
        await self._update_card_layout(
            card_id=card_id,
            message_source=message_source,
            text_message=text_message,
            sequence=sequence,
            form_data=None,
        )

    def _build_lark_form_field_elements(self, form_data: dict) -> tuple[list[dict], dict[str, str], list[str]]:
        elements: list[dict] = []
        input_name_map: dict[str, str] = {}
        file_help_lines: list[str] = []

        for idx, field in enumerate(_lark_current_input_defs(form_data), start=1):
            field_name = _dify_field_name(field)
            if not field_name:
                continue
            field_type = _dify_field_type(field)

            if field_type == 'select':
                options = _dify_select_options(field)
                component_name = _lark_form_component_name('Select', field_name, idx)
                input_name_map[component_name] = field_name
                elements.append(
                    {
                        'tag': 'select_static',
                        'name': component_name,
                        'label': {'tag': 'plain_text', 'content': field_name},
                        'placeholder': {'tag': 'plain_text', 'content': '请选择'},
                        'options': [
                            {
                                'text': {'tag': 'plain_text', 'content': option},
                                'value': option,
                            }
                            for option in options
                        ],
                        'type': 'default',
                        'width': 'fill',
                        'required': False,
                    }
                )
            elif field_type in {'file', 'file-list'}:
                allowed_types = ', '.join(field.get('allowed_file_types') or [])
                allowed = f' ({allowed_types})' if allowed_types else ''
                if field_type == 'file-list':
                    limit = field.get('number_limits')
                    suffix = f', up to {limit}' if limit else ''
                    file_help_lines.append(
                        f'- {field_name}: upload file(s){allowed}{suffix} in chat or reply `{field_name}: <url>`'
                    )
                else:
                    file_help_lines.append(
                        f'- {field_name}: upload a file{allowed} in chat or reply `{field_name}: <url>`'
                    )
            else:
                component_name = _lark_form_component_name('Input', field_name, idx)
                input_name_map[component_name] = field_name
                is_multiline = field_type in {'paragraph', 'long_text', 'multiline_text', 'textarea'}
                input_element = {
                    'tag': 'input',
                    'name': component_name,
                    'label': {'tag': 'plain_text', 'content': field_name},
                    'placeholder': {'tag': 'plain_text', 'content': '请输入'},
                    'default_value': _dify_default_value(field),
                    'width': 'fill',
                    'required': False,
                }
                if is_multiline:
                    input_element.update(
                        {
                            'input_type': 'multiline_text',
                            'rows': 3,
                            'auto_resize': True,
                            'max_rows': 6,
                        }
                    )
                elements.append(input_element)

        return elements, input_name_map, file_help_lines

    async def _update_card_layout(
        self,
        card_id: str,
        message_source: platform_events.MessageEvent,
        text_message: str = '',
        sequence: int = 1,
        form_data: dict | None = None,
        notice_text: str = '',
        resume_placeholder_text: str = '',
        show_form_prompt: bool = True,
    ):
        """Update the entire card layout.

        • form_data → show interactive buttons (initial Dify pause)
        • notice_text → replace buttons with a grey selection notice (resume transition)
        • resume_placeholder_text → add a streaming_txt_resume markdown element
        """
        form_data = form_data or {}
        actions = form_data.get('actions', [])
        form_token = form_data.get('form_token', '')
        workflow_run_id = form_data.get('workflow_run_id', '')
        pipeline_uuid = form_data.get('pipeline_uuid', '')
        node_title = form_data.get('node_title', '') or 'Human Input Required'
        form_content = form_data.get('form_content', '')
        input_defs = _lark_form_input_defs(form_data)

        # When form_data is set, the visible content is rendered inside the
        # interactive container, so the top streaming text should stay empty
        # to avoid duplicate text above the action area.
        #
        # For resume notice state, keep the existing text visible in the card
        # and only add the grey "selected" notice below it.
        if form_data:
            render_text_message = ''
        else:
            render_text_message = text_message

        # Determine session key from message source
        if isinstance(message_source, platform_events.GroupMessage):
            session_key = f'group_{message_source.group.id}'
        else:
            session_key = f'person_{message_source.sender.id}'

        # Build button elements matching the existing card template's thumbsup/down format
        action_buttons = []
        form_field_elements, input_name_map, file_help_lines = self._build_lark_form_field_elements(form_data)
        uses_form_container = bool(form_field_elements or input_name_map)
        if form_data:
            form_content = _lark_visible_form_content(form_data)
            self.card_form_content[card_id] = form_content
            self.card_form_input_defs[card_id] = input_defs
            self.card_form_inputs[card_id] = dict(form_data.get('inputs') or {})
        is_field_step = bool(form_data.get('_current_input_field')) and not form_data.get('_action_select_only')
        if is_field_step:
            actions = (
                [{'_input_progress': True, 'id': '', 'title': 'Next', 'button_style': 'primary'}]
                if uses_form_container
                else []
            )
        for action in actions:
            action_id = action.get('id', '')
            action_title = action.get('title', action_id)
            button_style = action.get('button_style', 'default')

            if button_style == 'primary':
                lark_button_type = 'primary'
            elif button_style == 'danger':
                lark_button_type = 'danger'
            else:
                lark_button_type = 'default'

            button = {
                'tag': 'button',
                'text': {'tag': 'plain_text', 'content': action_title},
                'type': lark_button_type,
                'width': 'fill',
                'size': 'medium',
                'hover_tips': {'tag': 'plain_text', 'content': action_title},
                'behaviors': [
                    {
                        'type': 'callback',
                        'value': {
                            'form_action': True,
                            'form_token': form_token,
                            'workflow_run_id': workflow_run_id,
                            'pipeline_uuid': pipeline_uuid,
                            'action_id': action_id,
                            'session_key': session_key,
                            'card_id': card_id,
                            'input_name_map': input_name_map,
                            '_input_progress': bool(action.get('_input_progress')),
                        },
                    }
                ],
                'margin': '0px 0px 0px 0px',
            }
            if uses_form_container:
                button['name'] = _lark_form_component_name('Button', action_id or action_title, len(action_buttons) + 1)
                button['form_action_type'] = 'submit'
            action_buttons.append(button)

        interactive_elements = []
        if form_data:
            if show_form_prompt:
                interactive_elements = [
                    {
                        'tag': 'markdown',
                        'content': f'**[Human Input Required] {node_title}**',
                        'text_align': 'left',
                        'text_size': 'normal',
                        'margin': '0px 0px 4px 0px',
                    }
                ]
                if form_content:
                    interactive_elements.append(
                        {
                            'tag': 'markdown',
                            'content': form_content,
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 8px 0px',
                        }
                    )
                completed_lines = (
                    []
                    if form_data.get('_action_select_only')
                    else _lark_completed_input_lines(
                        {
                            'input_defs': input_defs,
                            'inputs': form_data.get('inputs') or {},
                        }
                    )
                )
                if completed_lines:
                    interactive_elements.append(
                        {
                            'tag': 'markdown',
                            'content': '---\n' + '\n'.join(completed_lines),
                            'text_align': 'left',
                            'text_size': 'normal',
                            'margin': '0px 0px 8px 0px',
                        }
                    )
                if file_help_lines:
                    interactive_elements.append(
                        {
                            'tag': 'markdown',
                            'content': '\n'.join(file_help_lines),
                            'text_align': 'left',
                            'text_size': 'normal',
                            'text_color': 'grey',
                            'margin': '0px 0px 8px 0px',
                        }
                    )
            if action_buttons:
                interactive_elements.append(
                    {
                        'tag': 'column_set',
                        'horizontal_spacing': '8px',
                        'horizontal_align': 'left',
                        'margin': '0px 0px 0px 0px',
                        'columns': [
                            {
                                'tag': 'column',
                                'width': 'weighted',
                                'elements': [btn],
                                'padding': '0px 0px 0px 0px',
                            }
                            for btn in action_buttons
                        ],
                    }
                )

        # Build the full card JSON with buttons, same structure as create_card_id
        # ── mid_section: either form buttons, resume notice, or empty ──
        mid_section_elements = []
        if form_data:
            if uses_form_container:
                form_elements = interactive_elements[:-1] if action_buttons else interactive_elements[:]
                form_elements.extend(form_field_elements)
                if action_buttons:
                    form_elements.append(interactive_elements[-1])
                mid_section_elements = [
                    {
                        'tag': 'form',
                        'name': _lark_form_component_name('Form', form_token or workflow_run_id or card_id, 1),
                        'direction': 'vertical',
                        'vertical_spacing': '12px',
                        'margin': '12px 0px 8px 0px',
                        'padding': '12px 12px 12px 12px',
                        'elements': form_elements,
                    },
                    {'tag': 'hr', 'margin': '0px 0px 0px 0px'},
                ]
            else:
                mid_section_elements = [
                    {
                        'tag': 'interactive_container',
                        'margin': '12px 0px 8px 0px',
                        'padding': '12px 12px 12px 12px',
                        'has_border': True,
                        'elements': interactive_elements,
                    },
                    {'tag': 'hr', 'margin': '0px 0px 0px 0px'},
                ]
        elif notice_text:
            mid_section_elements = [
                {
                    'tag': 'markdown',
                    'content': notice_text,
                    'text_align': 'left',
                    'text_size': 'normal',
                    'margin': '8px 0px 4px 0px',
                    'text_color': 'grey',
                },
                {'tag': 'hr', 'margin': '0px 0px 0px 0px'},
            ]

        # ── resume placeholder element (empty, filled via acontent on each chunk) ──
        resume_elements = []
        if resume_placeholder_text:
            resume_elements = [
                {
                    'tag': 'markdown',
                    'content': resume_placeholder_text,
                    'text_align': 'left',
                    'text_size': 'normal',
                    'margin': '0px 0px 0px 0px',
                    'element_id': 'streaming_txt_resume',
                },
            ]

        card_data = {
            'schema': '2.0',
            'config': {
                'update_multi': True,
                'streaming_mode': False,
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
                        'content': render_text_message,
                        'text_align': 'left',
                        'text_size': 'normal',
                        'margin': '0px 0px 0px 0px',
                        'element_id': 'streaming_txt',
                    },
                    *mid_section_elements,
                    *resume_elements,
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
                            *(
                                []
                                if form_data
                                else [
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
                                                'behaviors': [{'type': 'callback', 'value': {'feedback': '有帮助'}}],
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
                                                'behaviors': [{'type': 'callback', 'value': {'feedback': '无帮助'}}],
                                                'margin': '0px 0px 0px 0px',
                                            }
                                        ],
                                        'padding': '0px 0px 0px 0px',
                                        'vertical_spacing': '8px',
                                        'horizontal_align': 'left',
                                        'vertical_align': 'top',
                                        'margin': '0px 0px 0px 0px',
                                    },
                                ]
                            ),
                        ],
                        'margin': '0px 0px 4px 0px',
                    },
                ],
            },
        }

        try:
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

            request: UpdateCardRequest = (
                UpdateCardRequest.builder()
                .card_id(card_id)
                .request_body(
                    UpdateCardRequestBody.builder()
                    .sequence(sequence)
                    .uuid(str(uuid.uuid4()))
                    .card(Card.builder().type('card_json').data(json.dumps(card_data)).build())
                    .build()
                )
                .build()
            )
            response: UpdateCardResponse = await self.api_client.cardkit.v1.card.aupdate(request, req_opt)
            if not response.success():
                await self.logger.error(
                    f'Failed to update lark card with form buttons: code={response.code}, msg={response.msg}, '
                    f'log_id={response.get_log_id()}, resp={getattr(getattr(response, "raw", None), "content", None)}'
                )
        except Exception:
            await self.logger.error(f'Error updating lark card with form buttons: {traceback.format_exc()}')

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
            elif 'card.action.trigger' == type:
                try:
                    event_data = data.get('event', {})
                    operator = event_data.get('operator', {})
                    action = event_data.get('action', {})
                    context_data = event_data.get('context', {})

                    action_value_obj = _lark_mapping_from_value(action.get('value', {}))
                    action_value = action_value_obj.get('feedback', '') if isinstance(action_value_obj, dict) else ''

                    if isinstance(action_value_obj, dict) and action_value_obj.get('form_action'):
                        form_token = action_value_obj.get('form_token', '')
                        workflow_run_id = action_value_obj.get('workflow_run_id', '')
                        action_id = action_value_obj.get('action_id', '')
                        session_key = action_value_obj.get('session_key', '')
                        form_inputs = _lark_extract_action_form_inputs(action, action_value_obj)

                        if session_key.startswith('group_') or session_key.startswith('g:'):
                            launcher_type = provider_session.LauncherTypes.GROUP
                            launcher_id = (
                                session_key.split(':', 1)[1]
                                if session_key.startswith('g:')
                                else session_key[len('group_') :]
                            )
                        else:
                            launcher_type = provider_session.LauncherTypes.PERSON
                            launcher_id = (
                                session_key.split(':', 1)[1]
                                if session_key.startswith('p:')
                                else session_key[len('person_') :]
                            )

                        form_action_data = {
                            'form_token': form_token,
                            'workflow_run_id': workflow_run_id,
                            'action_id': action_id,
                            'user': f'{launcher_type.value}_{launcher_id}',
                            'inputs': form_inputs,
                        }
                        if action_value_obj.get('_input_progress'):
                            form_action_data['_input_progress'] = True

                        open_message_id = context_data.get('open_message_id')
                        card_id = self.reply_message_card_ids.get(str(open_message_id)) if open_message_id else None
                        if not card_id:
                            card_id = str(action_value_obj.get('card_id') or '')
                        if card_id and form_inputs:
                            cached_inputs = dict(self.card_form_inputs.get(card_id) or {})
                            cached_inputs.update(form_inputs)
                            self.card_form_inputs[card_id] = cached_inputs
                            if self.ap is not None:
                                self.ap.logger.info(
                                    f'Lark form action inputs cached: card_id={card_id} '
                                    f'open_message_id={open_message_id} keys={list(form_inputs.keys())}'
                                )

                        source_time = datetime.datetime.now()
                        message_chain = platform_message.MessageChain(
                            [platform_message.Plain(text=f'[Form Action: {action_id or "confirm"}]')]
                        )
                        if open_message_id:
                            message_chain.insert(
                                0,
                                platform_message.Source(
                                    id=open_message_id,
                                    time=source_time,
                                ),
                            )

                        user_id = operator.get('open_id') or operator.get('user_id') or str(launcher_id)
                        event_time = source_time.timestamp()
                        if launcher_type == provider_session.LauncherTypes.GROUP:
                            synthetic_event = platform_events.GroupMessage(
                                sender=platform_entities.GroupMember(
                                    id=user_id,
                                    member_name='',
                                    permission=platform_entities.Permission.Member,
                                    group=platform_entities.Group(
                                        id=launcher_id,
                                        name='',
                                        permission=platform_entities.Permission.Member,
                                    ),
                                ),
                                message_chain=message_chain,
                                time=event_time,
                                source_platform_object=data,
                            )
                        else:
                            synthetic_event = platform_events.FriendMessage(
                                sender=platform_entities.Friend(
                                    id=user_id,
                                    nickname='',
                                    remark='',
                                ),
                                message_chain=message_chain,
                                time=event_time,
                                source_platform_object=data,
                            )

                        bot_uuid = ''
                        pipeline_uuid = action_value_obj.get('pipeline_uuid') or None
                        for bot in self.ap.platform_mgr.bots:
                            if bot.adapter is self:
                                bot_uuid = bot.bot_entity.uuid
                                pipeline_uuid = pipeline_uuid or bot.bot_entity.use_pipeline_uuid
                                break

                        await self.ap.query_pool.add_query(
                            bot_uuid=bot_uuid,
                            launcher_type=launcher_type,
                            launcher_id=launcher_id,
                            sender_id=user_id,
                            message_event=synthetic_event,
                            message_chain=message_chain,
                            adapter=self,
                            pipeline_uuid=pipeline_uuid,
                            variables={
                                '_dify_form_action': form_action_data,
                                '_routed_by_rule': True,
                            },
                        )

                        return {'toast': {'type': 'success', 'content': '操作成功'}}

                    if action_value == '有帮助':
                        feedback_type = 1
                    elif action_value == '无帮助':
                        feedback_type = 2
                    else:
                        return {'toast': {'type': 'success', 'content': '操作成功'}}

                    user_id = operator.get('open_id') or operator.get('user_id')
                    open_chat_id = context_data.get('open_chat_id')
                    open_message_id = context_data.get('open_message_id')

                    if open_chat_id:
                        session_id = f'group_{open_chat_id}'
                    elif user_id:
                        session_id = f'person_{user_id}'
                    else:
                        session_id = None

                    # Resolve monitoring message ID from reply message mapping
                    monitoring_msg_id = None
                    if open_message_id and open_message_id in self.reply_to_monitoring_msg:
                        monitoring_msg_id = self.reply_to_monitoring_msg[open_message_id][0]

                    feedback_event = platform_events.FeedbackEvent(
                        feedback_id=data.get('header', {}).get('event_id', str(uuid.uuid4())),
                        feedback_type=feedback_type,
                        feedback_content=action_value,
                        user_id=user_id,
                        session_id=session_id,
                        message_id=open_message_id,
                        stream_id=monitoring_msg_id,
                        source_platform_object=data,
                    )

                    if platform_events.FeedbackEvent in self.listeners:
                        await self.listeners[platform_events.FeedbackEvent](feedback_event, self)

                    return {'toast': {'type': 'success', 'content': '感谢您的反馈'}}
                except Exception:
                    await self.logger.error(f'Error in lark card action callback: {traceback.format_exc()}')
                    return {'toast': {'type': 'error', 'content': '反馈处理失败'}}

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
