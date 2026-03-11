"""WeChat Work AI Bot WebSocket long connection client.

Implements the WebSocket protocol for receiving messages and sending replies
via a persistent connection to wss://openws.work.weixin.qq.com, as an
alternative to the HTTP callback (webhook) mode.

Protocol reference: https://developer.work.weixin.qq.com/document/path/101463
Official Node.js SDK: https://github.com/WecomTeam/aibot-node-sdk
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
import traceback
from typing import Any, Callable, Optional

import aiohttp

from langbot.libs.wecom_ai_bot_api import wecombotevent
from langbot.libs.wecom_ai_bot_api.api import parse_wecom_bot_message
from langbot.pkg.platform.logger import EventLogger

DEFAULT_WS_URL = 'wss://openws.work.weixin.qq.com'

# WebSocket frame command constants
CMD_SUBSCRIBE = 'aibot_subscribe'
CMD_HEARTBEAT = 'ping'
CMD_MSG_CALLBACK = 'aibot_msg_callback'
CMD_EVENT_CALLBACK = 'aibot_event_callback'
CMD_RESPOND_MSG = 'aibot_respond_msg'
CMD_RESPOND_WELCOME = 'aibot_respond_welcome_msg'
CMD_RESPOND_UPDATE = 'aibot_respond_update_msg'
CMD_SEND_MSG = 'aibot_send_msg'


def _generate_req_id(prefix: str) -> str:
    """Generate a unique request ID in the format: {prefix}_{timestamp}_{random}."""
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(4)
    return f'{prefix}_{ts}_{rand}'


class WecomBotWsClient:
    """WeChat Work AI Bot WebSocket long connection client.

    Provides message receiving, streaming reply, proactive message sending,
    and event callback handling over a persistent WebSocket connection.
    """

    def __init__(
        self,
        bot_id: str,
        secret: str,
        logger: EventLogger,
        encoding_aes_key: str = '',
        ws_url: str = DEFAULT_WS_URL,
        heartbeat_interval: float = 30.0,
        max_reconnect_attempts: int = -1,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
    ):
        self.bot_id = bot_id
        self.secret = secret
        self.logger = logger
        self.encoding_aes_key = encoding_aes_key
        self.ws_url = ws_url
        self.heartbeat_interval = heartbeat_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_base_delay = reconnect_base_delay
        self.reconnect_max_delay = reconnect_max_delay

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._missed_pong_count = 0
        self._max_missed_pong = 2
        self._reconnect_attempts = 0

        # Message handler registry (same pattern as WecomBotClient)
        self._message_handlers: dict[str, list[Callable]] = {}
        # Message deduplication
        self._msg_id_map: dict[str, int] = {}

        # Pending ACK futures: req_id -> Future[dict]
        self._pending_acks: dict[str, asyncio.Future] = {}
        # Per-req_id serial reply queues
        self._reply_queues: dict[str, asyncio.Queue] = {}
        self._reply_workers: dict[str, asyncio.Task] = {}
        self._reply_ack_timeout = 5.0

        # Stream ID tracking for WebSocket mode
        self._stream_ids: dict[str, str] = {}  # msg_id -> req_id|stream_id

    # ── Public API ──────────────────────────────────────────────────

    async def connect(self):
        """Connect to WebSocket server with automatic reconnection.

        This method blocks until disconnect() is called or max reconnect
        attempts are exhausted.
        """
        self._running = True
        self._reconnect_attempts = 0

        while self._running:
            try:
                await self._connect_once()
            except Exception:
                if not self._running:
                    break
                await self.logger.error(f'WebSocket connection error: {traceback.format_exc()}')

            if not self._running:
                break

            # Reconnect with exponential backoff
            if self.max_reconnect_attempts != -1 and self._reconnect_attempts >= self.max_reconnect_attempts:
                await self.logger.error(f'Max reconnect attempts reached ({self.max_reconnect_attempts}), giving up')
                break

            self._reconnect_attempts += 1
            delay = min(
                self.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
                self.reconnect_max_delay,
            )
            await self.logger.info(f'Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})...')
            await asyncio.sleep(delay)

    async def disconnect(self):
        """Gracefully disconnect from the WebSocket server."""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        for task in self._reply_workers.values():
            if not task.done():
                task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    def on_message(self, msg_type: str) -> Callable:
        """Decorator to register a message handler.

        Same interface as WecomBotClient.on_message for compatibility.

        Args:
            msg_type: 'single', 'group', or specific message type.
        """

        def decorator(func: Callable[[wecombotevent.WecomBotEvent], Any]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def reply_stream(
        self,
        req_id: str,
        stream_id: str,
        content: str,
        finish: bool = False,
    ) -> Optional[dict]:
        """Send a streaming reply frame.

        Args:
            req_id: The req_id from the original message frame (must be passed through).
            stream_id: The stream ID for this streaming session.
            content: The content to send (supports Markdown).
            finish: Whether this is the final chunk.

        Returns:
            The ACK frame dict, or None on failure.
        """
        body = {
            'msgtype': 'stream',
            'stream': {
                'id': stream_id,
                'finish': finish,
                'content': content,
            },
        }
        return await self._send_reply(req_id, body)

    async def reply_text(self, req_id: str, content: str) -> Optional[dict]:
        """Send a non-streaming text reply.

        Args:
            req_id: The req_id from the original message frame.
            content: The text content to reply.

        Returns:
            The ACK frame dict, or None on failure.
        """
        body = {
            'msgtype': 'markdown',
            'markdown': {
                'content': content,
            },
        }
        return await self._send_reply(req_id, body)

    async def send_message(self, chat_id: str, content: str, msgtype: str = 'markdown') -> Optional[dict]:
        """Proactively send a message to a specified chat.

        Args:
            chat_id: The chat ID (userid for single chat, chatid for group chat).
            content: The message content.
            msgtype: Message type, 'markdown' by default.

        Returns:
            The ACK frame dict, or None on failure.
        """
        req_id = _generate_req_id(CMD_SEND_MSG)
        body: dict[str, Any] = {
            'chatid': chat_id,
            'msgtype': msgtype,
        }
        if msgtype == 'markdown':
            body['markdown'] = {'content': content}
        elif msgtype == 'text':
            body['text'] = {'content': content}
        return await self._send_reply(req_id, body, cmd=CMD_SEND_MSG)

    async def push_stream_chunk(self, msg_id: str, content: str, is_final: bool = False) -> bool:
        """Push a streaming chunk for a given message ID.

        Compatible interface with WecomBotClient.push_stream_chunk.

        Args:
            msg_id: The original message ID.
            content: The cumulative content from the pipeline.
            is_final: Whether this is the final chunk.

        Returns:
            True if the stream session exists and chunk was sent.
        """
        key = self._stream_ids.get(msg_id)
        if not key:
            return False
        req_id, stream_id = key.split('|', 1)
        try:
            await self.reply_stream(req_id, stream_id, content, finish=is_final)
            if is_final:
                self._stream_ids.pop(msg_id, None)
            return True
        except Exception:
            await self.logger.error(f'Failed to push stream chunk: {traceback.format_exc()}')
            return False

    async def set_message(self, msg_id: str, content: str):
        """Fallback: send content as a final stream chunk or direct reply.

        Compatible interface with WecomBotClient.set_message.
        """
        handled = await self.push_stream_chunk(msg_id, content, is_final=True)
        if not handled:
            await self.logger.warning(f'No active stream for msg_id={msg_id}, message dropped')

    # ── Connection lifecycle ────────────────────────────────────────

    async def _connect_once(self):
        """Establish a single WebSocket connection, authenticate, and listen."""
        await self.logger.info(f'Connecting to {self.ws_url}...')

        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(self.ws_url)
            self._missed_pong_count = 0
            self._reconnect_attempts = 0
            await self.logger.info('WebSocket connected, sending auth...')

            await self._send_auth()

            # Wait for auth response
            auth_ok = await self._wait_for_auth()
            if not auth_ok:
                await self.logger.error('Authentication failed')
                return

            await self.logger.info('Authenticated successfully')

            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            try:
                await self._listen_loop()
            finally:
                if self._heartbeat_task and not self._heartbeat_task.done():
                    self._heartbeat_task.cancel()
                self._clear_pending_acks('Connection closed')
        finally:
            if self._ws and not self._ws.closed:
                await self._ws.close()
            self._ws = None
            if self._session and not self._session.closed:
                await self._session.close()
            self._session = None

    async def _send_auth(self):
        """Send the authentication frame."""
        frame = {
            'cmd': CMD_SUBSCRIBE,
            'headers': {'req_id': _generate_req_id(CMD_SUBSCRIBE)},
            'body': {
                'bot_id': self.bot_id,
                'secret': self.secret,
            },
        }
        await self._send_frame(frame)

    async def _wait_for_auth(self) -> bool:
        """Wait for and validate the authentication response."""
        try:
            msg = await asyncio.wait_for(self._ws.receive(), timeout=10.0)
            if msg.type in (aiohttp.WSMsgType.TEXT,):
                frame = json.loads(msg.data)
                req_id = frame.get('headers', {}).get('req_id', '')
                if req_id.startswith(CMD_SUBSCRIBE) and frame.get('errcode') == 0:
                    return True
                await self.logger.error(f'Auth response: errcode={frame.get("errcode")}, errmsg={frame.get("errmsg")}')
                return False
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                await self.logger.error(f'WebSocket closed during auth: {msg.type}')
                return False
            await self.logger.error(f'Unexpected message type during auth: {msg.type}')
            return False
        except asyncio.TimeoutError:
            await self.logger.error('Auth response timeout')
            return False

    async def _heartbeat_loop(self):
        """Periodically send heartbeat pings."""
        try:
            while self._running and self._ws and not self._ws.closed:
                await asyncio.sleep(self.heartbeat_interval)
                if not self._running or not self._ws or self._ws.closed:
                    break

                if self._missed_pong_count >= self._max_missed_pong:
                    await self.logger.warning(
                        f'No heartbeat ack for {self._missed_pong_count} consecutive pings, connection considered dead'
                    )
                    await self._ws.close()
                    break

                self._missed_pong_count += 1
                frame = {
                    'cmd': CMD_HEARTBEAT,
                    'headers': {'req_id': _generate_req_id(CMD_HEARTBEAT)},
                }
                try:
                    await self._send_frame(frame)
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def _listen_loop(self):
        """Listen for incoming WebSocket frames and dispatch them."""
        async for msg in self._ws:
            if not self._running:
                break
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    frame = json.loads(msg.data)
                    await self._handle_frame(frame)
                except json.JSONDecodeError:
                    await self.logger.error(f'Failed to parse WebSocket message: {str(msg.data)[:200]}')
                except Exception:
                    await self.logger.error(f'Error handling frame: {traceback.format_exc()}')
            elif msg.type == aiohttp.WSMsgType.BINARY:
                try:
                    frame = json.loads(msg.data)
                    await self._handle_frame(frame)
                except Exception:
                    await self.logger.error(f'Error handling binary frame: {traceback.format_exc()}')
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                await self.logger.warning(f'WebSocket connection closed: {msg.type}')
                break

    # ── Frame handling ──────────────────────────────────────────────

    async def _handle_frame(self, frame: dict):
        """Route an incoming frame to the appropriate handler."""
        cmd = frame.get('cmd', '')

        # Message push
        if cmd == CMD_MSG_CALLBACK:
            asyncio.create_task(self._handle_message_callback(frame))
            return

        # Event push
        if cmd == CMD_EVENT_CALLBACK:
            asyncio.create_task(self._handle_event_callback(frame))
            return

        # No cmd → response/ACK frame, dispatch by req_id prefix
        req_id = frame.get('headers', {}).get('req_id', '')

        # Check pending ACKs first
        if req_id in self._pending_acks:
            future = self._pending_acks.pop(req_id)
            if not future.done():
                future.set_result(frame)
            return

        # Heartbeat response
        if req_id.startswith(CMD_HEARTBEAT):
            if frame.get('errcode') == 0:
                self._missed_pong_count = 0
            return

        # Unknown frame
        await self.logger.warning(f'Unknown frame: {json.dumps(frame, ensure_ascii=False)[:200]}')

    async def _handle_message_callback(self, frame: dict):
        """Handle an incoming message callback frame."""
        try:
            body = frame.get('body', {})
            req_id = frame.get('headers', {}).get('req_id', '')

            # Parse message using shared logic
            message_data = await parse_wecom_bot_message(body, self.encoding_aes_key, self.logger)
            if not message_data:
                return

            # Generate stream_id for this message and store the mapping
            stream_id = _generate_req_id('stream')
            msg_id = message_data.get('msgid', '')
            if msg_id:
                self._stream_ids[msg_id] = f'{req_id}|{stream_id}'
            message_data['stream_id'] = stream_id
            message_data['req_id'] = req_id

            event = wecombotevent.WecomBotEvent(message_data)
            await self._dispatch_event(event)
        except Exception:
            await self.logger.error(f'Error in message callback: {traceback.format_exc()}')

    async def _handle_event_callback(self, frame: dict):
        """Handle an incoming event callback frame (enter_chat, template_card_event, etc.)."""
        try:
            body = frame.get('body', {})
            req_id = frame.get('headers', {}).get('req_id', '')

            event_info = body.get('event', {})
            event_type = event_info.get('eventtype', '')

            message_data = {
                'msgtype': 'event',
                'type': body.get('chattype', 'single'),
                'event': event_info,
                'eventtype': event_type,
                'msgid': body.get('msgid', ''),
                'aibotid': body.get('aibotid', ''),
                'req_id': req_id,
            }

            from_info = body.get('from', {})
            message_data['userid'] = from_info.get('userid', '')
            message_data['username'] = from_info.get('alias', '') or from_info.get('userid', '')

            if body.get('chatid'):
                message_data['chatid'] = body.get('chatid', '')

            event = wecombotevent.WecomBotEvent(message_data)

            # Dispatch to event-specific handlers
            if event_type in self._message_handlers:
                for handler in self._message_handlers[event_type]:
                    await handler(event)

            # Also dispatch to generic 'event' handlers
            if 'event' in self._message_handlers:
                for handler in self._message_handlers['event']:
                    await handler(event)

        except Exception:
            await self.logger.error(f'Error in event callback: {traceback.format_exc()}')

    async def _dispatch_event(self, event: wecombotevent.WecomBotEvent):
        """Dispatch a message event to registered handlers with deduplication."""
        try:
            message_id = event.message_id
            if message_id in self._msg_id_map:
                self._msg_id_map[message_id] += 1
                return
            self._msg_id_map[message_id] = 1

            msg_type = event.type
            if msg_type in self._message_handlers:
                for handler in self._message_handlers[msg_type]:
                    await handler(event)
        except Exception:
            await self.logger.error(f'Error dispatching event: {traceback.format_exc()}')

    # ── Reply sending with serial queue ─────────────────────────────

    async def _send_reply(
        self,
        req_id: str,
        body: dict,
        cmd: str = CMD_RESPOND_MSG,
    ) -> Optional[dict]:
        """Send a reply frame and wait for ACK.

        Replies with the same req_id are serialized to maintain ordering.
        """
        if not self._ws or self._ws.closed:
            return None

        frame = {
            'cmd': cmd,
            'headers': {'req_id': req_id},
            'body': body,
        }

        # Ensure serial delivery per req_id
        if req_id not in self._reply_queues:
            self._reply_queues[req_id] = asyncio.Queue()
            self._reply_workers[req_id] = asyncio.create_task(self._reply_queue_worker(req_id))

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._reply_queues[req_id].put((frame, future))
        return await future

    async def _reply_queue_worker(self, req_id: str):
        """Process reply queue items serially for a given req_id."""
        queue = self._reply_queues[req_id]
        try:
            while self._running:
                try:
                    frame, future = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # Queue idle, clean up worker
                    break

                try:
                    ack = await self._send_and_wait_ack(frame)
                    if not future.done():
                        future.set_result(ack)
                except Exception as e:
                    if not future.done():
                        future.set_exception(e)
        except asyncio.CancelledError:
            pass
        finally:
            self._reply_queues.pop(req_id, None)
            self._reply_workers.pop(req_id, None)

    async def _send_and_wait_ack(self, frame: dict) -> Optional[dict]:
        """Send a frame and wait for the corresponding ACK."""
        req_id = frame['headers']['req_id']
        ack_future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_acks[req_id] = ack_future

        try:
            await self._send_frame(frame)
            result = await asyncio.wait_for(ack_future, timeout=self._reply_ack_timeout)
            if result.get('errcode', 0) != 0:
                await self.logger.warning(
                    f'Reply ACK error: errcode={result.get("errcode")}, errmsg={result.get("errmsg")}'
                )
            return result
        except asyncio.TimeoutError:
            self._pending_acks.pop(req_id, None)
            await self.logger.warning(f'Reply ACK timeout ({self._reply_ack_timeout}s) for req_id={req_id}')
            return None

    async def _send_frame(self, frame: dict):
        """Send a JSON frame over the WebSocket connection."""
        if self._ws and not self._ws.closed:
            await self._ws.send_str(json.dumps(frame, ensure_ascii=False))

    def _clear_pending_acks(self, reason: str):
        """Reject all pending ACK futures on disconnection."""
        for req_id, future in self._pending_acks.items():
            if not future.done():
                future.set_exception(ConnectionError(reason))
        self._pending_acks.clear()
