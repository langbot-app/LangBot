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
from langbot.libs.wecom_ai_bot_api.api import (
    parse_wecom_bot_message,
    StreamSession,
    build_human_input_template_card_payload,
    build_human_input_text_prompt,
    build_button_interaction_update_card,
    build_multiple_interaction_update_card,
    extract_template_card_action,
    extract_template_card_event_payload,
    extract_template_card_selections,
    extract_wecom_event_type,
    parse_select_button_action,
)
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


def _frame_snippet(frame: dict, limit: int = 1000) -> str:
    return json.dumps(frame, ensure_ascii=False, default=str)[:limit]


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
        # Dedup: skip sending when content hasn't changed
        self._stream_last_content: dict[str, str] = {}  # msg_id -> last content sent
        # Stream session info for feedback tracking
        self._stream_sessions: dict[str, dict] = {}  # msg_id -> session info
        # Feedback tracking: feedback_id -> session info
        self._feedback_sessions: dict[str, dict] = {}  # feedback_id -> {msg_id, user_id, chat_id, stream_id, req_id}
        # msg_id -> feedback_id (for associating feedback with message)
        self._msg_feedback_ids: dict[str, str] = {}  # msg_id -> feedback_id

        # Dify human-input pause state for ws mode. Keys are task_id (echoed
        # back in template_card_event.TaskId so we can rebuild the session
        # context on click).
        # task_id -> {form_data, msg_id, user_id, chat_id, stream_id, req_id}
        self._pending_forms_by_task: dict[str, dict] = {}
        # Reverse: msg_id -> task_id (for cleanup when stream finishes).
        self._task_id_by_msg: dict[str, str] = {}
        # Optional card-action callback registered by the adapter.
        # Signature mirrors the http-mode WecomBotClient:
        #   async def callback(session, action_id, task_id, raw_event) -> None
        self._card_action_callback: Optional[Callable] = None
        # Optional `source` block injected into every interactive
        # template_card the client builds via `push_form_pause`. Set via
        # `set_card_source` from the adapter after reading config.
        self.card_source: Optional[dict] = None

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

    def on_feedback(self) -> Callable:
        """Decorator to register a feedback event handler.

        Same interface as WecomBotClient.on_feedback for compatibility.
        """

        def decorator(func: Callable):
            if 'feedback' not in self._message_handlers:
                self._message_handlers['feedback'] = []
            self._message_handlers['feedback'].append(func)
            return func

        return decorator

    async def reply_stream(
        self,
        req_id: str,
        stream_id: str,
        content: str,
        finish: bool = False,
        feedback_id: str = '',
    ) -> Optional[dict]:
        """Send a streaming reply frame.

        Args:
            req_id: The req_id from the original message frame (must be passed through).
            stream_id: The stream ID for this streaming session.
            content: The content to send (supports Markdown).
            finish: Whether this is the final chunk.
            feedback_id: Optional feedback ID for receiving user feedback (like/dislike).

        Returns:
            The ACK frame dict, or None on failure.
        """
        stream_payload = {
            'id': stream_id,
            'finish': finish,
            'content': content,
        }
        if feedback_id:
            stream_payload['feedback'] = {'id': feedback_id}

        body = {
            'msgtype': 'stream',
            'stream': stream_payload,
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

    async def reply_template_card(self, req_id: str, card_payload: dict[str, Any]) -> Optional[dict]:
        """Send a template_card (button_interaction etc.) reply.

        Args:
            req_id: The req_id from the original message frame.
            card_payload: Body produced by ``build_button_interaction_payload``;
                must contain ``msgtype`` and ``template_card`` keys.

        Returns:
            ACK frame dict, or None on failure.
        """
        return await self._send_reply(req_id, card_payload)

    async def update_template_card(
        self,
        req_id: str,
        template_card: dict[str, Any],
    ) -> Optional[dict]:
        """Update an existing template_card via WebSocket.

        Uses the ``aibot_respond_update_msg`` command.  Must be called
        within 5 seconds of receiving the ``template_card_event`` callback,
        using the **same req_id** from that callback.

        The ``template_card`` dict should contain ``card_type`` and the
        new content fields (e.g. ``main_title``, ``button_list`` with
        disabled buttons and ``replace_text``).

        Returns:
            ACK frame dict, or None on failure.
        """
        body: dict[str, Any] = {
            'response_type': 'update_template_card',
            'template_card': template_card,
        }
        return await self._send_reply(req_id, body, cmd=CMD_RESPOND_UPDATE)

    def set_card_action_callback(self, callback: Callable) -> None:
        """Register the button-click handler.

        ``async def callback(session, action_id, task_id, raw_event) -> None``
        — same signature as the http-mode WecomBotClient version so the
        adapter can hand both off to the same coroutine.
        """
        self._card_action_callback = callback

    def set_card_source(self, source: Optional[dict]) -> None:
        """Set the `source` block injected into every interactive
        template_card pushed via `push_form_pause`. Pass None to clear."""
        self.card_source = source

    async def push_form_pause(
        self, msg_id: str, form_data: dict, task_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """Attach a Dify human-input pause to the active stream and send
        the button_interaction card immediately.

        ws mode has no notion of polled "followup" responses — each reply
        is a one-shot frame send. So unlike the http path (which defers
        card delivery to the next followup), here we just craft the card
        and reply with it on the original req_id. The corresponding stream
        session is then torn down so subsequent chunks don't re-send.

        Returns:
            ``(ok, stream_id, task_id)``. ``ok=False`` if no active stream
            for this msg_id (e.g. message arrived in non-stream mode).
        """
        key = self._stream_ids.get(msg_id)
        if not key:
            return False, None, None
        req_id, stream_id = key.split('|', 1)

        if not task_id:
            task_id = f'dify-{secrets.token_hex(12)}'

        session_info = self._stream_sessions.get(msg_id) or {}
        text_prompt = build_human_input_text_prompt(form_data)
        if text_prompt:
            try:
                ack = await self.reply_text(req_id, text_prompt)
                if ack is None:
                    return False, stream_id, None
            except Exception:
                await self.logger.error(f'Failed to send human-input text prompt: {traceback.format_exc()}')
                return False, stream_id, None

            self._stream_ids.pop(msg_id, None)
            self._stream_last_content.pop(msg_id, None)
            self._stream_sessions.pop(msg_id, None)
            return True, stream_id, None

        self._pending_forms_by_task[task_id] = {
            'form_data': form_data,
            'msg_id': msg_id,
            'user_id': session_info.get('user_id', ''),
            'chat_id': session_info.get('chat_id', ''),
            'stream_id': stream_id,
            'req_id': req_id,
        }
        self._task_id_by_msg[msg_id] = task_id

        card_payload = build_human_input_template_card_payload(
            form_data,
            task_id,
            source=self.card_source,
            select_as_buttons=True,
        )
        try:
            await self.reply_template_card(req_id, card_payload)
        except Exception:
            await self.logger.error(f'Failed to send button_interaction card: {traceback.format_exc()}')
            # Roll back the bookkeeping so the next attempt isn't blocked.
            self._pending_forms_by_task.pop(task_id, None)
            self._task_id_by_msg.pop(msg_id, None)
            return False, stream_id, None

        # Tear down the stream — WeCom expects either stream chunks OR a
        # template_card, not both on the same req_id. Subsequent
        # push_stream_chunk calls for this msg_id become no-ops.
        self._stream_ids.pop(msg_id, None)
        self._stream_last_content.pop(msg_id, None)
        # Keep _stream_sessions so the button callback can still resolve
        # user/chat context; it gets cleaned up when the click fires.

        return True, stream_id, task_id

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

    async def send_template_card(self, chat_id: str, card_payload: dict[str, Any]) -> Optional[dict]:
        """Proactively push a template_card to a chat.

        Used for the resumed-workflow path (button click → new query):
        synthetic events have no inbound req_id to reply against, so we
        fall back to proactive ``aibot_send_msg`` instead of reply mode.

        Args:
            chat_id: userid (single chat) or chatid (group chat).
            card_payload: ``{"msgtype": "template_card", "template_card": {...}}``
                as produced by :func:`build_button_interaction_payload`.
        """
        req_id = _generate_req_id(CMD_SEND_MSG)
        body = dict(card_payload)
        body['chatid'] = chat_id
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
            previous_content = self._stream_last_content.get(msg_id, '')
            if previous_content and content.startswith(previous_content):
                next_content = content
            elif previous_content and not content:
                next_content = previous_content
            else:
                next_content = previous_content + content if previous_content else content

            # Skip sending if content hasn't changed (e.g. during tool call argument streaming)
            if not is_final and next_content == previous_content:
                return True

            # Skip empty/whitespace-only snapshots — the runner injects a
            # zero-width space ('​') as a pass-through when workflow_paused
            # fires without any preceding LLM output.  WeCom renders that
            # as an empty bubble that sits before the form card; skip it.
            # NOTE: Python str.strip() does NOT strip ​, so we use
            # a regex that treats any character with Unicode category Zs
            # (separator space) or Cf (format char like ZWS) as blank.
            if not is_final:
                import re as _re

                if not _re.sub(r'[\s​‌‍﻿]', '', next_content):
                    return True

            # Generate feedback_id for final chunk
            feedback_id = ''
            if is_final:
                feedback_id = _generate_req_id('feedback')
                self._msg_feedback_ids[msg_id] = feedback_id
                # Store session info for feedback tracking
                session_info = self._stream_sessions.get(msg_id)
                if session_info:
                    self._feedback_sessions[feedback_id] = session_info

            # WeCom replaces the displayed stream content on each refresh, so
            # every frame must contain the complete snapshot, not only a delta.
            await self.reply_stream(req_id, stream_id, next_content, finish=is_final, feedback_id=feedback_id)
            self._stream_last_content[msg_id] = next_content
            if is_final:
                self._stream_ids.pop(msg_id, None)
                self._stream_last_content.pop(msg_id, None)
                self._stream_sessions.pop(msg_id, None)
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
        await self.logger.warning(f'Unknown frame: {_frame_snippet(frame)}')

    async def _handle_message_callback(self, frame: dict):
        """Handle an incoming message callback frame."""
        try:
            body = frame.get('body', {})
            req_id = frame.get('headers', {}).get('req_id', '')

            event_type = extract_wecom_event_type(body)
            if event_type == 'template_card_event':
                await self._handle_template_card_event_frame(frame, body)
                return
            if event_type:
                await self.logger.debug(f'Received msg_callback event_type={event_type}: {_frame_snippet(frame)}')

            # Parse message using shared logic
            message_data = await parse_wecom_bot_message(body, self.encoding_aes_key, self.logger)
            if not message_data:
                return

            # Generate stream_id for this message and store the mapping
            stream_id = _generate_req_id('stream')
            msg_id = message_data.get('msgid', '')
            if msg_id:
                self._stream_ids[msg_id] = f'{req_id}|{stream_id}'
                # Store session info for feedback tracking
                self._stream_sessions[msg_id] = {
                    'req_id': req_id,
                    'stream_id': stream_id,
                    'msg_id': msg_id,
                    'user_id': message_data.get('userid', ''),
                    'chat_id': message_data.get('chatid', ''),
                    'chat_type': message_data.get('type', 'single'),
                }
            message_data['stream_id'] = stream_id
            message_data['req_id'] = req_id

            event = wecombotevent.WecomBotEvent(message_data)
            await self._dispatch_event(event)
        except Exception:
            await self.logger.error(f'Error in message callback: {traceback.format_exc()}')

    async def _handle_event_callback(self, frame: dict):
        """Handle an incoming event callback frame (enter_chat, template_card_event, feedback_event, disconnected_event)."""
        try:
            body = frame.get('body', {})
            req_id = frame.get('headers', {}).get('req_id', '')

            event_info = body.get('event', {}) if isinstance(body.get('event'), dict) else body
            event_type = extract_wecom_event_type(body)
            if not event_type:
                await self.logger.warning(f'Received event_callback without event_type: {_frame_snippet(frame)}')
            else:
                await self.logger.debug(f'Received event_callback event_type={event_type}')

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

            if event_type == 'feedback_event':
                feedback_event = event_info.get('feedback_event', {})
                feedback_id = feedback_event.get('id', '')
                feedback_type = feedback_event.get('type', 0)
                feedback_content = feedback_event.get('content', '')
                inaccurate_reasons = feedback_event.get('inaccurate_reason_list', [])

                await self.logger.info(
                    f'收到用户反馈事件: feedback_id={feedback_id}, type={feedback_type}, '
                    f'content={feedback_content}, reasons={inaccurate_reasons}'
                )

                # Look up session by feedback_id
                session_info = self._feedback_sessions.get(feedback_id)
                session = None
                if session_info:
                    session = StreamSession(
                        stream_id=session_info.get('stream_id', ''),
                        msg_id=session_info.get('msg_id', ''),
                        chat_id=session_info.get('chat_id') or None,
                        user_id=session_info.get('user_id') or None,
                        feedback_id=feedback_id,
                    )
                    await self.logger.info(
                        f'反馈关联到会话: stream_id={session.stream_id}, msg_id={session.msg_id}, user_id={session.user_id}'
                    )
                else:
                    await self.logger.warning(f'未找到 feedback_id={feedback_id} 对应的会话')

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
                        await self.logger.error(f'Error in feedback handler: {traceback.format_exc()}')
                return

            if event_type == 'template_card_event':
                await self._handle_template_card_event_frame(frame, body)
                return

            event = wecombotevent.WecomBotEvent(message_data)

            if event_type in self._message_handlers:
                for handler in self._message_handlers[event_type]:
                    await handler(event)

            if 'event' in self._message_handlers:
                for handler in self._message_handlers['event']:
                    await handler(event)

        except Exception:
            await self.logger.error(f'Error in event callback: {traceback.format_exc()}')

    async def _handle_template_card_event_frame(self, frame: dict, body: dict):
        """Handle template_card_event frames from event_callback or msg_callback."""
        tce = extract_template_card_event_payload(body)
        task_id, event_key, card_type = extract_template_card_action(tce)
        await self.logger.info(
            f'Received template_card_event (ws): task_id={task_id} event_key={event_key!r} card_type={card_type}'
        )

        pending = self._pending_forms_by_task.get(task_id)
        if pending is None:
            await self.logger.warning(f'No pending_form found for task_id={task_id} (ws); card event ignored')
            return

        req_id_for_update = frame.get('headers', {}).get('req_id', '')
        form_data = pending.get('form_data', {}) or {}
        selections = extract_template_card_selections(tce, form_data)
        if not selections:
            selections = parse_select_button_action(event_key, form_data)
        if card_type == 'multiple_interaction' and not selections:
            await self.logger.warning(
                f'multiple_interaction callback has no parseable selections (ws): raw={str(tce)[:1000]}'
            )
            self._drop_pending_form_task(task_id, pending)
            return

        update_card = build_button_interaction_update_card(
            form_data,
            task_id,
            event_key,
            source=self.card_source,
        )
        if card_type == 'multiple_interaction' or selections:
            update_card = build_multiple_interaction_update_card(
                form_data,
                task_id,
                selections,
                source=self.card_source,
            )
        try:
            await self.update_template_card(req_id_for_update, update_card)
        except Exception:
            await self.logger.warning(f'Failed to update template card (ws): {traceback.format_exc()}')

        if self._card_action_callback is not None:
            try:
                session = StreamSession(
                    stream_id=pending.get('stream_id', ''),
                    msg_id=pending.get('msg_id', ''),
                    chat_id=pending.get('chat_id') or None,
                    user_id=pending.get('user_id') or None,
                )
                session.pending_form = pending.get('form_data')
                session.pending_form_task_id = task_id
                await self._card_action_callback(session, event_key, task_id, body)
            except Exception:
                await self.logger.error(f'card action callback raised (ws): {traceback.format_exc()}')

        self._drop_pending_form_task(task_id, pending)

    def _drop_pending_form_task(self, task_id: str, pending: dict) -> None:
        self._pending_forms_by_task.pop(task_id, None)
        msg_id = pending.get('msg_id', '')
        if msg_id:
            self._task_id_by_msg.pop(msg_id, None)
            self._stream_sessions.pop(msg_id, None)

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
