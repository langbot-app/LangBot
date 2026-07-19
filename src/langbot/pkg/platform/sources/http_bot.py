"""HTTP Bot adapter — standalone server-to-server platform adapter.

Lets any external backend drive a LangBot pipeline over plain HTTP:

* **Inbound**  — the backend POSTs a signed message to the unified webhook
  route ``POST /bots/<bot_uuid>``; this adapter verifies the signature, builds
  a platform event carrying the caller-defined ``session_id`` as the launcher
  id, and fires it into the normal pipeline (so message aggregation, N->1,
  works for free).
* **Outbound** — every ``reply_message`` / ``reply_message_chunk`` the pipeline
  emits is delivered as a signed POST to the configured ``callback_url``. A
  single turn may emit many replies (1->M); each is one callback, ordered per
  session via a small worker queue.

Design notes:

* The callback URL is taken **only** from adapter config (never from the
  inbound message) to keep the SSRF surface closed.
* Replies for one ``session_id`` are delivered in ``sequence`` order; the
  caller knows a turn is complete when ``is_final: true`` arrives.
* No new HTTP route is registered — the existing unified webhook dispatcher
  (``pkg/api/http/controller/groups/webhooks.py``) calls
  ``handle_unified_webhook`` on this adapter.

See docs/platforms/http-bot.md for the full integration guide.
"""

from __future__ import annotations

import asyncio
import json
import time
import typing
import uuid
from datetime import datetime

import aiohttp
import pydantic
import quart

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger

from . import http_bot_signing as signing
from ...utils import httpclient


# Error envelope codes (HTTP status -> body code), documented in the design doc.
_ERR = {
    'bad_request': (400, 40001),
    'bad_signature': (401, 40101),
    'duplicate': (409, 40901),
    'too_large': (413, 41301),
    'internal': (500, 50001),
}

# Max accepted inbound body size (bytes).
_MAX_BODY = 1 * 1024 * 1024

# Idempotency dedup window (seconds) and cap.
_IDEMPOTENCY_TTL = 600
_IDEMPOTENCY_MAX = 4096


