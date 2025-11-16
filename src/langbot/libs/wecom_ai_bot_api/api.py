import asyncio
import base64
import json
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
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


class StreamSessionManager:
    """管理 stream 会话的生命周期，并负责队列的生产消费。"""

    def __init__(self, logger: EventLogger, ttl: int = 60) -> None:
        self.logger = logger

        self.ttl = ttl  # 超时时间（秒），超过该时间未被访问的会话会被清理由 cleanup
        self._sessions: dict[str, StreamSession] = {}  # stream_id -> StreamSession 映射
        self._msg_index: dict[str, str] = {}  # msgid -> stream_id 映射，便于流水线根据消息 ID 找到会话

    def get_stream_id_by_msg(self, msg_id: str) -> Optional[str]:
        if not msg_id:
            return None
        return self._msg_index.get(msg_id)

    def get_session(self, stream_id: str) -> Optional[StreamSession]:
        return self._sessions.get(stream_id)

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


class WecomBotClient:
    def __init__(self, Token: str, EnCodingAESKey: str, Corpid: str, logger: EventLogger):
        """企业微信智能机器人客户端。

        Args:
            Token: 企业微信回调验证使用的 token。
            EnCodingAESKey: 企业微信消息加解密密钥。
            Corpid: 企业 ID。
            logger: 日志记录器。

        Example:
            >>> client = WecomBotClient(Token='token', EnCodingAESKey='aeskey', Corpid='corp', logger=logger)
        """

        self.Token = Token
        self.EnCodingAESKey = EnCodingAESKey
        self.Corpid = Corpid
        self.ReceiveId = ''
        self.app = Quart(__name__)
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

    @staticmethod
    def _build_stream_payload(stream_id: str, content: str, finish: bool) -> dict[str, Any]:
        """按照企业微信协议拼装返回报文。

        Args:
            stream_id: 企业微信会话 ID。
            content: 推送的文本内容。
            finish: 是否为最终片段。

        Returns:
            dict[str, Any]: 可直接加密返回的 payload。

        Example:
            组装 `{'msgtype': 'stream', 'stream': {'id': 'sid', ...}}` 结构。
        """
        return {
            'msgtype': 'stream',
            'stream': {
                'id': stream_id,
                'finish': finish,
                'content': content,
            },
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

        message_data = await self.get_message(msg_json)
        if message_data:
            message_data['stream_id'] = session.stream_id
            try:
                event = wecombotevent.WecomBotEvent(message_data)
            except Exception:
                await self.logger.error(traceback.format_exc())
            else:
                if is_new:
                    asyncio.create_task(self._dispatch_event(event))

        payload = self._build_stream_payload(session.stream_id, '', False)
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
        """企业微信回调入口。

        Returns:
            Quart Response: 根据请求类型返回验证、首包或刷新结果。

        Example:
            作为 Quart 路由处理函数直接注册并使用。
        """
        try:
            self.wxcpt = WXBizMsgCrypt(self.Token, self.EnCodingAESKey, '')
            await self.logger.info(f'{request.method} {request.url} {str(request.args)}')

            if request.method == 'GET':
                return await self._handle_get_callback()

            if request.method == 'POST':
                return await self._handle_post_callback()

            return Response('', status=405)

        except Exception:
            await self.logger.error(traceback.format_exc())
            return Response('Internal Server Error', status=500)

    async def _handle_get_callback(self) -> tuple[Response, int] | Response:
        """处理企业微信的 GET 验证请求。"""

        msg_signature = unquote(request.args.get('msg_signature', ''))
        timestamp = unquote(request.args.get('timestamp', ''))
        nonce = unquote(request.args.get('nonce', ''))
        echostr = unquote(request.args.get('echostr', ''))

        if not all([msg_signature, timestamp, nonce, echostr]):
            await self.logger.error('请求参数缺失')
            return Response('缺少参数', status=400)

        ret, decrypted_str = self.wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        if ret != 0:
            await self.logger.error('验证URL失败')
            return Response('验证失败', status=403)

        return Response(decrypted_str, mimetype='text/plain')

    async def _handle_post_callback(self) -> tuple[Response, int] | Response:
        """处理企业微信的 POST 回调请求。"""

        self.stream_sessions.cleanup()

        msg_signature = unquote(request.args.get('msg_signature', ''))
        timestamp = unquote(request.args.get('timestamp', ''))
        nonce = unquote(request.args.get('nonce', ''))

        encrypted_json = await request.get_json()
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

        if msg_json.get('msgtype') == 'stream':
            return await self._handle_post_followup_response(msg_json, nonce)

        return await self._handle_post_initial_response(msg_json, nonce)

    async def get_message(self, msg_json):
        message_data = {}

        if msg_json.get('chattype', '') == 'single':
            message_data['type'] = 'single'
        elif msg_json.get('chattype', '') == 'group':
            message_data['type'] = 'group'

        if msg_json.get('msgtype') == 'text':
            message_data['content'] = msg_json.get('text', {}).get('content')
        elif msg_json.get('msgtype') == 'image':
            picurl = msg_json.get('image', {}).get('url', '')
            base64 = await self.download_url_to_base64(picurl, self.EnCodingAESKey)
            message_data['picurl'] = base64
        elif msg_json.get('msgtype') == 'mixed':
            items = msg_json.get('mixed', {}).get('msg_item', [])
            texts = []
            picurl = None
            for item in items:
                if item.get('msgtype') == 'text':
                    texts.append(item.get('text', {}).get('content', ''))
                elif item.get('msgtype') == 'image' and picurl is None:
                    picurl = item.get('image', {}).get('url')

            if texts:
                message_data['content'] = ''.join(texts)  # 拼接所有 text
            if picurl:
                base64 = await self.download_url_to_base64(picurl, self.EnCodingAESKey)
                message_data['picurl'] = base64  # 只保留第一个 image

        # Extract user information
        from_info = msg_json.get('from', {})
        message_data['userid'] = from_info.get('userid', '')
        message_data['username'] = (
            from_info.get('alias', '') or from_info.get('name', '') or from_info.get('userid', '')
        )

        # Extract chat/group information
        if msg_json.get('chattype', '') == 'group':
            message_data['chatid'] = msg_json.get('chatid', '')
            # Try to get group name if available
            message_data['chatname'] = msg_json.get('chatname', '') or msg_json.get('chatid', '')

        message_data['msgid'] = msg_json.get('msgid', '')

        if msg_json.get('aibotid'):
            message_data['aibotid'] = msg_json.get('aibotid', '')

        return message_data

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

    async def download_url_to_base64(self, download_url, encoding_aes_key):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)
            if response.status_code != 200:
                await self.logger.error(f'failed to get file: {response.text}')
                return None

            encrypted_bytes = response.content

        aes_key = base64.b64decode(encoding_aes_key + '=')  # base64 补齐
        iv = aes_key[:16]

        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted_bytes)

        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]

        if decrypted.startswith(b'\xff\xd8'):  # JPEG
            mime_type = 'image/jpeg'
        elif decrypted.startswith(b'\x89PNG'):  # PNG
            mime_type = 'image/png'
        elif decrypted.startswith((b'GIF87a', b'GIF89a')):  # GIF
            mime_type = 'image/gif'
        elif decrypted.startswith(b'BM'):  # BMP
            mime_type = 'image/bmp'
        elif decrypted.startswith(b'II*\x00') or decrypted.startswith(b'MM\x00*'):  # TIFF
            mime_type = 'image/tiff'
        else:
            mime_type = 'application/octet-stream'

        # 转 base64
        base64_str = base64.b64encode(decrypted).decode('utf-8')
        return f'data:{mime_type};base64,{base64_str}'

    async def run_task(self, host: str, port: int, *args, **kwargs):
        """
        启动 Quart 应用。
        """
        await self.app.run_task(host=host, port=port, *args, **kwargs)
