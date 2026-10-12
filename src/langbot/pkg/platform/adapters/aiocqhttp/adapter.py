from __future__ import annotations

import asyncio
import traceback
import hmac
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from langbot.pkg.core.task_boundary import create_detached_task
from langbot.pkg.platform.adapters.aiocqhttp.transport import OneBotClient, OneBotConnection
import typing

import aiocqhttp

from langbot.pkg.platform.sources.aiocqhttp import AiocqhttpEventConverter as LegacyAiocqhttpEventConverter
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.aiocqhttp.api_impl import AiocqhttpAPIMixin
from langbot.pkg.platform.adapters.aiocqhttp.event_converter import AiocqhttpEventConverter
from langbot.pkg.platform.adapters.aiocqhttp.message_converter import AiocqhttpMessageConverter
from langbot.pkg.platform.adapters.aiocqhttp.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class AiocqhttpAdapter(AiocqhttpAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: typing.Any = pydantic.Field(exclude=True)
    _runtime: typing.Any = pydantic.PrivateAttr(default=None)
    _stopped: asyncio.Event = pydantic.PrivateAttr(default_factory=asyncio.Event)
    _connection_task: typing.Any = pydantic.PrivateAttr(default=None)

    message_converter: AiocqhttpMessageConverter = AiocqhttpMessageConverter()
    event_converter: AiocqhttpEventConverter = AiocqhttpEventConverter()

    _lookup: typing.Any = pydantic.PrivateAttr(default_factory=LegacyAiocqhttpEventConverter)
    config: dict
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        config = dict(config)
        config.setdefault('connection_mode', 'reverse_ws')
        if not isinstance(config.get('access-token'), str) or not config['access-token'].strip():
            raise ValueError('OneBot requires a non-empty access token')
        if config['connection_mode'] not in ('reverse_ws', 'forward_ws'):
            raise ValueError('Unsupported OneBot connection mode')
        if config['connection_mode'] == 'forward_ws':
            url = urlsplit(config.get('ws_url', ''))
            if url.scheme not in ('ws', 'wss') or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError('OneBot ws_url must be a ws:// or wss:// endpoint without embedded credentials')
        super().__init__(config=config, logger=logger, bot=OneBotClient(), bot_account_id='', listeners={})

    def bind_runtime(self, runtime):
        self._runtime = runtime

    async def _validate_connection(self):
        if self._stopped.is_set() or self._runtime is None:
            raise RuntimeError('OneBot runtime is inactive')
        current = await self._runtime.ap.platform_mgr.resolve_public_bot(self._runtime.bot_entity.uuid)
        if current is not self._runtime or not current.enable:
            raise RuntimeError('OneBot runtime placement changed')

    def authenticate(self, headers):
        token = str(self.config.get('access-token', ''))
        supplied = headers.get('Authorization', '')
        return bool(token) and hmac.compare_digest(supplied.encode(), ('Bearer ' + token).encode())

    async def serve_connection(self, send, receive, close, self_id=''):
        await self._validate_connection()
        if self.bot.connection is not None:
            raise RuntimeError('OneBot already has an active connection')
        expected = str(self.config.get('self_id', '') or '')
        if expected and self_id and expected != self_id:
            raise ValueError('OneBot account mismatch')
        connection = OneBotConnection(
            send,
            receive,
            close,
            self._receive_event,
            self._validate_connection,
            self_id=expected or self_id,
        )
        self.bot.connection = connection
        self.bot_account_id = expected or self_id
        self._lookup.clear()
        task = create_detached_task(connection.run(), workspace_uuid=self._runtime.workspace_uuid)
        self._connection_task = task
        try:
            await task
        finally:
            await connection.close()
            if self.bot.connection is connection:
                self.bot.connection = None
                self._connection_task = None
                self._lookup.clear()

    async def _receive_event(self, payload):
        await self._handle_native_event(aiocqhttp.Event.from_payload(payload))

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'message.deleted',
            'group.member_joined',
            'group.member_left',
            'group.member_banned',
            'friend.request_received',
            'friend.added',
            'bot.invited_to_group',
            'bot.removed_from_group',
            'bot.muted',
            'bot.unmuted',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'delete_message',
            'forward_message',
            'get_message',
            'get_group_info',
            'get_group_list',
            'get_group_member_list',
            'get_group_member_info',
            'set_group_name',
            'get_user_info',
            'get_friend_list',
            'approve_friend_request',
            'approve_group_invite',
            'mute_member',
            'unmute_member',
            'kick_member',
            'leave_group',
            'call_platform_api',
        ]

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self.bot, params)

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
        registered = self.listeners.get(event_type)
        if registered is callback:
            self.listeners.pop(event_type, None)

    async def run_async(self):
        if not self.config.get('access-token'):
            raise ValueError('OneBot requires a non-empty access token')
        if self.config['connection_mode'] == 'reverse_ws':
            await self._stopped.wait()
            return
        delay = 1
        while not self._stopped.is_set():
            await self._validate_connection()
            try:
                async with connect(
                    self.config['ws_url'],
                    additional_headers={'Authorization': 'Bearer ' + self.config['access-token']},
                    open_timeout=10,
                    close_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=8 * 1024 * 1024,
                    proxy=None,
                ) as socket:
                    delay = 1
                    await self.serve_connection(socket.send, socket.recv, socket.close)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.logger.warning(f'OneBot connection lost ({type(exc).__name__}); reconnecting')
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=delay)
            except TimeoutError:
                pass
            delay = min(delay * 2, 30)

    async def kill(self) -> bool:
        self._stopped.set()
        task = self._connection_task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._lookup.clear()
        return True

    async def _handle_native_event(self, event: aiocqhttp.Event):
        self.bot_account_id = str(getattr(event, 'self_id', '') or self.bot_account_id)
        # Connection metadata belongs to the adapter, never business event routing.
        if getattr(event, 'type', None) == 'meta_event':
            return
        if getattr(event, 'type', None) == 'message' and str(getattr(event, 'user_id', '')) == self.bot_account_id:
            return
        try:
            if getattr(event, 'type', None) == 'message' and (
                platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners
            ):
                legacy_event = await self.event_converter.target2legacy(event, self.bot, self._lookup)
                if legacy_event:
                    callback = self.listeners.get(type(legacy_event))
                    if callback:
                        await callback(legacy_event, self)
            await self._dispatch_native_event(event)
        except Exception:
            await self.logger.error(f'Error in aiocqhttp native event: {traceback.format_exc()}')

    async def _dispatch_native_event(self, event: aiocqhttp.Event):
        eba_event = await self.event_converter.target2yiri(event, self.bot, self.bot_account_id, self._lookup)
        if eba_event:
            await self._dispatch_eba_event(eba_event)

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return
