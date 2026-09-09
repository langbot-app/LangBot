"""ESPL V3 adapter — WebSocket server for E-SP-Line2's Adapter Gateway (接入器).

LangBot acts as a server-mode WebSocket endpoint. E-SP-Line2's adapter (接入器)
in **client mode** connects to this endpoint (or a reverse proxy forwards it)
and exchanges e-commerce messages:

* **Inbound**  — E-SP-Line2 broadcasts ``message.received`` envelopes to every
  connected adapter client. This adapter converts each envelope into a LangBot
  ``FriendMessage`` / ``GroupMessage`` event (the ``conversation_id`` maps to
  the LangBot launcher/session id) and fires it into the normal pipeline.
* **Outbound** — every ``reply_message`` / ``reply_message_chunk`` the pipeline
  emits is converted into an ESPL v3 outbound ``message`` frame
  (``command_type: send_text``) and sent back over the WebSocket that carries
  the matching conversation.

Design notes:

* Listens on ``ws://<host>:<port>/ws`` (default ``ws://127.0.0.1:8000/ws``).
  In E-SP-Line2 create a **client-mode** 接入器 with ``ws_url`` pointing here.
* Supports multiple simultaneous E-SP-Line2 connections. Each connection is
  identified by its ``adapter_id`` (from the ``key``/path) so outbound replies
  route back to the correct connection.
* Heartbeats: responds to ``ping`` frames with ``pong``; the E-SP-Line2
  gateway also sends server pings that we answer automatically via the
  websockets library.
* The ``conversation_id`` from the inbound envelope is used as the LangBot
  launcher id so each e-commerce conversation maps 1:1 to an isolated LangBot
  session. Replies are routed back to the same ``conversation_id``.
* ``instance_id`` is captured from the inbound envelope and stashed on the
  event's ``source_platform_object``.

See docs/user-guide/adapter-gateway.md in the E-SP-Line2 repo for the full
ESPL v3 protocol reference.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import typing
import uuid
from datetime import datetime

import pydantic
import websockets

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger

logger = logging.getLogger(__name__)

# Default listen host / port (E-SP-Line2 client-mode 接入器 connects here).
_DEFAULT_HOST = '127.0.0.1'
_DEFAULT_PORT = 8000
# Default heartbeat ping interval (seconds).
_DEFAULT_HEARTBEAT_INTERVAL = 30
# Max inbound frame size (1MB, matches E-SP-Line2 gateway).
_MAX_MESSAGE_SIZE = 1 * 1024 * 1024


class _EsplConnection:
    """A single connected E-SP-Line2 adapter gateway client.

    Holds the WebSocket plus the routing info needed to reply.
    """

    def __init__(self, ws, adapter_id: str = ''):
        self.ws = ws
        self.adapter_id = adapter_id
        self.send_lock = asyncio.Lock()

    async def send_frame(self, frame: dict) -> None:
        async with self.send_lock:
            await self.ws.send(json.dumps(frame, ensure_ascii=False))


class EsplAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """ESPL V3 WebSocket server adapter (LangBot is the server)."""

    bot_uuid: str = pydantic.Field(default='', exclude=True)

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict, exclude=True)

    # WebSocket server state (excluded from pydantic serialization).
    server: typing.Any = pydantic.Field(default=None, exclude=True)
    running: bool = pydantic.Field(default=False, exclude=True)
    connections: dict[str, '_EsplConnection'] = pydantic.Field(default_factory=dict, exclude=True)
    inbound_tasks: set[asyncio.Task] = pydantic.Field(default_factory=set, exclude=True)
    heartbeat_task: asyncio.Task | None = pydantic.Field(default=None, exclude=True)

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(config=config, logger=logger, **kwargs)
        self.bot_account_id = 'espl'
        self.listeners = {}
        self.server = None
        self.running = False
        self.connections = {}
        self.inbound_tasks = set()
        self.heartbeat_task = None

    # -- framework hooks ------------------------------------------------------

    def set_bot_uuid(self, bot_uuid: str) -> None:
        """Called by the bot manager so the adapter knows its own bot uuid."""
        object.__setattr__(self, 'bot_uuid', bot_uuid)

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str:
        """Map an inbound event to a LangBot launcher id.

        We use the e-commerce ``conversation_id`` (stashed on the sender id at
        inbound time) so each conversation maps 1:1 to an isolated LangBot
        session.
        """
        if isinstance(event, platform_events.GroupMessage):
            return str(event.sender.group.id)
        return str(event.sender.id)

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        self.listeners[event_type] = func

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        func: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        self.listeners.pop(event_type, None)

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def is_stream_output_supported(self) -> bool:
        return False

    # -- server lifecycle -----------------------------------------------------

    async def run_async(self):
        """Start the WebSocket server and serve forever."""
        host = str(self.config.get('host', _DEFAULT_HOST))
        port = int(self.config.get('port', _DEFAULT_PORT))
        self.running = True

        self.server = await websockets.serve(
            self._handle_connection,
            host,
            port,
            ping_interval=None,  # we manage heartbeats ourselves
            max_size=_MAX_MESSAGE_SIZE,
        )
        await self.logger.info(f'ESPL adapter listening on ws://{host}:{port}/ws')

        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        try:
            # Serve forever; run_async is expected to stay alive.
            while self.running:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        finally:
            if self.server is not None:
                self.server.close()
                await self.server.wait_closed()
                self.server = None

    async def kill(self) -> bool:
        """Stop the server and close all connections."""
        self.running = False
        if self.heartbeat_task is not None and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            self.heartbeat_task = None
        for task in list(self.inbound_tasks):
            if not task.done():
                task.cancel()
        self.inbound_tasks.clear()
        for conn in list(self.connections.values()):
            try:
                await conn.ws.close()
            except Exception:
                pass
        self.connections.clear()
        return True

    # -- connection handler ---------------------------------------------------

    async def _handle_connection(self, ws):
        """Handle a new WebSocket connection from an E-SP-Line2 gateway client.

        The E-SP-Line2 client-mode adapter connects with ``?key=<KEY>`` in the
        query string.  If the adapter has been configured with a non-empty
        ``key``, this method **rejects** connections that do not present a
        matching key (close code 1008 — policy violation).

        Note: websockets >= 14 removed the ``path`` / ``query_string``
        attributes from the connection object.  The request path (including
        the query string) is available via ``ws.request.path``.
        """
        # In websockets >= 14 the request path (with query string) lives on
        # ``ws.request.path`` (e.g. ``/ws?key=abc``).  Fall back to the legacy
        # ``ws.path`` / ``ws.query_string`` attributes for older versions.
        request = getattr(ws, 'request', None)
        if request is not None:
            raw_path = str(getattr(request, 'path', '') or '')
        else:
            raw_path = str(getattr(ws, 'path', '') or '')
        path, _, query = raw_path.partition('?')

        # ── Key authentication ──────────────────────────────────────────
        expected_key = str(self.config.get('key') or '')
        provided_key = self._extract_key(query)
        if expected_key:
            if not provided_key:
                await self.logger.warning(
                    f'ESPL adapter key missing; closing connection from {raw_path}'
                )
                await ws.close(1008, 'Unauthorized: key missing')
                return
            if provided_key != expected_key:
                await self.logger.warning(
                    f'ESPL adapter key mismatch; closing connection from {raw_path}'
                )
                await ws.close(1008, 'Unauthorized: invalid key')
                return

        # ── Identify the connection for routing ─────────────────────────
        adapter_id = self._extract_adapter_id(path, query)

        conn = _EsplConnection(ws, adapter_id=adapter_id)
        conn_key = adapter_id or ('conn_' + uuid.uuid4().hex)
        self.connections[conn_key] = conn

        await self.logger.info(
            f'ESPL adapter client connected: adapter_id={adapter_id or "(client-mode, no adapter-id in path)"} '
            f'path={raw_path}'
        )

        # ── Send the connected handshake ────────────────────────────────
        try:
            await conn.send_frame(
                {
                    'type': 'connected',
                    'id': uuid.uuid4().hex,
                    'timestamp': int(time.time() * 1000),
                    'adapter_id': adapter_id or '',
                    'gateway_version': 'v3',
                    'session_id': conn_key,
                    'adapter_name': self.config.get('name', 'ESPL'),
                    'platform': self.config.get('platform', ''),
                }
            )
        except Exception as e:
            await self.logger.warning(f'ESPL adapter handshake failed: {e}')
            self.connections.pop(conn_key, None)
            return

        # ── Read loop ───────────────────────────────────────────────────
        try:
            async for raw in ws:
                try:
                    frame = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    await self.logger.warning(f'ESPL adapter received non-JSON frame: {raw[:200]}')
                    continue
                await self._handle_frame(conn, frame)
        except websockets.exceptions.ConnectionClosed as e:
            await self.logger.info(f'ESPL adapter client disconnected: {e.code} {e.reason}')
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await self.logger.warning(f'ESPL adapter connection error: {e}')
        finally:
            self.connections.pop(conn_key, None)

    @staticmethod
    def _extract_adapter_id(path: str, query: str) -> str:
        """Extract the adapter id from the connection path.

        E-SP-Line2 client mode may connect to /ws/adapter-gateway/<id>?key=...
        or a custom path /custom?key=... The adapter id is extracted from the
        path segment, NOT from the key query parameter.
        """
        path_part = path.split('?', 1)[0]
        if '/ws/adapter-gateway/' in path_part:
            maybe_id = path_part.rsplit('/', 1)[-1]
            if maybe_id and maybe_id not in ('ws', 'adapter-gateway'):
                return maybe_id
        # No adapter id in the path; return empty string (anonymous connection).
        return ''

    @staticmethod
    def _extract_key(query: str) -> str:
        """Extract the ``key`` query parameter from the WebSocket query string.

        E-SP-Line2 client-mode adapter passes the access key as
        ``?key=<KEY>`` in the WebSocket URL (see ``client_connector.go``
        line 172-177).
        """
        for pair in query.split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                if k == 'key':
                    return v
        return ''

    async def _handle_frame(self, conn: _EsplConnection, frame: dict) -> None:
        """Handle a single inbound frame from an E-SP-Line2 gateway client."""
        msg_type = frame.get('type', '')
        if msg_type == 'ping':
            await conn.send_frame({'type': 'pong', 'timestamp': int(time.time() * 1000)})
            return
        if msg_type == 'pong':
            return
        if msg_type == 'ack':
            return
        if msg_type == 'error':
            await self.logger.warning(f'ESPL adapter gateway error: {frame.get("code")} {frame.get("message")}')
            return

        # Inbound message envelope (message.received).
        if frame.get('event_type') == 'message.received':
            await self._handle_inbound_message(conn, frame)
            return

        await self.logger.debug(f'ESPL adapter unhandled frame type: {msg_type}')

    def _start_inbound_task(self, coro) -> asyncio.Task | None:
        self.inbound_tasks = {task for task in self.inbound_tasks if not task.done()}
        task = asyncio.create_task(coro)
        self.inbound_tasks.add(task)

        def task_done(done_task: asyncio.Task) -> None:
            self.inbound_tasks.discard(done_task)
            if not done_task.cancelled():
                done_task.exception()

        task.add_done_callback(task_done)
        return task

    async def _handle_inbound_message(self, conn: _EsplConnection, envelope: dict) -> None:
        """Convert a message.received envelope into a LangBot event and fire it."""
        payload = envelope.get('payload') or {}
        if not isinstance(payload, dict):
            await self.logger.warning('ESPL adapter inbound payload is not an object')
            return

        conversation_id = str(payload.get('conversation_id') or '')
        sender_id = str(payload.get('sender_id') or '')
        sender_name = str(payload.get('sender_name') or 'User')
        message_content = str(payload.get('message_content') or '')
        instance_id = str(payload.get('instance') or payload.get('instance_id') or '')
        platform = str(payload.get('platform_id') or envelope.get('platform') or '')

        if not conversation_id:
            await self.logger.warning('ESPL adapter inbound message missing conversation_id')
            return

        chain = self._build_message_chain(payload.get('message_chain'), message_content)

        # Stash routing context (instance_id, conversation_id, conn_key) on the
        # event so outbound replies route back to the correct connection.
        source_platform_object = {
            'instance_id': instance_id,
            'conversation_id': conversation_id,
            'platform': platform,
            'sender_id': sender_id,
            '_conn': conn,
        }

        session_type = str(payload.get('session_type') or 'person')
        if session_type == 'group':
            group = platform_entities.Group(
                id=conversation_id,
                name=str(payload.get('group_name') or conversation_id),
                permission=platform_entities.Permission.Member,
            )
            sender = platform_entities.GroupMember(
                id=sender_id or conversation_id,
                member_name=sender_name,
                group=group,
                permission=platform_entities.Permission.Member,
            )
            event = platform_events.GroupMessage(
                sender=sender,
                message_chain=chain,
                time=datetime.now().timestamp(),
                source_platform_object=source_platform_object,
            )
        else:
            sender = platform_entities.Friend(
                id=conversation_id,
                nickname=sender_name,
                remark=sender_name,
            )
            event = platform_events.FriendMessage(
                sender=sender,
                message_chain=chain,
                time=datetime.now().timestamp(),
                source_platform_object=source_platform_object,
            )

        listener = self.listeners.get(type(event))
        if listener is None:
            await self.logger.warning(f'ESPL adapter no listener for {type(event).__name__}')
            return

        await self.logger.info(
            f'ESPL adapter inbound: conversation={conversation_id} sender={sender_name} '
            f'content={message_content[:100]}'
        )
        self._start_inbound_task(listener(event, self))

    def _build_message_chain(
        self,
        message_chain: typing.Any,
        fallback_text: str,
    ) -> platform_message.MessageChain:
        """Convert an ESPL message_chain into a LangBot MessageChain."""
        components: list[platform_message.MessageComponent] = []
        if isinstance(message_chain, list):
            for elem in message_chain:
                if not isinstance(elem, dict):
                    continue
                elem_type = elem.get('type', '')
                content = elem.get('content')
                if elem_type == 'text':
                    text = ''
                    if isinstance(content, dict):
                        text = str(content.get('text', ''))
                    elif isinstance(content, str):
                        text = content
                    else:
                        text = str(elem.get('text', ''))
                    if text:
                        components.append(platform_message.Plain(text=text))
                elif elem_type == 'image':
                    url = ''
                    if isinstance(content, dict):
                        url = str(content.get('url', ''))
                    elif isinstance(content, str):
                        url = content
                    else:
                        url = str(elem.get('url', ''))
                    if url:
                        components.append(platform_message.Image(url=url))
                elif elem_type in ('item', 'product', 'goods'):
                    # E-commerce product card (e.g. 闲鱼 itemInfo).
                    # Render as a plain-text description so the product info
                    # (title/price) is not dropped downstream.
                    title = ''
                    price = ''
                    if isinstance(content, dict):
                        title = str(content.get('title') or '')
                        price = str(content.get('price') or '')
                    elif isinstance(content, str):
                        title = content
                    else:
                        title = str(elem.get('title') or '')
                        price = str(elem.get('price') or '')
                    product_text = title
                    if price:
                        product_text = f'{title} [价格: {price}]' if title else f'价格: {price}'
                    if product_text:
                        components.append(platform_message.Plain(text=product_text))
        if not components and fallback_text:
            components.append(platform_message.Plain(text=fallback_text))
        return platform_message.MessageChain(components)

    # -- outbound -------------------------------------------------------------

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain) -> dict:
        """Proactively push a message to a conversation (target_id == conversation_id)."""
        return await self._emit_outbound(target_id, message)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        return await self._emit_outbound_from_event(message_source, message)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        # ESPL v3 has no streaming; send the whole chunk as a final message.
        return await self._emit_outbound_from_event(message_source, message)

    async def _emit_outbound_from_event(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
    ) -> dict:
        """Send a reply, routing back to the connection captured at inbound."""
        source = getattr(message_source, 'source_platform_object', None) or {}
        conn = source.get('_conn')
        conversation_id = str(source.get('conversation_id') or '')
        instance_id = str(source.get('instance_id') or '')
        sender_id = str(source.get('sender_id') or '')
        if not conversation_id:
            conversation_id = str(self.get_launcher_id(message_source))
        return await self._emit_outbound(
            conversation_id,
            message,
            instance_id=instance_id,
            sender_id=sender_id,
            conn=conn,
        )

    async def _emit_outbound(
        self,
        conversation_id: str,
        message: platform_message.MessageChain,
        instance_id: str = '',
        sender_id: str = '',
        conn: _EsplConnection | None = None,
    ) -> dict:
        """Build and send an ESPL v3 outbound message frame."""
        if conn is None:
            # Try to find a connection for this conversation by scanning.
            if not self.connections:
                await self.logger.warning('ESPL adapter no connections; dropping outbound message')
                return {}
            conn = next(iter(self.connections.values()))

        # Convert the LangBot message chain to ESPL chain elements.
        chain = []
        for component in message:
            if isinstance(component, platform_message.Plain):
                chain.append({'type': 'text', 'content': {'text': component.text}})
            elif isinstance(component, platform_message.Image):
                chain.append({'type': 'image', 'content': {'url': component.url or ''}})

        frame = {
            'type': 'message',
            'id': 'out_' + uuid.uuid4().hex,
            'timestamp': int(time.time() * 1000),
            'payload': {
                'instance_id': instance_id,
                'command_type': 'send_text',
                'conversation_id': conversation_id,
                'target_id': sender_id or conversation_id,
                'sender_id': sender_id,
                'message_chain': chain,
            },
        }
        try:
            await conn.send_frame(frame)
        except Exception as e:
            await self.logger.error(f'ESPL adapter failed to send outbound: {e}')
            return {}
        await self.logger.info(f'ESPL adapter outbound: conversation={conversation_id} chain={chain}')
        return frame

    # -- heartbeat ------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all connected clients to keep connections alive."""
        interval = int(self.config.get('heartbeat_interval', _DEFAULT_HEARTBEAT_INTERVAL))
        while self.running:
            await asyncio.sleep(interval)
            for conn in list(self.connections.values()):
                try:
                    await conn.send_frame({'type': 'ping', 'timestamp': int(time.time() * 1000)})
                except Exception as e:
                    await self.logger.warning(f'ESPL adapter heartbeat to client failed: {e}')
