from __future__ import annotations

import asyncio
import base64
import json
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple
from urllib.parse import unquote

import httpx
from Crypto.Cipher import AES
from quart import Quart, request, Response, jsonify

from langbot.libs.wecom_ai_bot_api import wecombotevent
from langbot.libs.wecom_ai_bot_api.WXBizMsgCrypt3 import WXBizMsgCrypt

if TYPE_CHECKING:
    from langbot.pkg.platform.logger import EventLogger


@dataclass
class StreamChunk:
    """描述单次推送给企业微信的流式片段。"""

    # 需要返回给企业微信的文本内容
    content: str

    # 标记是否为最终片段，对应企业微信协议里的 finish 字段
    is_final: bool = False

    # 预留额外元信息，未来支持多模态扩展时可使用
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamSession:
    """维护一次企业微信流式会话的上下文。"""

    # 企业微信要求的 stream_id，用于标识后续刷新请求
    stream_id: str

    # 原始消息的 msgid，便于与流水线消息对应
    msg_id: str

    # 群聊会话标识（单聊时为空）
    chat_id: Optional[str]

    # 触发消息的发送者
    user_id: Optional[str]

    # 会话创建时间
    created_at: float = field(default_factory=time.time)

    # 最近一次被访问的时间，cleanup 依据该值判断过期
    last_access: float = field(default_factory=time.time)

    # 将流水线增量结果缓存到队列，刷新请求逐条消费
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    # 是否已经完成（收到最终片段）
    finished: bool = False

    # 缓存最近一次片段，处理重试或超时兜底
    last_chunk: Optional[StreamChunk] = None

    # 反馈 ID，用于接收用户点赞/点踩反馈
    feedback_id: Optional[str] = None

    # Dify 人工输入暂停态：runner 把 _form_data 传过来时填充。
    # 一旦设置，下次企微 followup 请求时返回 button_interaction 模板卡
    # 替代 stream chunk。点击按钮会回调 template_card_event，EventKey
    # 就是 Dify 的 action_id。
    pending_form: Optional[dict] = None

    # template_card task_id（企微要求 button_interaction 必填且不可重复）。
    # 创建 pending_form 时生成；按钮点击回调里用来反查 session。
    pending_form_task_id: Optional[str] = None


class StreamSessionManager:
    """管理 stream 会话的生命周期，并负责队列的生产消费。"""

    # Sessions with registered feedback_ids use a longer TTL to survive the
    # full like → cancel → dislike feedback flow. Must align with the adapter's
    # _stream_to_monitoring_msg TTL (wecombot.py).
    _FEEDBACK_SESSION_TTL = 600  # 10 minutes

    def __init__(self, logger: EventLogger, ttl: int = 60) -> None:
        self.logger = logger

        self.ttl = ttl  # 超时时间（秒），超过该时间未被访问的会话会被清理由 cleanup
        self._sessions: dict[str, StreamSession] = {}  # stream_id -> StreamSession 映射
        self._msg_index: dict[str, str] = {}  # msgid -> stream_id 映射，便于流水线根据消息 ID 找到会话
        self._feedback_index: dict[str, str] = {}  # feedback_id -> stream_id 映射
        # task_id (button_interaction template_card 的) -> stream_id 映射，
        # 用于按钮点击回调里反查 pending_form。
        self._task_index: dict[str, str] = {}

    def get_stream_id_by_msg(self, msg_id: str) -> Optional[str]:
        if not msg_id:
            return None
        return self._msg_index.get(msg_id)

    def get_session(self, stream_id: str) -> Optional[StreamSession]:
        return self._sessions.get(stream_id)

    def get_session_by_feedback_id(self, feedback_id: str) -> Optional[StreamSession]:
        """根据 feedback_id 查找会话。

        Args:
            feedback_id: 企业微信反馈事件中的反馈 ID。

        Returns:
            Optional[StreamSession]: 找到的会话实例，未找到返回 None。
        """
        if not feedback_id:
            return None
        stream_id = self._feedback_index.get(feedback_id)
        if stream_id:
            return self._sessions.get(stream_id)
        return None

    def register_feedback_id(self, stream_id: str, feedback_id: str) -> None:
        """注册 feedback_id 与 stream_id 的映射。

        Args:
            stream_id: 企业微信流式会话 ID。
            feedback_id: 反馈 ID。
        """
        if feedback_id and stream_id:
            self._feedback_index[feedback_id] = stream_id

    def set_pending_form(self, stream_id: str, form_data: dict, task_id: str) -> None:
        """把 Dify 人工输入暂停态绑定到 stream session。

        下一次企微 followup 请求时，adapter 检测到 pending_form，
        返回 button_interaction 模板卡而不是 stream chunk。
        """
        session = self._sessions.get(stream_id)
        if not session:
            return
        session.pending_form = form_data
        session.pending_form_task_id = task_id
        if task_id:
            self._task_index[task_id] = stream_id

    def get_session_by_task_id(self, task_id: str) -> Optional[StreamSession]:
        """按按钮点击回调里的 TaskId 反查 session。"""
        if not task_id:
            return None
        stream_id = self._task_index.get(task_id)
        if not stream_id:
            return None
        return self._sessions.get(stream_id)

    def clear_pending_form(self, stream_id: str) -> None:
        """按钮点击消费完后清掉 pending_form，避免重复弹卡。"""
        session = self._sessions.get(stream_id)
        if not session:
            return
        task_id = session.pending_form_task_id
        session.pending_form = None
        session.pending_form_task_id = None
        if task_id:
            self._task_index.pop(task_id, None)

    def create_or_get(self, msg_json: dict[str, Any]) -> tuple[StreamSession, bool]:
        """根据企业微信回调创建或获取会话。

        Args:
            msg_json: 企业微信解密后的回调 JSON。

        Returns:
            Tuple[StreamSession, bool]: `StreamSession` 为会话实例，`bool` 指示是否为新建会话。

        Example:
            在首次回调中调用，得到 `is_new=True` 后再触发流水线。
        """
        msg_id = msg_json.get('msgid', '')
        if msg_id and msg_id in self._msg_index:
            stream_id = self._msg_index[msg_id]
            session = self._sessions.get(stream_id)
            if session:
                session.last_access = time.time()
                return session, False

        stream_id = str(uuid.uuid4())
        session = StreamSession(
            stream_id=stream_id,
            msg_id=msg_id,
            chat_id=msg_json.get('chatid'),
            user_id=msg_json.get('from', {}).get('userid'),
        )

        if msg_id:
            self._msg_index[msg_id] = stream_id
        self._sessions[stream_id] = session
        return session, True

    async def publish(self, stream_id: str, chunk: StreamChunk) -> bool:
        """向 stream 队列写入新的增量片段。

        Args:
            stream_id: 企业微信分配的流式会话 ID。
            chunk: 待发送的增量片段。

        Returns:
            bool: 当流式队列存在并成功入队时返回 True。

        Example:
            在收到模型增量后调用 `await manager.publish('sid', StreamChunk('hello'))`。
        """
        session = self._sessions.get(stream_id)
        if not session:
            return False

        session.last_access = time.time()
        session.last_chunk = chunk

        try:
            session.queue.put_nowait(chunk)
        except asyncio.QueueFull:
            # 默认无界队列，此处兜底防御
            await session.queue.put(chunk)

        if chunk.is_final:
            session.finished = True

        return True

    async def consume(self, stream_id: str, timeout: float = 0.5) -> Optional[StreamChunk]:
        """从队列中取出一个片段，若超时返回 None。

        Args:
            stream_id: 企业微信流式会话 ID。
            timeout: 取片段的最长等待时间（秒）。

        Returns:
            Optional[StreamChunk]: 成功时返回片段，超时或会话不存在时返回 None。

        Example:
            企业微信刷新到达时调用，若队列有数据则立即返回 `StreamChunk`。
        """
        session = self._sessions.get(stream_id)
        if not session:
            return None

        session.last_access = time.time()

        try:
            chunk = await asyncio.wait_for(session.queue.get(), timeout)
            session.last_access = time.time()
            if chunk.is_final:
                session.finished = True
            return chunk
        except asyncio.TimeoutError:
            if session.finished and session.last_chunk:
                return session.last_chunk
            return None

    def mark_finished(self, stream_id: str) -> None:
        session = self._sessions.get(stream_id)
        if session:
            session.finished = True
            session.last_access = time.time()

    def cleanup(self) -> None:
        """定期清理过期会话，防止队列与映射无上限累积。

        已注册 feedback_id 的会话使用更长的 TTL，确保用户在点赞/取消/点踩流程中
        不会因为 session 被提前清除而丢失上下文信息。
        """
        now = time.time()
        expired: list[str] = []
        for stream_id, session in self._sessions.items():
            # Sessions with registered feedback_ids use a longer TTL
            effective_ttl = self._FEEDBACK_SESSION_TTL if session.feedback_id else self.ttl
            if now - session.last_access > effective_ttl:
                expired.append(stream_id)

        for stream_id in expired:
            session = self._sessions.pop(stream_id, None)
            if not session:
                continue
            msg_id = session.msg_id
            if msg_id and self._msg_index.get(msg_id) == stream_id:
                self._msg_index.pop(msg_id, None)
            # Clean up feedback index for expired sessions
            if session.feedback_id:
                self._feedback_index.pop(session.feedback_id, None)


