import asyncio
import base64
import json
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
import re
from typing import Any, Callable, Optional, Tuple
from urllib.parse import unquote

import httpx
from Crypto.Cipher import AES
from quart import Quart, request, Response, jsonify

from langbot.libs.wecom_ai_bot_api import wecombotevent
from langbot.libs.wecom_ai_bot_api.WXBizMsgCrypt3 import WXBizMsgCrypt
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


class StreamSessionManager:
    """管理 stream 会话的生命周期，并负责队列的生产消费。"""

    def __init__(self, logger: EventLogger, ttl: int = 60) -> None:
        self.logger = logger

        self.ttl = ttl  # 超时时间（秒），超过该时间未被访问的会话会被清理由 cleanup
        self._sessions: dict[str, StreamSession] = {}  # stream_id -> StreamSession 映射
        self._msg_index: dict[str, str] = {}  # msgid -> stream_id 映射，便于流水线根据消息 ID 找到会话
        self._feedback_index: dict[str, str] = {}  # feedback_id -> stream_id 映射

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
        """定期清理过期会话，防止队列与映射无上限累积。"""
        now = time.time()
        expired: list[str] = []
        for stream_id, session in self._sessions.items():
            if now - session.last_access > self.ttl:
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

    return message_data


class WecomBotClient:
    def __init__(self, Token: str, EnCodingAESKey: str, Corpid: str, logger: EventLogger, unified_mode: bool = False):
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

    def set_feedback_callback(self, callback: Callable) -> None:
        """设置反馈回调函数。

        Args:
            callback: 反馈回调函数，签名: async def callback(feedback_id, feedback_type, feedback_content, inaccurate_reasons, session)
        """
        self._feedback_callback = callback

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

        event = msg_json.get('event', {})
        event_type = event.get('eventtype', '')

        if event_type == 'feedback_event':
            return await self._handle_feedback_event(msg_json, nonce)

        if msg_json.get('msgtype') == 'stream':
            return await self._handle_post_followup_response(msg_json, nonce)

        return await self._handle_post_initial_response(msg_json, nonce)

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
                await self.logger.warning(
                    f'未找到 feedback_id={feedback_id} 对应的会话，仍将记录反馈'
                )

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

        chunk = StreamChunk(content=content, is_final=is_final)
        await self.stream_sessions.publish(stream_id, chunk)
        if is_final:
            self.stream_sessions.mark_finished(stream_id)
        return True

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