class _SessionOutbound:
    """Per-session outbound state: ordered delivery queue + sequence counter."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self.worker: asyncio.Task | None = None
        self.sequence: int = 0
        self.last_was_final: bool = True  # so the first reply of a turn starts at seq 1


class _SyncCollector:
    """Collects reply parts for a /sync request and resolves when the turn ends."""

    def __init__(self) -> None:
        self.parts: list = []
        self.done: asyncio.Event = asyncio.Event()


class HttpBotAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Standalone HTTP adapter (inbound webhook + outbound callbacks)."""

    bot_uuid: str = pydantic.Field(default='', exclude=True)

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict, exclude=True)

    # session_id -> outbound state
    outbound_states: dict[str, _SessionOutbound] = pydantic.Field(default_factory=dict, exclude=True)
    # idempotency key -> accepted-at epoch
    idempotency_cache: dict[str, float] = pydantic.Field(default_factory=dict, exclude=True)
    # session_id -> sync collector (set while a /sync request is awaiting a turn)
    sync_waiters: dict[str, '_SyncCollector'] = pydantic.Field(default_factory=dict, exclude=True)

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        super().__init__(config=config, logger=logger, **kwargs)
        self.bot_account_id = 'http_bot'
        self.outbound_states = {}
        self.idempotency_cache = {}
        self.sync_waiters = {}

    # -- framework hooks ------------------------------------------------------

    def set_bot_uuid(self, bot_uuid: str) -> None:
        """Called by the bot manager so the adapter knows its own bot uuid."""
        object.__setattr__(self, 'bot_uuid', bot_uuid)

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str:
        """Map an inbound event to a LangBot launcher id.

        We return the caller-defined ``session_id`` (stashed on the sender /
        group id at inbound time) so that each external session maps 1:1 to an
        isolated LangBot session.
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
        return True

    async def run_async(self):
        # Purely webhook-driven; nothing to poll. Stay alive.
        while True:
            await asyncio.sleep(3600)

    async def kill(self):
        # Cancel any outbound workers.
        for state in self.outbound_states.values():
            if state.worker and not state.worker.done():
                state.worker.cancel()
        return True

    # -- inbound --------------------------------------------------------------

    def _err(self, kind: str, detail: str = ''):
        status, code = _ERR[kind]
        return quart.jsonify({'code': code, 'msg': detail or kind, 'data': None}), status

    def _prune_idempotency(self) -> None:
        now = time.time()
        if len(self.idempotency_cache) > _IDEMPOTENCY_MAX:
            self.idempotency_cache.clear()
            return
        expired = [k for k, ts in self.idempotency_cache.items() if now - ts > _IDEMPOTENCY_TTL]
        for k in expired:
            self.idempotency_cache.pop(k, None)

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        """Handle an inbound POST from the unified webhook dispatcher.

        Sub-path routing:
            (no path)  -> push a message
            "reset"    -> reset a session's conversation (body: {session_id, session_type?})
            "sync"     -> push a message and wait for the final reply (collapses 1->M)
        """
        object.__setattr__(self, 'bot_uuid', bot_uuid)

        if path == 'reset':
            return await self._handle_reset(request)
        if path == 'sync':
            return await self._handle_inbound(request, sync=True)
        if path in ('', None):
            return await self._handle_inbound(request, sync=False)
        return self._err('bad_request', f'unknown sub-path: {path}')

    async def _read_and_verify(self, request) -> tuple[dict | None, typing.Any]:
        """Read body, enforce size + signature. Returns (data, error_response)."""
        body = await request.get_data()
        if body and len(body) > _MAX_BODY:
            return None, self._err('too_large', 'message too large')

        if self.config.get('signature_required', True):
            ok, reason = signing.verify(
                secret=self.config.get('inbound_secret', ''),
                body=body,
                timestamp=request.headers.get(signing.HEADER_TIMESTAMP),
                signature=request.headers.get(signing.HEADER_SIGNATURE),
            )
            if not ok:
                await self.logger.warning(f'http_bot inbound signature rejected: {reason}')
                return None, self._err('bad_signature', f'invalid signature: {reason}')

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return None, self._err('bad_request', 'body is not valid JSON')
        if not isinstance(data, dict):
            return None, self._err('bad_request', 'body must be a JSON object')
        return data, None

    def _build_event(self, data: dict) -> tuple[platform_events.MessageEvent, str, str, str]:
        """Build a platform event from inbound data.

        Returns (event, session_id, session_type, message_id).
        """
        session_id = str(data['session_id'])
        session_type = data.get('session_type') or self.config.get('default_session_type', 'person')
        sender_meta = data.get('sender') or {}
        sender_name = str(sender_meta.get('name', 'User'))

        message_id = 'in_' + uuid.uuid4().hex
        chain = platform_message.MessageChain.model_validate(data['message'])
        # Carry the inbound message id + timestamp as the Source component.
        chain.insert(0, platform_message.Source(id=message_id, time=datetime.now()))

        if session_type == 'group':
            group = platform_entities.Group(
                id=session_id,
                name=str(sender_meta.get('group_name', session_id)),
                permission=platform_entities.Permission.Member,
            )
            sender = platform_entities.GroupMember(
                id=str(sender_meta.get('id', session_id)),
                member_name=sender_name,
                group=group,
                permission=platform_entities.Permission.Member,
            )
            event = platform_events.GroupMessage(sender=sender, message_chain=chain, time=datetime.now().timestamp())
        else:
            sender = platform_entities.Friend(id=session_id, nickname=sender_name, remark=sender_name)
            event = platform_events.FriendMessage(sender=sender, message_chain=chain, time=datetime.now().timestamp())
        return event, session_id, session_type, message_id

    async def _handle_inbound(self, request, sync: bool):
        data, err = await self._read_and_verify(request)
        if err is not None:
            return err

        if 'session_id' not in data or 'message' not in data:
            return self._err('bad_request', 'session_id and message are required')

        # Idempotency.
        idem = request.headers.get(signing.HEADER_IDEMPOTENCY)
        if idem:
            self._prune_idempotency()
            if idem in self.idempotency_cache:
                return self._err('duplicate', 'idempotency key already accepted')
            self.idempotency_cache[idem] = time.time()

        try:
            event, session_id, session_type, message_id = self._build_event(data)
        except Exception as e:  # noqa: BLE001
            return self._err('bad_request', f'failed to parse message: {e}')

        listener = self.listeners.get(type(event))
        if listener is None:
            return self._err('internal', 'no listener registered for event type')

        if sync:
            return await self._run_sync(event, listener, session_id, message_id)

        # Fire-and-collect: kick the pipeline, return 202 immediately.
        asyncio.create_task(listener(event, self))
        return quart.jsonify(
            {
                'code': 0,
                'msg': 'accepted',
                'data': {
                    'session_id': session_id,
                    'accepted_message_id': message_id,
                    'aggregating': True,
                },
            }
        ), 202

    async def _handle_reset(self, request):
        data, err = await self._read_and_verify(request)
        if err is not None:
            return err
        if 'session_id' not in data:
            return self._err('bad_request', 'session_id is required')

        session_id = str(data['session_id'])
        session_type = data.get('session_type') or self.config.get('default_session_type', 'person')
        launcher_type = 'group' if session_type == 'group' else 'person'

        removed = await self._reset_session(launcher_type, session_id)
        return quart.jsonify({'code': 0, 'msg': 'reset', 'data': {'session_id': session_id, 'removed': removed}}), 200

    async def _reset_session(self, launcher_type: str, launcher_id: str) -> bool:
        """Drop the matching session so the next message starts a fresh conversation."""
        execution_context = getattr(self.logger, 'execution_context', None)
        if (
            execution_context is None
            or not execution_context.instance_uuid
            or not execution_context.workspace_uuid
            or execution_context.placement_generation <= 0
            or not self.bot_uuid
        ):
            raise RuntimeError('http_bot reset requires a trusted execution scope')
        expected_prefix = (
            execution_context.instance_uuid,
            execution_context.workspace_uuid,
            execution_context.placement_generation,
            self.bot_uuid,
            launcher_type,
        )

        sess_mgr = self.ap.sess_mgr
        before = len(sess_mgr.session_list)
        sess_mgr.session_list = [
            s for s in sess_mgr.session_list if not self._matches_session_scope(s, expected_prefix, launcher_id)
        ]
        return len(sess_mgr.session_list) < before

    @staticmethod
    def _matches_session_scope(session, expected_prefix: tuple[str, str, int, str, str], launcher_id: str) -> bool:
        session_key = getattr(session, '_langbot_session_key', None)
        return (
            isinstance(session_key, tuple)
            and len(session_key) == 6
            and session_key[:5] == expected_prefix
            and str(session_key[5]) == launcher_id
        )

    # -- outbound -------------------------------------------------------------

    @staticmethod
    def _extract_session_id(message_source: platform_events.MessageEvent) -> str:
        if isinstance(message_source, platform_events.GroupMessage):
            return str(message_source.sender.group.id)
        return str(message_source.sender.id)

    @staticmethod
    def _extract_reply_to(message_source: platform_events.MessageEvent) -> str:
        for comp in message_source.message_chain:
            if isinstance(comp, platform_message.Source):
                return str(comp.id)
        return ''

    def _next_sequence(self, session_id: str, is_final: bool) -> int:
        state = self.outbound_states.setdefault(session_id, _SessionOutbound())
        if state.last_was_final:
            state.sequence = 1
        else:
            state.sequence += 1
        state.last_was_final = is_final
        return state.sequence

    async def _enqueue_callback(self, session_id: str, payload: dict) -> None:
        state = self.outbound_states.setdefault(session_id, _SessionOutbound())
        if state.worker is None or state.worker.done():
            state.worker = asyncio.create_task(self._outbound_worker(session_id, state))
        try:
            state.queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop oldest to bound memory, then enqueue (best-effort, at-least-once).
            try:
                state.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await self.logger.warning(f'http_bot outbound queue full for session {session_id}; dropped oldest')
            state.queue.put_nowait(payload)

    async def _outbound_worker(self, session_id: str, state: _SessionOutbound) -> None:
        while True:
            payload = await state.queue.get()
            try:
                await self._deliver_callback(payload)
            except Exception as e:  # noqa: BLE001
                await self.logger.error(f'http_bot callback delivery failed for {session_id}: {e}')
            finally:
                state.queue.task_done()

    async def _deliver_callback(self, payload: dict) -> None:
        callback_url = self.config.get('callback_url', '')
        if not callback_url:
            await self.logger.warning('http_bot has no callback_url configured; dropping reply')
            return

        body = json.dumps(payload, ensure_ascii=False).encode()
        secret = self.config.get('outbound_secret') or self.config.get('inbound_secret', '')
        ts, sig = signing.sign(secret, body)
        headers = {
            'Content-Type': 'application/json',
            signing.HEADER_TIMESTAMP: ts,
            signing.HEADER_SIGNATURE: sig,
        }
        timeout = aiohttp.ClientTimeout(total=int(self.config.get('callback_timeout', 15)))
        max_retries = int(self.config.get('callback_max_retries', 3))

        session = httpclient.get_session()
        attempt = 0
        while True:
            attempt += 1
            try:
                async with session.post(callback_url, data=body, headers=headers, timeout=timeout) as resp:
                    if resp.status < 400:
                        return
                    if resp.status < 500 or attempt > max_retries:
                        await self.logger.warning(f'http_bot callback {callback_url} -> {resp.status}, giving up')
                        return
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt > max_retries:
                    await self.logger.warning(f'http_bot callback {callback_url} failed after {attempt} tries: {e}')
                    return
            await asyncio.sleep(min(2 ** (attempt - 1), 30))

    async def _emit_reply(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        is_final: bool,
        stream: bool,
    ) -> dict:
        session_id = self._extract_session_id(message_source)
        reply_to = self._extract_reply_to(message_source)
        sequence = self._next_sequence(session_id, is_final)
        parts = [c.model_dump() if hasattr(c, 'model_dump') else c.__dict__ for c in message]
        payload = {
            'session_id': session_id,
            'reply_to': reply_to,
            'sequence': sequence,
            'is_final': is_final,
            'stream': stream,
            'message': parts,
            'timestamp': datetime.now().isoformat(),
        }

        # If a /sync request is awaiting this session, collect instead of POSTing.
        collector = self.sync_waiters.get(session_id)
        if collector is not None:
            collector.parts.extend(parts)
            if is_final:
                collector.done.set()
            return payload

        await self._enqueue_callback(session_id, payload)
        return payload

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain) -> dict:
        """Proactively push a message to a session (target_id == session_id)."""
        sequence = self._next_sequence(str(target_id), is_final=True)
        payload = {
            'session_id': str(target_id),
            'reply_to': '',
            'sequence': sequence,
            'is_final': True,
            'stream': False,
            'message': [c.model_dump() if hasattr(c, 'model_dump') else c.__dict__ for c in message],
            'timestamp': datetime.now().isoformat(),
        }
        await self._enqueue_callback(str(target_id), payload)
        return payload

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> dict:
        return await self._emit_reply(message_source, message, is_final=True, stream=False)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ) -> dict:
        message_is_final = is_final and getattr(bot_message, 'tool_calls', None) is None
        return await self._emit_reply(message_source, message, is_final=message_is_final, stream=True)

    # -- sync convenience mode ------------------------------------------------

    async def _run_sync(self, event, listener, session_id: str, message_id: str):
        """Push a message and wait for the final reply, collapsing 1->M parts.

        Lossy by design (drops streaming/ordering nuance); documented as such.
        Concurrency-safe: routing is via the per-session ``_sync_waiters``
        registry that ``_emit_reply`` consults, not by patching methods.
        """
        if session_id in self.sync_waiters:
            return self._err('duplicate', 'a sync request is already in flight for this session')

        collector = _SyncCollector()
        self.sync_waiters[session_id] = collector
        try:
            asyncio.create_task(listener(event, self))
            timeout = int(self.config.get('callback_timeout', 15)) * 4
            try:
                await asyncio.wait_for(collector.done.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                await self.logger.warning(f'http_bot sync wait timed out for session {session_id}')
        finally:
            self.sync_waiters.pop(session_id, None)

        return quart.jsonify(
            {
                'code': 0,
                'msg': 'ok',
                'data': {
                    'session_id': session_id,
                    'reply_to': message_id,
                    'message': collector.parts,
                },
            }
        ), 200