def _decrypt_file(encrypted_data: bytes, aes_key_str: str) -> bytes:
    """Decrypt AES-256-CBC encrypted file data.

    Aligned with the official WeCom AI Bot Python SDK (crypto_utils.py).

    Args:
        encrypted_data: The raw encrypted bytes.
        aes_key_str: Base64-encoded AES key (may lack padding).

    Returns:
        Decrypted bytes with PKCS#7 padding removed.
    """
    if not encrypted_data:
        raise ValueError('encrypted_data is empty')
    if not aes_key_str:
        raise ValueError('aes_key is empty')

    # Python's base64.b64decode requires proper padding (length % 4 == 0).
    # Node.js Buffer.from tolerates missing '=', so we must pad manually.
    remainder = len(aes_key_str) % 4
    if remainder != 0:
        aes_key_str = aes_key_str + '=' * (4 - remainder)
    key = base64.b64decode(aes_key_str)

    iv = key[:16]

    cipher = AES.new(key, AES.MODE_CBC, iv)

    # Ensure encrypted data is aligned to AES block size (16 bytes).
    # Node.js setAutoPadding(false) silently handles unaligned data,
    # but PyCryptodome will raise an error.
    block_size = 16
    data_remainder = len(encrypted_data) % block_size
    if data_remainder != 0:
        encrypted_data = encrypted_data + b'\x00' * (block_size - data_remainder)

    decrypted = cipher.decrypt(encrypted_data)

    # Remove PKCS#7 padding with validation
    if len(decrypted) == 0:
        raise ValueError('Decrypted data is empty')

    pad_len = decrypted[-1]
    if pad_len < 1 or pad_len > 32 or pad_len > len(decrypted):
        raise ValueError(f'Invalid PKCS#7 padding value: {pad_len}')

    # Verify all padding bytes are consistent
    for i in range(len(decrypted) - pad_len, len(decrypted)):
        if decrypted[i] != pad_len:
            raise ValueError('Invalid PKCS#7 padding: padding bytes mismatch')

    return decrypted[: len(decrypted) - pad_len]


def _extract_filename(content_disposition: str) -> Optional[str]:
    """Extract filename from a Content-Disposition header value."""
    if not content_disposition:
        return None
    # RFC 5987: filename*=UTF-8''xxx
    utf8_match = re.search(r"filename\*=UTF-8''([^;\s]+)", content_disposition, re.IGNORECASE)
    if utf8_match:
        return unquote(utf8_match.group(1))
    # Standard: filename="xxx" or filename=xxx
    match = re.search(r'filename="?([^";\s]+)"?', content_disposition, re.IGNORECASE)
    if match:
        return unquote(match.group(1))
    return None


def _bytes_to_data_uri(data: bytes) -> str:
    """Convert raw bytes to a data URI with auto-detected MIME type."""
    if data.startswith(b'\xff\xd8'):
        mime_type = 'image/jpeg'
    elif data.startswith(b'\x89PNG'):
        mime_type = 'image/png'
    elif data.startswith((b'GIF87a', b'GIF89a')):
        mime_type = 'image/gif'
    elif data.startswith(b'BM'):
        mime_type = 'image/bmp'
    elif data.startswith(b'II*\x00') or data.startswith(b'MM\x00*'):
        mime_type = 'image/tiff'
    elif data[:4] == b'%PDF':
        mime_type = 'application/pdf'
    elif data[:4] == b'PK\x03\x04':
        mime_type = 'application/zip'
    else:
        mime_type = 'application/octet-stream'

    base64_str = base64.b64encode(data).decode('utf-8')
    return f'data:{mime_type};base64,{base64_str}'


async def download_encrypted_file(
    download_url: str, aes_key: str, logger: EventLogger
) -> Tuple[Optional[bytes], Optional[str]]:
    """Download an AES-encrypted file from WeChat Work and decrypt it.

    Args:
        download_url: The encrypted file download URL.
        aes_key: The AES key for decryption (base64-encoded, per-message aeskey
                 or platform EncodingAESKey).
        logger: Logger instance.

    Returns:
        A tuple of (decrypted_bytes, filename) or (None, None) on failure.
    """
    if not download_url:
        return None, None
    if not aes_key:
        await logger.error('download_encrypted_file: aes_key is empty, cannot decrypt')
        return None, None

    filename: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(download_url)
            if response.status_code != 200:
                await logger.error(f'Failed to download file (HTTP {response.status_code}): {response.text[:200]}')
                return None, None
            encrypted_bytes = response.content
            filename = _extract_filename(response.headers.get('content-disposition', ''))
    except Exception:
        await logger.error(f'Failed to download file: {traceback.format_exc()}')
        return None, None

    try:
        decrypted = _decrypt_file(encrypted_bytes, aes_key)
        return decrypted, filename
    except Exception:
        await logger.error(f'Failed to decrypt file: {traceback.format_exc()}')
        return None, None


async def parse_wecom_bot_message(
    msg_json: dict[str, Any], encoding_aes_key: str, logger: EventLogger
) -> dict[str, Any]:
    """Parse a decrypted WeChat Work AI Bot message JSON into a unified message dict.

    This is the shared message parsing logic used by both webhook and WebSocket modes.

    Args:
        msg_json: The decrypted message JSON from WeChat Work.
        encoding_aes_key: AES key for file decryption.
        logger: Logger instance.

    Returns:
        A dict suitable for constructing a WecomBotEvent.
    """
    message_data: dict[str, Any] = {}

    msg_type = msg_json.get('msgtype', '')
    if msg_type:
        message_data['msgtype'] = msg_type

    if msg_json.get('chattype', '') == 'single':
        message_data['type'] = 'single'
    elif msg_json.get('chattype', '') == 'group':
        message_data['type'] = 'group'

    max_inline_file_size = 5 * 1024 * 1024

    async def _safe_download(url: str, per_msg_aeskey: str = '') -> Tuple[Optional[bytes], Optional[str]]:
        """Download and decrypt a file, preferring per-message aeskey over platform key."""
        if not url:
            return None, None
        key = per_msg_aeskey or encoding_aes_key
        if not key:
            await logger.warning('No AES key available for file decryption, skipping download')
            return None, None
        return await download_encrypted_file(url, key, logger)

    async def _safe_download_as_data_uri(url: str, per_msg_aeskey: str = '') -> Optional[str]:
        """Download, decrypt, and convert to data URI for backward compatibility."""
        data, _filename = await _safe_download(url, per_msg_aeskey)
        if data:
            return _bytes_to_data_uri(data)
        return None

    if msg_type == 'text':
        message_data['content'] = msg_json.get('text', {}).get('content')
    elif msg_type == 'markdown':
        message_data['content'] = msg_json.get('markdown', {}).get('content') or msg_json.get('text', {}).get(
            'content', ''
        )
    elif msg_type == 'image':
        image_info = msg_json.get('image', {})
        picurl = image_info.get('url', '')
        per_msg_aeskey = image_info.get('aeskey', '')
        base64_data = await _safe_download_as_data_uri(picurl, per_msg_aeskey)
        if base64_data:
            message_data['picurl'] = base64_data
            message_data['images'] = [base64_data]
    elif msg_type == 'voice':
        voice_info = msg_json.get('voice', {}) or {}
        download_url = voice_info.get('url')
        per_msg_aeskey = voice_info.get('aeskey', '')
        message_data['voice'] = {
            'url': download_url,
            'md5sum': voice_info.get('md5sum') or voice_info.get('md5'),
            'filesize': voice_info.get('filesize') or voice_info.get('size'),
            'sdkfileid': voice_info.get('sdkfileid') or voice_info.get('fileid'),
        }
        if voice_info.get('content'):
            message_data['content'] = voice_info.get('content')
        # if (message_data['voice'].get('filesize') or 0) <= max_inline_file_size:
        #     voice_base64 = await _safe_download_as_data_uri(download_url, per_msg_aeskey)
        #     if voice_base64:
        #         message_data['voice']['base64'] = voice_base64
    elif msg_type == 'video':
        video_info = msg_json.get('video', {}) or {}
        download_url = video_info.get('url')
        per_msg_aeskey = video_info.get('aeskey', '')
        video_data = {
            'url': download_url,
            'filesize': video_info.get('filesize') or video_info.get('size'),
            'sdkfileid': video_info.get('sdkfileid') or video_info.get('fileid'),
            'md5sum': video_info.get('md5sum') or video_info.get('md5'),
            'filename': video_info.get('filename') or video_info.get('name'),
        }
        # if (video_data.get('filesize') or 0) <= max_inline_file_size:
        #     video_base64 = await _safe_download_as_data_uri(download_url, per_msg_aeskey)
        #     if video_base64:
        #         video_data['base64'] = video_base64
        # 应为需要解密，但是目前暂时不能下载到内部进行解密，所以先将下载链接拼接aeskey返回给用户，由插件去处理该链接的下载和解密逻辑
        video_data['download_url'] = download_url + f'?aeskey={per_msg_aeskey}'
        message_data['video'] = video_data
    elif msg_type == 'file':
        file_info = msg_json.get('file', {}) or {}
        download_url = file_info.get('url') or file_info.get('fileurl')
        per_msg_aeskey = file_info.get('aeskey', '')
        file_data = {
            'filename': file_info.get('filename') or file_info.get('name'),
            'filesize': file_info.get('filesize') or file_info.get('size'),
            'md5sum': file_info.get('md5sum') or file_info.get('md5'),
            'sdkfileid': file_info.get('sdkfileid') or file_info.get('fileid'),
            'download_url': download_url,
            'extra': file_info,
        }
        # if (file_data.get('filesize') or 0) <= max_inline_file_size:
        #     file_bytes, dl_filename = await _safe_download(download_url, per_msg_aeskey)
        #     if file_bytes:
        #         file_data['base64'] = _bytes_to_data_uri(file_bytes)
        #         if dl_filename and not file_data.get('filename'):
        #             file_data['filename'] = dl_filename

        # 应为需要解密，但是目前暂时不能下载到内部进行解密，所以先将下载链接拼接aeskey返回给用户，由插件去处理该链接的下载和解密逻辑
        file_data['download_url'] = download_url + f'?aeskey={per_msg_aeskey}'
        message_data['file'] = file_data
    elif msg_type == 'link':
        message_data['link'] = msg_json.get('link', {})
        if not message_data.get('content'):
            title = message_data['link'].get('title', '')
            desc = message_data['link'].get('description') or message_data['link'].get('digest', '')
            message_data['content'] = '\n'.join(filter(None, [title, desc]))
    elif msg_type == 'mixed':
        items = msg_json.get('mixed', {}).get('msg_item', [])
        texts = []
        images = []
        files = []
        voices = []
        videos = []
        links = []
        for item in items:
            item_type = item.get('msgtype')
            if item_type == 'text':
                texts.append(item.get('text', {}).get('content', ''))
            elif item_type == 'image':
                img_info = item.get('image', {})
                img_url = img_info.get('url')
                img_aeskey = img_info.get('aeskey', '')
                base64_data = await _safe_download_as_data_uri(img_url, img_aeskey)
                if base64_data:
                    images.append(base64_data)
            elif item_type == 'file':
                file_info = item.get('file', {}) or {}
                download_url = file_info.get('url') or file_info.get('fileurl')
                item_aeskey = file_info.get('aeskey', '')
                file_data = {
                    'filename': file_info.get('filename') or file_info.get('name'),
                    'filesize': file_info.get('filesize') or file_info.get('size'),
                    'md5sum': file_info.get('md5sum') or file_info.get('md5'),
                    'sdkfileid': file_info.get('sdkfileid') or file_info.get('fileid'),
                    'download_url': download_url,
                    'extra': file_info,
                }
                if (file_data.get('filesize') or 0) <= max_inline_file_size:
                    file_bytes, dl_filename = await _safe_download(download_url, item_aeskey)
                    if file_bytes:
                        file_data['base64'] = _bytes_to_data_uri(file_bytes)
                        if dl_filename and not file_data.get('filename'):
                            file_data['filename'] = dl_filename
                files.append(file_data)
            elif item_type == 'voice':
                voice_info = item.get('voice', {}) or {}
                download_url = voice_info.get('url')
                item_aeskey = voice_info.get('aeskey', '')
                voice_data = {
                    'url': download_url,
                    'md5sum': voice_info.get('md5sum') or voice_info.get('md5'),
                    'filesize': voice_info.get('filesize') or voice_info.get('size'),
                    'sdkfileid': voice_info.get('sdkfileid') or voice_info.get('fileid'),
                }
                if voice_info.get('content'):
                    texts.append(voice_info.get('content'))
                if (voice_data.get('filesize') or 0) <= max_inline_file_size:
                    voice_base64 = await _safe_download_as_data_uri(download_url, item_aeskey)
                    if voice_base64:
                        voice_data['base64'] = voice_base64
                voices.append(voice_data)
            elif item_type == 'video':
                video_info = item.get('video', {}) or {}
                download_url = video_info.get('url')
                item_aeskey = video_info.get('aeskey', '')
                video_data = {
                    'url': download_url,
                    'filesize': video_info.get('filesize') or video_info.get('size'),
                    'sdkfileid': video_info.get('sdkfileid') or video_info.get('fileid'),
                    'md5sum': video_info.get('md5sum') or video_info.get('md5'),
                    'filename': video_info.get('filename') or video_info.get('name'),
                }
                if (video_data.get('filesize') or 0) <= max_inline_file_size:
                    video_base64 = await _safe_download_as_data_uri(download_url, item_aeskey)
                    if video_base64:
                        video_data['base64'] = video_base64
                videos.append(video_data)
            elif item_type == 'link':
                links.append(item.get('link', {}))

        if texts:
            message_data['content'] = ' '.join(texts)
        if images:
            message_data['images'] = images
            message_data['picurl'] = images[0]
        if files:
            message_data['files'] = files
            message_data['file'] = files[0]
        if voices:
            message_data['voices'] = voices
            message_data['voice'] = voices[0]
        if videos:
            message_data['videos'] = videos
            message_data['video'] = videos[0]
        if links:
            message_data['link'] = links[0]
        if items:
            message_data['attachments'] = items
    else:
        message_data['raw_msg'] = msg_json

    from_info = msg_json.get('from', {})
    message_data['userid'] = from_info.get('userid', '')
    message_data['username'] = from_info.get('alias', '') or from_info.get('name', '') or from_info.get('userid', '')

    if msg_json.get('chattype', '') == 'group':
        message_data['chatid'] = msg_json.get('chatid', '')
        message_data['chatname'] = msg_json.get('chatname', '') or msg_json.get('chatid', '')

    message_data['msgid'] = msg_json.get('msgid', '')

    if msg_json.get('aibotid'):
        message_data['aibotid'] = msg_json.get('aibotid', '')

    # Handle quote (referenced message) - important for group chat file references
    quote_info = msg_json.get('quote')
    if quote_info:
        quote_data: dict[str, Any] = {}
        quote_type = quote_info.get('msgtype', '')
        quote_data['msgtype'] = quote_type

        if quote_type == 'text':
            quote_data['content'] = quote_info.get('text', {}).get('content', '')
        elif quote_type == 'image':
            img_info = quote_info.get('image', {})
            img_url = img_info.get('url', '')
            img_aeskey = img_info.get('aeskey', '')
            base64_data = await _safe_download_as_data_uri(img_url, img_aeskey)
            if base64_data:
                quote_data['picurl'] = base64_data
                quote_data['images'] = [base64_data]
        elif quote_type == 'file':
            file_info = quote_info.get('file', {}) or {}
            download_url = file_info.get('url') or file_info.get('fileurl')
            item_aeskey = file_info.get('aeskey', '')
            file_data = {
                'filename': file_info.get('filename') or file_info.get('name'),
                'filesize': file_info.get('filesize') or file_info.get('size'),
                'md5sum': file_info.get('md5sum') or file_info.get('md5'),
                'sdkfileid': file_info.get('sdkfileid') or file_info.get('fileid'),
                'download_url': download_url,
                'extra': file_info,
            }
            # Same as private chat: append aeskey to download_url for plugin processing
            if download_url and item_aeskey:
                file_data['download_url'] = download_url + f'?aeskey={item_aeskey}'
            quote_data['file'] = file_data
        elif quote_type == 'voice':
            voice_info = quote_info.get('voice', {}) or {}
            download_url = voice_info.get('url')
            item_aeskey = voice_info.get('aeskey', '')
            voice_data = {
                'url': download_url,
                'md5sum': voice_info.get('md5sum') or voice_info.get('md5'),
                'filesize': voice_info.get('filesize') or voice_info.get('size'),
                'sdkfileid': voice_info.get('sdkfileid') or voice_info.get('fileid'),
            }
            if voice_info.get('content'):
                quote_data['content'] = voice_info.get('content')
            # Same as private chat: append aeskey to url for plugin processing
            if download_url and item_aeskey:
                voice_data['url'] = download_url + f'?aeskey={item_aeskey}'
            quote_data['voice'] = voice_data
        elif quote_type == 'video':
            video_info = quote_info.get('video', {}) or {}
            download_url = video_info.get('url')
            item_aeskey = video_info.get('aeskey', '')
            video_data = {
                'url': download_url,
                'filesize': video_info.get('filesize') or video_info.get('size'),
                'sdkfileid': video_info.get('sdkfileid') or video_info.get('fileid'),
                'md5sum': video_info.get('md5sum') or video_info.get('md5'),
                'filename': video_info.get('filename') or video_info.get('name'),
            }
            # Same as private chat: append aeskey to download_url for plugin processing
            if download_url and item_aeskey:
                video_data['download_url'] = download_url + f'?aeskey={item_aeskey}'
            quote_data['video'] = video_data
        elif quote_type == 'link':
            quote_data['link'] = quote_info.get('link', {})
            link = quote_data['link']
            title = link.get('title', '')
            desc = link.get('description') or link.get('digest', '')
            quote_data['content'] = '\n'.join(filter(None, [title, desc]))
        elif quote_type == 'mixed':
            # Handle mixed type in quote (text + images + files etc.)
            items = quote_info.get('mixed', {}).get('msg_item', [])
            texts = []
            images = []
            files = []
            for item in items:
                item_type = item.get('msgtype')
                if item_type == 'text':
                    texts.append(item.get('text', {}).get('content', ''))
                elif item_type == 'image':
                    img_info = item.get('image', {})
                    img_url = img_info.get('url')
                    img_aeskey = img_info.get('aeskey', '')
                    base64_data = await _safe_download_as_data_uri(img_url, img_aeskey)
                    if base64_data:
                        images.append(base64_data)
                elif item_type == 'file':
                    file_info = item.get('file', {}) or {}
                    download_url = file_info.get('url') or file_info.get('fileurl')
                    item_aeskey = file_info.get('aeskey', '')
                    file_data = {
                        'filename': file_info.get('filename') or file_info.get('name'),
                        'filesize': file_info.get('filesize') or file_info.get('size'),
                        'md5sum': file_info.get('md5sum') or file_info.get('md5'),
                        'sdkfileid': file_info.get('sdkfileid') or file_info.get('fileid'),
                        'download_url': download_url,
                        'extra': file_info,
                    }
                    # Same as private chat: append aeskey to download_url for plugin processing
                    if download_url and item_aeskey:
                        file_data['download_url'] = download_url + f'?aeskey={item_aeskey}'
                    files.append(file_data)
            if texts:
                quote_data['content'] = ' '.join(texts)
            if images:
                quote_data['images'] = images
                quote_data['picurl'] = images[0]
            if files:
                quote_data['files'] = files
                quote_data['file'] = files[0]

        message_data['quote'] = quote_data

    return message_data


def _wecom_button_style(action: dict, *, selected: bool = False) -> int:
    """Map Dify button style to WeCom button style."""

    if not selected:
        return 2

    return 1


def _wecom_field_display_name(field: dict, fallback: str = '') -> str:
    label = (
        field.get('label') or field.get('title') or field.get('name') or field.get('output_variable_name') or fallback
    )
    return str(label or fallback).strip()


def _wecom_input_hint_lines(form_data: dict) -> list[str]:
    lines: list[str] = []
    current_field = str(form_data.get('_current_input_field') or '').strip()
    for field in form_data.get('input_defs') or []:
        field_name = str(field.get('output_variable_name') or '').strip()
        field_type = str(field.get('type') or 'text').strip().lower()
        field_label = _wecom_field_display_name(field, field_name)
        if current_field and field_name != current_field:
            continue
        if not field_name:
            continue
        if field_type in {'file', 'file-list'}:
            limit = field.get('number_limits') if field_type == 'file-list' else 1
            allowed_types = ', '.join(field.get('allowed_file_types') or [])
            suffix = f', up to {limit}' if field_type == 'file-list' and limit else ''
            allowed = f' ({allowed_types})' if allowed_types else ''
            lines.append(f'- {field_label}: upload file(s){allowed}{suffix} or reply `{field_name}: <url>`')
    return lines


def _wecom_pending_input_defs(form_data: dict) -> list[dict]:
    if form_data.get('_action_select_only'):
        return []
    inputs = form_data.get('inputs') or {}
    current_field = str(form_data.get('_current_input_field') or '').strip()
    pending = []
    for field in form_data.get('input_defs') or []:
        field_name = str(field.get('output_variable_name') or '').strip()
        if not field_name:
            continue
        if current_field and field_name != current_field:
            continue
        if str(field.get('type') or '').strip().lower() in {'file', 'file-list'}:
            continue
        if inputs.get(field_name) in (None, '', []):
            pending.append(field)
    return pending


def _wecom_select_options(field: dict) -> list[str]:
    source = field.get('option_source') or {}
    options = source.get('value') if isinstance(source, dict) else []
    if not isinstance(options, list):
        return []
    return [str(option) for option in options]


def _wecom_select_option_id(index: int) -> str:
    return f'opt_{index + 1}'


def _wecom_pending_select_defs(form_data: dict) -> list[dict]:
    return [
        field
        for field in _wecom_pending_input_defs(form_data)
        if str(field.get('type') or '').strip().lower() == 'select' and _wecom_select_options(field)
    ]


def _wecom_field_title(field: dict, fallback: str) -> str:
    title = _wecom_field_display_name(field, fallback)
    return str(title or fallback).strip()[:13] or fallback


def _wecom_form_desc(form_data: dict) -> str:
    form_content = _wecom_clean_form_content(form_data)
    return form_content[:512] if form_content else ''


def build_human_input_text_prompt(form_data: dict) -> Optional[str]:
    """Build a plain-text prompt for a current non-select input field."""

    current_field = str(form_data.get('_current_input_field') or '').strip()
    if not current_field:
        return None
    for field in form_data.get('input_defs') or form_data.get('all_input_defs') or []:
        if str(field.get('output_variable_name') or '').strip() != current_field:
            continue
        field_type = str(field.get('type') or 'text').strip().lower()
        if field_type == 'select':
            return None
        form_content = _wecom_clean_form_content(form_data)
        if not form_content:
            form_content = _wecom_field_display_name(field, current_field)
        node_title = str(form_data.get('node_title') or '人工介入').strip()
        return f'{node_title}\n\n{form_content}' if form_content else node_title
    return None


def build_multiple_interaction_payload(
    form_data: dict,
    task_id: str,
    *,
    source: Optional[dict] = None,
) -> dict[str, Any]:
    """Build a WeCom multiple_interaction card for pending select fields."""

    select_fields = _wecom_pending_select_defs(form_data)
    node_title = (form_data.get('node_title') or '').strip() or 'Human Input'
    inputs = form_data.get('inputs') or {}

    select_list = []
    for field_index, field in enumerate(select_fields[:10]):
        field_name = str(field.get('output_variable_name') or '').strip()
        if not field_name:
            continue
        options = _wecom_select_options(field)[:10]
        option_list = [
            {
                'id': _wecom_select_option_id(idx),
                'text': option_text[:10] or _wecom_select_option_id(idx),
            }
            for idx, option_text in enumerate(options)
        ]
        selected_id = _wecom_select_option_id(0)
        current_value = inputs.get(field_name)
        if current_value not in (None, '', []):
            for idx, option_text in enumerate(options):
                if str(current_value) == option_text:
                    selected_id = _wecom_select_option_id(idx)
                    break
        select_list.append(
            {
                'question_key': field_name,
                'title': _wecom_field_title(field, f'Select {field_index + 1}'),
                'selected_id': selected_id,
                'option_list': option_list,
            }
        )

    card: dict[str, Any] = {
        'card_type': 'multiple_interaction',
        'main_title': {
            'title': node_title,
            'desc': _wecom_form_desc(form_data),
        },
        'select_list': select_list,
        'submit_button': {
            'text': 'Submit',
            'key': 'submit_human_input',
        },
        'task_id': task_id,
    }
    if source:
        card['source'] = source
    return {
        'msgtype': 'template_card',
        'template_card': card,
    }


_SELECT_BUTTON_KEY_PREFIX = '__dify_select__'


def _encode_select_button_key(field_name: str, option_index: int) -> str:
    data = json.dumps({'f': field_name, 'i': option_index}, ensure_ascii=False, separators=(',', ':'))
    encoded = base64.urlsafe_b64encode(data.encode('utf-8')).decode('ascii').rstrip('=')
    return f'{_SELECT_BUTTON_KEY_PREFIX}:{encoded}'


def parse_select_button_action(action_id: str, form_data: dict) -> dict[str, str]:
    """Decode a select option represented as a button_interaction click."""

    action_id = str(action_id or '').strip()
    prefix = f'{_SELECT_BUTTON_KEY_PREFIX}:'
    if not action_id.startswith(prefix):
        return {}
    encoded = action_id[len(prefix) :]
    try:
        padded = encoded + '=' * (-len(encoded) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8'))
    except Exception:
        return {}
    field_name = str(data.get('f') or '').strip()
    option_index = data.get('i')
    if not field_name or not isinstance(option_index, int):
        return {}
    for field in form_data.get('input_defs') or form_data.get('all_input_defs') or []:
        if str(field.get('output_variable_name') or '').strip() != field_name:
            continue
        options = _wecom_select_options(field)
        if 0 <= option_index < len(options):
            return {field_name: options[option_index]}
    return {}


def build_select_button_interaction_payload(
    form_data: dict,
    task_id: str,
    *,
    source: Optional[dict] = None,
) -> dict[str, Any]:
    """Build a button_interaction card that emulates a select field.

    WeCom AI Bot long-connection callbacks are reliable for button clicks, so
    this is used as a fallback when multiple_interaction submit callbacks are
    not delivered by the platform.
    """

    select_fields = _wecom_pending_select_defs(form_data)
    field = select_fields[0] if select_fields else {}
    field_name = str(field.get('output_variable_name') or '').strip()
    options = _wecom_select_options(field)[:10] if field else []
    visible_options = options[:6]
    overflow_options = options[6:]

    node_title = (form_data.get('node_title') or '').strip() or 'Human Input'
    form_content = _wecom_clean_form_content(form_data)

    sub_title_parts: list[str] = []
    if form_content:
        sub_title_parts.append(form_content)
    if overflow_options:
        extra_lines = [f'  - {idx + 7}. {option}' for idx, option in enumerate(overflow_options)]
        sub_title_parts.append(
            'More options can be entered by replying with the option text:\n' + '\n'.join(extra_lines)
        )

    button_list = [
        {
            'text': option_text[:10] or f'Option {idx + 1}',
            'style': 2 if idx == 0 else 0,
            'key': _encode_select_button_key(field_name, idx),
        }
        for idx, option_text in enumerate(visible_options)
    ]

    card: dict[str, Any] = {
        'card_type': 'button_interaction',
        'main_title': {
            'title': node_title,
        },
        'sub_title_text': '\n\n'.join(sub_title_parts),
        'button_list': button_list,
        'task_id': task_id,
    }
    if source:
        card['source'] = source
    return {
        'msgtype': 'template_card',
        'template_card': card,
    }


def build_human_input_template_card_payload(
    form_data: dict,
    task_id: str,
    *,
    source: Optional[dict] = None,
    select_as_buttons: bool = False,
) -> dict[str, Any]:
    """Build the best WeCom template card for a Dify human-input form."""

    if _wecom_pending_select_defs(form_data):
        if select_as_buttons:
            return build_select_button_interaction_payload(form_data, task_id, source=source)
        return build_multiple_interaction_payload(form_data, task_id, source=source)
    return build_button_interaction_payload(form_data, task_id, source=source)


def _wecom_clean_form_content(form_data: dict) -> str:
    is_field_step = bool(form_data.get('_current_input_field')) and not form_data.get('_action_select_only')
    raw_content = str(form_data.get('raw_form_content') or '')
    content = form_data.get('form_content') or raw_content
    input_defs = list(form_data.get('all_input_defs') or form_data.get('input_defs') or [])
    fields = {
        str(field.get('output_variable_name') or '').strip(): field
        for field in input_defs
        if str(field.get('output_variable_name') or '').strip()
    }

    if form_data.get('_action_select_only') and raw_content:
        placeholders = [
            match
            for match in re.finditer(r'\{\{#\$output\.([^#{}]+)#\}\}', raw_content)
            if match.group(1).strip() in fields
        ]
        if placeholders:
            content = raw_content[placeholders[-1].end() :]

    if is_field_step:
        inputs = form_data.get('inputs') or {}

        def replace_placeholder(match: re.Match[str]) -> str:
            field_name = match.group(1).strip()
            field = fields.get(field_name)
            value = inputs.get(field_name)
            if not field or value in (None, '', []):
                return ''
            return f'✅ {field_name}：{_wecom_display_input_value(field, value)}'

        content = re.sub(r'\{\{#\$output\.([^#{}]+)#\}\}', replace_placeholder, str(content))

    kept_lines: list[str] = []
    for line in str(content).splitlines():
        placeholder = re.fullmatch(r'\s*\{\{#\$output\.([^#{}]+)#\}\}\s*', line)
        if placeholder and placeholder.group(1).strip() in fields:
            continue
        kept_lines.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept_lines).strip())


def _wecom_display_input_value(field: dict, value: Any) -> str:
    field_type = str(field.get('type') or 'text').strip().lower()
    if field_type == 'file':
        if isinstance(value, dict):
            return str(value.get('url') or value.get('upload_file_id') or '1 file')
    elif field_type == 'file-list' and isinstance(value, list):
        return f'{len(value)} file(s)'
    return str(value)


def build_button_interaction_payload(
    form_data: dict,
    task_id: str,
    *,
    source: Optional[dict] = None,
) -> dict[str, Any]:
    """Build a `template_card` (button_interaction) WeCom payload.

    Shared by both the webhook-mode client (returns the payload as the
    response to a stream-followup callback) and the ws_client (sends it
    as a reply frame). Output shape is `{"msgtype": "template_card",
    "template_card": {...}}` per the WeCom spec.

    Args:
        form_data: Dify human-input form data with keys ``actions`` (list of
            ``{id, title, button_style}``), ``node_title``, ``form_content``.
        task_id: Unique per-card identifier. WeCom requires this for
            button_interaction. The click callback returns it as TaskId so we
            can find the originating session.
        source: Optional source header dict ``{icon_url, desc, desc_color}``
            shown at the top of the card. WeCom accepts arbitrary HTTPS
            URLs for ``icon_url`` (unlike DingTalk Avatar which requires
            a uploaded media id), so the LangBot logo URL can be passed
            straight through.

    Notes:
        * ``button.key`` is set directly to the Dify ``action_id``. The click
          callback's ``EventKey`` carries this back unchanged (1024-byte limit
          per the spec, far more than we ever need).
        * WeCom caps the button list at 6. Extra actions are appended to
          ``sub_title_text`` so users can still reply with the id as text.
        * Styles map ``primary``→1 (blue), ``danger``→2 (red), default→0
          (gray). First button is auto-promoted to primary when no style.
    """
    actions = list(form_data.get('actions') or [])
    node_title = (form_data.get('node_title') or '').strip() or '人工介入'
    form_content = _wecom_clean_form_content(form_data)
    should_show_actions = not _wecom_pending_input_defs(form_data)

    visible_actions = actions[:6] if should_show_actions else []
    overflow = actions[6:] if should_show_actions else []

    sub_title_parts: list[str] = []
    if form_content:
        sub_title_parts.append(form_content)
    input_hint_lines = _wecom_input_hint_lines(form_data)
    if input_hint_lines:
        sub_title_parts.append('Fill these fields in chat before choosing an action:\n' + '\n'.join(input_hint_lines))
    if overflow:
        extra_lines = [f'  - {a.get("title") or a.get("id") or ""} (回复 id: {a.get("id") or ""})' for a in overflow]
        sub_title_parts.append(f'另有 {len(overflow)} 个选项不在按钮列表中，可直接回复 id：\n' + '\n'.join(extra_lines))
    sub_title_text = '\n\n'.join(sub_title_parts)

    button_list = []
    for idx, action in enumerate(visible_actions):
        action_id = str(action.get('id') or '')
        title = str(action.get('title') or action_id or f'选项 {idx + 1}')
        button_list.append(
            {
                'text': title,
                'style': _wecom_button_style(action),
                'key': action_id,
            }
        )

    card: dict[str, Any] = {
        'card_type': 'button_interaction',
        'main_title': {
            'title': node_title,
        },
        'sub_title_text': sub_title_text,
        'button_list': button_list,
        'task_id': task_id,
    }
    if source:
        card['source'] = source
    return {
        'msgtype': 'template_card',
        'template_card': card,
    }


def extract_template_card_action(tce: dict[str, Any]) -> tuple[str, str, str]:
    """Extract task id, clicked button key, and card type from a WeCom callback."""

    task_id = tce.get('TaskId') or tce.get('task_id') or tce.get('taskid') or tce.get('taskId') or ''
    event_key = (
        tce.get('EventKey')
        or tce.get('event_key')
        or tce.get('eventkey')
        or tce.get('eventKey')
        or tce.get('key')
        or tce.get('Key')
        or ''
    )
    card_type = tce.get('CardType') or tce.get('card_type') or tce.get('cardtype') or tce.get('cardType') or ''

    for button_key in ('button', 'Button', 'selected_button', 'selectedButton'):
        button = tce.get(button_key)
        if isinstance(button, dict):
            if not event_key:
                event_key = (
                    button.get('key')
                    or button.get('Key')
                    or button.get('event_key')
                    or button.get('EventKey')
                    or button.get('id')
                    or button.get('Id')
                    or ''
                )
            break

    return str(task_id or ''), str(event_key or ''), str(card_type or '')


def extract_wecom_event_type(payload: dict[str, Any]) -> str:
    """Extract eventtype from common WeCom callback wrapper shapes."""

    event = payload.get('event') if isinstance(payload, dict) else {}
    if not isinstance(event, dict):
        event = {}
    event_type = (
        event.get('eventtype')
        or event.get('event_type')
        or event.get('eventType')
        or event.get('EventType')
        or payload.get('eventtype')
        or payload.get('event_type')
        or payload.get('eventType')
        or payload.get('EventType')
        or ''
    )
    if event_type:
        return str(event_type)

    tce = extract_template_card_event_payload(payload)
    task_id, event_key, card_type = extract_template_card_action(tce)
    if task_id or event_key or card_type or extract_template_card_selections(tce):
        return 'template_card_event'
    return ''


def extract_template_card_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract template_card_event from common WeCom callback wrapper shapes."""

    if not isinstance(payload, dict):
        return {}
    event = payload.get('event') if isinstance(payload.get('event'), dict) else {}
    candidates = (
        event.get('template_card_event'),
        event.get('templateCardEvent'),
        event.get('TemplateCardEvent'),
        event.get('template_card'),
        payload.get('template_card_event'),
        payload.get('templateCardEvent'),
        payload.get('TemplateCardEvent'),
        payload.get('template_card'),
    )
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    if any(
        key in payload
        for key in (
            'TaskId',
            'task_id',
            'taskId',
            'EventKey',
            'event_key',
            'eventKey',
            'CardType',
            'card_type',
            'cardType',
            'ResponseData',
            'response_data',
            'select_list',
            'SelectList',
        )
    ):
        return payload
    if any(
        key in event
        for key in (
            'TaskId',
            'task_id',
            'taskId',
            'EventKey',
            'event_key',
            'eventKey',
            'CardType',
            'card_type',
            'cardType',
            'ResponseData',
            'response_data',
            'select_list',
            'SelectList',
        )
    ):
        return event
    return {}


def extract_template_card_selections(tce: dict[str, Any], form_data: Optional[dict] = None) -> dict[str, str]:
    """Extract multiple_interaction select values from a WeCom callback.

    WeCom callback examples differ between webhook and websocket docs, so this
    parser accepts common snake_case/camelCase/PascalCase variants and maps the
    selected option id back to the Dify select option text when form_data is
    available.
    """

    fields_by_name: dict[str, dict] = {}
    if form_data:
        for field in form_data.get('input_defs') or form_data.get('all_input_defs') or []:
            field_name = str(field.get('output_variable_name') or '').strip()
            if field_name:
                fields_by_name[field_name] = field

    def _maybe_decode_json(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text or text[0] not in '[{':
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value

    def _walk(value: Any) -> list[dict]:
        value = _maybe_decode_json(value)
        found: list[dict] = []
        if isinstance(value, dict):
            found.append(value)
            for child in value.values():
                found.extend(_walk(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(_walk(child))
        return found

    def _lookup(item: dict, *keys: str) -> Any:
        for key in keys:
            if key in item:
                return item.get(key)
        lower_map = {str(key).lower(): value for key, value in item.items()}
        for key in keys:
            lowered = key.lower()
            if lowered in lower_map:
                return lower_map[lowered]
        return ''

    def _normalise_selected_value(question_key: str, selected: Any) -> str:
        selected = _maybe_decode_json(selected)
        if isinstance(selected, dict):
            selected = _lookup(
                selected,
                'selected_id',
                'SelectedId',
                'selected_option_id',
                'SelectedOptionId',
                'option_id',
                'OptionId',
                'id',
                'Id',
                'value',
                'Value',
            )
        selected_id = str(selected or '').strip()
        if not selected_id:
            return ''
        selected_value = selected_id
        field = fields_by_name.get(question_key)
        if field:
            options = _wecom_select_options(field)
            for idx, option_text in enumerate(options):
                if selected_id in {_wecom_select_option_id(idx), option_text}:
                    selected_value = option_text
                    break
        return selected_value

    selections: dict[str, str] = {}
    for item in _walk(tce):
        question_key = _lookup(
            item,
            'question_key',
            'questionKey',
            'QuestionKey',
            'question',
            'Question',
            'key',
            'Key',
        )
        selected_id = _lookup(
            item,
            'selected_id',
            'selectedId',
            'SelectedId',
            'selected_option_id',
            'selectedOptionId',
            'SelectedOptionId',
            'option_id',
            'optionId',
            'OptionId',
            'value',
            'Value',
        )
        question_key = str(question_key or '').strip()
        selected_id = str(selected_id or '').strip()
        if question_key not in fields_by_name or not selected_id:
            continue

        selected_value = _normalise_selected_value(question_key, selected_id)
        if not selected_value:
            continue
        selections[question_key] = selected_value

    # Some WeCom callbacks encode ResponseData as a direct mapping:
    # {"xiala": "id_two"} rather than a select_list item array.
    for item in _walk(tce):
        if not isinstance(item, dict):
            continue
        for question_key, selected in item.items():
            question_key = str(question_key or '').strip()
            if question_key not in fields_by_name or question_key in selections:
                continue
            selected_value = _normalise_selected_value(question_key, selected)
            if selected_value:
                selections[question_key] = selected_value

    return selections


def resolve_form_action_title(form_data: dict, action_id: str) -> str:
    """Resolve a Dify form action title from its id."""

    clean_action_id = str(action_id or '').strip()
    for action in form_data.get('actions') or []:
        if str(action.get('id', '')) == clean_action_id:
            return str(action.get('title') or clean_action_id)
    return clean_action_id


def build_button_interaction_update_card(
    form_data: dict,
    task_id: str,
    action_id: str,
    source: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build the template_card body used to update a clicked form card."""

    node_title = str(form_data.get('node_title') or '').strip() or '人工介入'
    form_content = _wecom_clean_form_content(form_data)
    action_title = resolve_form_action_title(form_data, action_id)
    clean_action_id = str(action_id or '').strip()

    button_list = []
    matched = False
    for idx, action in enumerate(list(form_data.get('actions') or [])[:6]):
        action_key = str(action.get('id') or '')
        button_title = str(action.get('title') or action_key or f'Option {idx + 1}')
        button = {
            'text': button_title,
            'style': _wecom_button_style(action),
            'key': action_key,
        }
        if action_key == clean_action_id:
            button['style'] = _wecom_button_style(action, selected=True)
            button['text'] = f'✅ {button_title}'
            button['replace_text'] = f'✅ {button_title}'
            matched = True
        button_list.append(button)

    if clean_action_id and not matched:
        button_list.append(
            {
                'text': action_title or clean_action_id,
                'style': 1,
                'key': clean_action_id,
                'replace_text': f'✅ {action_title or clean_action_id}',
            }
        )

    card: dict[str, Any] = {
        'card_type': 'button_interaction',
        'main_title': {
            'title': node_title,
        },
        'sub_title_text': form_content,
        'button_list': button_list,
        'task_id': task_id,
    }
    if source:
        card['source'] = source
    return card


def build_multiple_interaction_update_card(
    form_data: dict,
    task_id: str,
    selections: Optional[dict[str, str]] = None,
    source: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build an update card that freezes submitted select values."""

    node_title = str(form_data.get('node_title') or '').strip() or 'Human Input'
    selected_values = dict(form_data.get('inputs') or {})
    selected_values.update(selections or {})

    select_list = []
    fields = _wecom_pending_select_defs(form_data)
    if not fields:
        fields = [
            field
            for field in (form_data.get('input_defs') or form_data.get('all_input_defs') or [])
            if str(field.get('type') or '').strip().lower() == 'select'
        ]
    for field_index, field in enumerate(fields[:10]):
        field_name = str(field.get('output_variable_name') or '').strip()
        if not field_name:
            continue
        options = _wecom_select_options(field)[:10]
        option_list = [
            {
                'id': _wecom_select_option_id(idx),
                'text': option_text[:10] or _wecom_select_option_id(idx),
            }
            for idx, option_text in enumerate(options)
        ]
        selected_id = _wecom_select_option_id(0)
        current_value = selected_values.get(field_name)
        if current_value not in (None, '', []):
            for idx, option_text in enumerate(options):
                if str(current_value) == option_text or str(current_value) == _wecom_select_option_id(idx):
                    selected_id = _wecom_select_option_id(idx)
                    break
        select_list.append(
            {
                'question_key': field_name,
                'title': _wecom_field_title(field, f'Select {field_index + 1}'),
                'disable': True,
                'selected_id': selected_id,
                'option_list': option_list,
            }
        )

    display_form_data = dict(form_data)
    display_form_data['inputs'] = selected_values
    form_content = _wecom_clean_form_content(display_form_data)

    card: dict[str, Any] = {
        'card_type': 'multiple_interaction',
        'main_title': {
            'title': node_title,
            'desc': form_content,
        },
        'select_list': select_list,
        'submit_button': {
            'text': '✅',
            'key': 'submit_human_input',
        },
        'task_id': task_id,
    }
    if source:
        card['source'] = source
    return card


class WecomBotClient:
    def __init__(
        self,
        Token: str,
        EnCodingAESKey: str,
        Corpid: str,
        logger: EventLogger,
        unified_mode: bool = False,
    ):
        """企业微信智能机器人客户端。

        Args:
            Token: 企业微信回调验证使用的 token。
            EnCodingAESKey: 企业微信消息加解密密钥。
            Corpid: 企业 ID。
            logger: 日志记录器。
            unified_mode: 是否使用统一 webhook 模式（默认 False）。

        Example:
            >>> client = WecomBotClient(Token='token', EnCodingAESKey='aeskey', Corpid='corp', logger=logger)
        """

        self.Token = Token
        self.EnCodingAESKey = EnCodingAESKey
        self.Corpid = Corpid
        self.ReceiveId = ''
        self.unified_mode = unified_mode
        self.app = Quart(__name__)

        # 只有在非统一模式下才注册独立路由
        if not self.unified_mode:
            self.app.add_url_rule(
                '/callback/command', 'handle_callback', self.handle_callback_request, methods=['POST', 'GET']
            )

        self._message_handlers = {
            'example': [],
        }
        self.logger = logger
        self.generated_content: dict[str, str] = {}
        self.msg_id_map: dict[str, int] = {}
        self.stream_sessions = StreamSessionManager(logger=logger)
        self.stream_poll_timeout = 0.5

        self._feedback_callback: Optional[Callable] = None
        self._card_action_callback: Optional[Callable] = None
        self._stream_last_content: dict[str, str] = {}
        # Optional `source` block injected into every interactive template_card
        # the client builds. Set via `set_card_source` from the adapter after
        # reading config. Format: {icon_url, desc, desc_color}.
        self.card_source: Optional[dict] = None

    def set_card_source(self, source: Optional[dict]) -> None:
        """Set the `source` header dict injected into every
        button_interaction template_card. Pass None to clear."""
        self.card_source = source

    def set_feedback_callback(self, callback: Callable) -> None:
        """设置反馈回调函数。

        Args:
            callback: 反馈回调函数，签名: async def callback(feedback_id, feedback_type, feedback_content, inaccurate_reasons, session)
        """
        self._feedback_callback = callback

    def set_card_action_callback(self, callback: Callable) -> None:
        """设置按钮卡片点击回调函数。

        Signature: ``async def callback(session, action_id, task_id, raw_event) -> None``

        ``session`` is the StreamSession the card was attached to;
        ``action_id`` is the Dify action_id reflected back via the
        button's ``key`` field; ``task_id`` is the card's task_id
        (matches ``session.pending_form_task_id``); ``raw_event`` is the
        decoded callback JSON for any extra fields the adapter wants.
        """
        self._card_action_callback = callback

    @staticmethod
    def _build_stream_payload(
        stream_id: str, content: str, finish: bool, feedback_id: Optional[str] = None
    ) -> dict[str, Any]:
        """按照企业微信协议拼装返回报文。

        Args:
            stream_id: 企业微信会话 ID。
            content: 推送的文本内容。
            finish: 是否为最终片段。
            feedback_id: 反馈 ID，用于接收用户点赞/点踩反馈。

        Returns:
            dict[str, Any]: 可直接加密返回的 payload。

        Example:
            组装 `{'msgtype': 'stream', 'stream': {'id': 'sid', ...}}` 结构。
        """
        stream_payload = {
            'id': stream_id,
            'finish': finish,
            'content': content,
        }
        if feedback_id:
            stream_payload['feedback'] = {'id': feedback_id}
        return {
            'msgtype': 'stream',
            'stream': stream_payload,
        }

    def _build_button_interaction_payload(self, form_data: dict, task_id: str) -> dict[str, Any]:
        """Class-level shim — delegates to module-level builder and auto-
        injects the client's configured `source` block so every card emitted
        through this client carries the LangBot header."""
        return build_human_input_template_card_payload(form_data, task_id, source=self.card_source)

    async def _encrypt_and_reply(self, payload: dict[str, Any], nonce: str) -> tuple[Response, int]:
        """对响应进行加密封装并返回给企业微信。

        Args:
            payload: 待加密的响应内容。
            nonce: 企业微信回调参数中的 nonce。

        Returns:
            Tuple[Response, int]: Quart Response 对象及状态码。

        Example:
            在首包或刷新场景中调用以生成加密响应。
        """
        reply_plain_str = json.dumps(payload, ensure_ascii=False)
        reply_timestamp = str(int(time.time()))
        ret, encrypt_text = self.wxcpt.EncryptMsg(reply_plain_str, nonce, reply_timestamp)
        if ret != 0:
            await self.logger.error(f'加密失败: {ret}')
            return jsonify({'error': 'encrypt_failed'}), 500

        root = ET.fromstring(encrypt_text)
        encrypt = root.find('Encrypt').text
        resp = {
            'encrypt': encrypt,
        }
        return jsonify(resp), 200

    async def _dispatch_event(self, event: wecombotevent.WecomBotEvent) -> None:
        """异步触发流水线处理，避免阻塞首包响应。

        Args:
            event: 由企业微信消息转换的内部事件对象。
        """
        try:
            await self._handle_message(event)
        except Exception:
            await self.logger.error(traceback.format_exc())

    async def _handle_post_initial_response(self, msg_json: dict[str, Any], nonce: str) -> tuple[Response, int]:
        """处理企业微信首次推送的消息，返回 stream_id 并开启流水线。

        Args:
            msg_json: 解密后的企业微信消息 JSON。
            nonce: 企业微信回调参数 nonce。

        Returns:
            Tuple[Response, int]: Quart Response 及状态码。

        Example:
            首次回调时调用，立即返回带 `stream_id` 的响应。
        """
        session, is_new = self.stream_sessions.create_or_get(msg_json)

        feedback_id = str(uuid.uuid4())
        session.feedback_id = feedback_id
        self.stream_sessions.register_feedback_id(session.stream_id, feedback_id)

        message_data = await self.get_message(msg_json)
        if message_data:
            message_data['stream_id'] = session.stream_id
            message_data['feedback_id'] = feedback_id
            try:
                event = wecombotevent.WecomBotEvent(message_data)
            except Exception:
                await self.logger.error(traceback.format_exc())
            else:
                if is_new:
                    asyncio.create_task(self._dispatch_event(event))

        payload = self._build_stream_payload(session.stream_id, '', False, feedback_id)
        return await self._encrypt_and_reply(payload, nonce)

    async def _handle_post_followup_response(self, msg_json: dict[str, Any], nonce: str) -> tuple[Response, int]:
        """处理企业微信的流式刷新请求，按需返回增量片段。

        Args:
            msg_json: 解密后的企业微信刷新请求。
            nonce: 企业微信回调参数 nonce。

        Returns:
            Tuple[Response, int]: Quart Response 及状态码。

        Example:
            在刷新请求中调用，按需返回增量片段。
        """
        stream_info = msg_json.get('stream', {})
        stream_id = stream_info.get('id', '')
        if not stream_id:
            await self.logger.error('刷新请求缺少 stream.id')
            return await self._encrypt_and_reply(self._build_stream_payload('', '', True), nonce)

        session = self.stream_sessions.get_session(stream_id)

        # If a Dify human-input pause arrived during this stream, switch
        # the response from `msgtype: stream` to `msgtype: template_card`
        # (button_interaction). The session's stream is also marked
        # finished so future followups aren't expected (assuming the
        # WeCom client treats template_card as the terminal response —
        # we'll know from the next callback whether it kept polling).
        if session and session.pending_form and session.pending_form_task_id:
            await self.logger.info(
                f'WeComBot: returning button_interaction for stream_id={stream_id} '
                f'task_id={session.pending_form_task_id} actions={len(session.pending_form.get("actions") or [])}'
            )
            card_payload = self._build_button_interaction_payload(session.pending_form, session.pending_form_task_id)
            self.stream_sessions.mark_finished(stream_id)
            return await self._encrypt_and_reply(card_payload, nonce)

        chunk = await self.stream_sessions.consume(stream_id, timeout=self.stream_poll_timeout)

        if not chunk:
            cached_content = None
            if session and session.msg_id:
                cached_content = self.generated_content.pop(session.msg_id, None)
            if cached_content is not None:
                chunk = StreamChunk(content=cached_content, is_final=True)
            else:
                payload = self._build_stream_payload(stream_id, '', False)
                return await self._encrypt_and_reply(payload, nonce)

        payload = self._build_stream_payload(stream_id, chunk.content, chunk.is_final)
        if chunk.is_final:
            self.stream_sessions.mark_finished(stream_id)
        return await self._encrypt_and_reply(payload, nonce)

    async def handle_callback_request(self):
        """企业微信回调入口（独立端口模式，使用全局 request）。

        Returns:
            Quart Response: 根据请求类型返回验证、首包或刷新结果。

        Example:
            作为 Quart 路由处理函数直接注册并使用。
        """
        return await self._handle_callback_internal(request)

    async def handle_unified_webhook(self, req):
        """处理回调请求（统一 webhook 模式，显式传递 request）。

        Args:
            req: Quart Request 对象

        Returns:
            响应数据
        """
        return await self._handle_callback_internal(req)

    async def _handle_callback_internal(self, req):
        """处理回调请求的内部实现，包括 GET 验证和 POST 消息接收。

        Args:
            req: Quart Request 对象
        """
        try:
            self.wxcpt = WXBizMsgCrypt(self.Token, self.EnCodingAESKey, '')

            if req.method == 'GET':
                return await self._handle_get_callback(req)

            if req.method == 'POST':
                return await self._handle_post_callback(req)

            return Response('', status=405)

        except Exception:
            await self.logger.error(traceback.format_exc())
            return Response('Internal Server Error', status=500)

    async def _handle_get_callback(self, req) -> tuple[Response, int] | Response:
        """处理企业微信的 GET 验证请求。"""

        msg_signature = unquote(req.args.get('msg_signature', ''))
        timestamp = unquote(req.args.get('timestamp', ''))
        nonce = unquote(req.args.get('nonce', ''))
        echostr = unquote(req.args.get('echostr', ''))

        if not all([msg_signature, timestamp, nonce, echostr]):
            await self.logger.error('请求参数缺失')
            return Response('缺少参数', status=400)

        ret, decrypted_str = self.wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret != 0:
            await self.logger.error('验证URL失败')
            return Response('验证失败', status=403)

        return Response(decrypted_str, mimetype='text/plain')

    async def _handle_post_callback(self, req) -> tuple[Response, int] | Response:
        """处理企业微信的 POST 回调请求。"""

        self.stream_sessions.cleanup()

        msg_signature = unquote(req.args.get('msg_signature', ''))
        timestamp = unquote(req.args.get('timestamp', ''))
        nonce = unquote(req.args.get('nonce', ''))

        encrypted_json = await req.get_json()
        encrypted_msg = (encrypted_json or {}).get('encrypt', '')
        if not encrypted_msg:
            await self.logger.error("请求体中缺少 'encrypt' 字段")
            return Response('Bad Request', status=400)

        xml_post_data = f'<xml><Encrypt><![CDATA[{encrypted_msg}]]></Encrypt></xml>'
        ret, decrypted_xml = self.wxcpt.DecryptMsg(xml_post_data, msg_signature, timestamp, nonce)
        if ret != 0:
            await self.logger.error('解密失败')
            return Response('解密失败', status=400)

        msg_json = json.loads(decrypted_xml)

        event_type = extract_wecom_event_type(msg_json)

        if event_type == 'feedback_event':
            return await self._handle_feedback_event(msg_json, nonce)

        # Button click on a button_interaction template_card. The WeCom doc
        # calls this `template_card_event`; some routes wrap the button
        # event payload inside `event.template_card_event`.
        if event_type == 'template_card_event':
            return await self._handle_template_card_event(msg_json, nonce)

        if msg_json.get('msgtype') == 'stream':
            return await self._handle_post_followup_response(msg_json, nonce)

        return await self._handle_post_initial_response(msg_json, nonce)

    async def _handle_template_card_event(self, msg_json: dict[str, Any], nonce: str) -> tuple[Response, int]:
        """Handle a button click on a button_interaction template_card.

        WeCom carries the click info in ``event.template_card_event`` with
        ``TaskId`` matching the card we created and ``EventKey`` carrying
        the button's ``key`` (which we set to the Dify ``action_id``).
        """
        try:
            tce = extract_template_card_event_payload(msg_json)
            task_id, event_key, card_type = extract_template_card_action(tce)

            await self.logger.info(f'收到按钮点击: task_id={task_id} event_key={event_key!r} card_type={card_type}')

            session = self.stream_sessions.get_session_by_task_id(task_id)
            if session is None:
                await self.logger.warning(f'未找到 task_id={task_id} 对应的 session，按钮点击被丢弃')
            else:
                if self._card_action_callback is not None:
                    try:
                        await self._card_action_callback(session, event_key, task_id, msg_json)
                    except Exception:
                        await self.logger.error(f'card action callback raised: {traceback.format_exc()}')
                # Drop the form so a fresh chunk/followup doesn't re-render
                # the same card (and so the task_id can be GC'd).
                self.stream_sessions.clear_pending_form(session.stream_id)
        except Exception:
            await self.logger.error(f'_handle_template_card_event error: {traceback.format_exc()}')

        # WeCom expects an empty success ack for event callbacks.
        return await self._encrypt_and_reply({}, nonce)

    async def _handle_feedback_event(self, msg_json: dict[str, Any], nonce: str) -> tuple[Response, int]:
        """处理企业微信用户反馈事件（点赞/点踩）。

        Args:
            msg_json: 解密后的企业微信反馈事件 JSON。
            nonce: 企业微信回调参数 nonce。

        Returns:
            Tuple[Response, int]: Quart Response 及状态码。

        Note:
            企业微信协议要求：反馈事件目前仅支持回复空包。
        """
        try:
            feedback_event = msg_json.get('event', {}).get('feedback_event', {})
            feedback_id = feedback_event.get('id', '')
            feedback_type = feedback_event.get('type', 0)
            feedback_content = feedback_event.get('content', '')
            inaccurate_reasons = feedback_event.get('inaccurate_reason_list', [])

            await self.logger.info(
                f'收到用户反馈事件: feedback_id={feedback_id}, type={feedback_type}, '
                f'content={feedback_content}, reasons={inaccurate_reasons}'
            )

            session = self.stream_sessions.get_session_by_feedback_id(feedback_id)

            if session:
                await self.logger.info(
                    f'反馈关联到会话: stream_id={session.stream_id}, msg_id={session.msg_id}, user_id={session.user_id}'
                )
            else:
                await self.logger.warning(f'未找到 feedback_id={feedback_id} 对应的会话，仍将记录反馈')

            # Dispatch feedback event regardless of session availability
            for handler in self._message_handlers.get('feedback', []):
                try:
                    await handler(
                        feedback_id=feedback_id,
                        feedback_type=feedback_type,
                        feedback_content=feedback_content,
                        inaccurate_reasons=inaccurate_reasons,
                        session=session,
                    )
                except Exception:
                    await self.logger.error(traceback.format_exc())

            if self._feedback_callback:
                try:
                    await self._feedback_callback(
                        feedback_id=feedback_id,
                        feedback_type=feedback_type,
                        feedback_content=feedback_content,
                        inaccurate_reasons=inaccurate_reasons,
                        session=session,
                    )
                except Exception:
                    await self.logger.error(traceback.format_exc())

        except Exception:
            await self.logger.error(traceback.format_exc())

        return await self._encrypt_and_reply({}, nonce)

    async def get_message(self, msg_json):
        return await parse_wecom_bot_message(msg_json, self.EnCodingAESKey, self.logger)

    async def _handle_message(self, event: wecombotevent.WecomBotEvent):
        """
        处理消息事件。
        """
        try:
            message_id = event.message_id
            if message_id in self.msg_id_map.keys():
                self.msg_id_map[message_id] += 1
                return
            self.msg_id_map[message_id] = 1
            msg_type = event.type
            if msg_type in self._message_handlers:
                for handler in self._message_handlers[msg_type]:
                    await handler(event)
        except Exception:
            print(traceback.format_exc())

    async def push_stream_chunk(self, msg_id: str, content: str, is_final: bool = False) -> bool:
        """将流水线片段推送到 stream 会话。

        Args:
            msg_id: 原始企业微信消息 ID。
            content: 模型产生的片段内容。
            is_final: 是否为最终片段。

        Returns:
            bool: 当成功写入流式队列时返回 True。

        Example:
            在流水线 `reply_message_chunk` 中调用，将增量推送至企业微信。
        """
        # 根据 msg_id 找到对应 stream 会话，如果不存在说明当前消息非流式
        stream_id = self.stream_sessions.get_stream_id_by_msg(msg_id)
        if not stream_id:
            return False

        previous_content = self._stream_last_content.get(msg_id, '')
        if previous_content and content.startswith(previous_content):
            next_content = content
        elif previous_content and not content:
            next_content = previous_content
        else:
            next_content = previous_content + content if previous_content else content

        if not is_final and next_content == previous_content:
            return True

        # Follow-up responses replace the displayed stream body in WeCom.
        # Publish the complete snapshot so earlier chunks remain visible.
        chunk = StreamChunk(content=next_content, is_final=is_final)
        await self.stream_sessions.publish(stream_id, chunk)
        self._stream_last_content[msg_id] = next_content
        if is_final:
            self._stream_last_content.pop(msg_id, None)
            self.stream_sessions.mark_finished(stream_id)
        return True

    async def push_form_pause(
        self, msg_id: str, form_data: dict, task_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Attach a Dify human-input pause to the active stream session.

        On the next WeCom followup poll, the response switches from
        ``msgtype: stream`` to ``msgtype: template_card`` (button_interaction)
        carrying the buttons. ``task_id`` is auto-generated if not provided
        and is what the button-click callback uses to look the session back up.

        Returns:
            ``(ok, stream_id, task_id)``. ``ok`` is False if the
            adapter's msg_id maps to no stream session (e.g. non-stream mode).
        """
        stream_id = self.stream_sessions.get_stream_id_by_msg(msg_id)
        if not stream_id:
            return False, None, None
        if not task_id:
            # WeCom requires task_id [A-Za-z0-9_-@], <= 128 bytes, unique per bot.
            task_id = f'dify-{uuid.uuid4().hex[:24]}'
        self.stream_sessions.set_pending_form(stream_id, form_data, task_id)
        return True, stream_id, task_id

    async def set_message(self, msg_id: str, content: str):
        """兼容旧逻辑：若无法流式返回则缓存最终结果。

        Args:
            msg_id: 企业微信消息 ID。
            content: 最终回复的文本内容。

        Example:
            在非流式场景下缓存最终结果以备刷新时返回。
        """
        handled = await self.push_stream_chunk(msg_id, content, is_final=True)
        if not handled:
            self.generated_content[msg_id] = content

    def on_message(self, msg_type: str):
        def decorator(func: Callable[[wecombotevent.WecomBotEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    def on_feedback(self):
        def decorator(func: Callable):
            if 'feedback' not in self._message_handlers:
                self._message_handlers['feedback'] = []
            self._message_handlers['feedback'].append(func)
            return func

        return decorator

    async def download_url_to_base64(self, download_url, encoding_aes_key):
        data, _filename = await download_encrypted_file(download_url, encoding_aes_key, self.logger)
        if data:
            return _bytes_to_data_uri(data)
        return None

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)
