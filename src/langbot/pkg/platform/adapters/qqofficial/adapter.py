from __future__ import annotations

import asyncio
import time
import traceback
import typing

import pydantic

from langbot.libs.qq_official_api.api import QQOfficialClient
from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from langbot.pkg.platform.adapters.qqofficial.api_impl import QQOfficialAPIMixin
from langbot.pkg.platform.adapters.qqofficial.errors import NotSupportedError
from langbot.pkg.platform.adapters.qqofficial.event_converter import QQOfficialEventConverter
from langbot.pkg.platform.adapters.qqofficial.message_converter import QQOfficialMessageConverter
from langbot.pkg.platform.adapters.qqofficial.platform_api import PLATFORM_API_MAP
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message


class QQOfficialAdapter(QQOfficialAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: typing.Any = pydantic.Field(exclude=True)

    message_converter: QQOfficialMessageConverter = QQOfficialMessageConverter()
    event_converter: QQOfficialEventConverter = QQOfficialEventConverter()

    config: dict
    bot_uuid: str | None = None
    enable_webhook: bool = False
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}
    _group_cache: dict[str, platform_entities.UserGroup] = {}
    _member_cache: dict[tuple[str, str], platform_entities.UserGroupMember] = {}
    _stream_ctx: dict[str, dict] = {}
    _stream_ctx_ts: dict[str, float] = {}
    _fallback_text: dict[str, str] = {}
    _fallback_text_ts: dict[str, float] = {}
    _ws_task: asyncio.Task | None = None

    _STREAM_CTX_TTL = 300

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = ['appid', 'secret', 'token']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise Exception(f'QQOfficial EBA adapter missing config: {missing_keys}')

        enable_webhook = config.get('enable-webhook', config.get('enable_webhook', False))
        bot = QQOfficialClient(
            app_id=config['appid'],
            secret=config['secret'],
            token=config['token'],
            logger=logger,
            unified_mode=enable_webhook,
        )
        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=config['appid'],
            bot_uuid=None,
            enable_webhook=enable_webhook,
            listeners={},
            _message_cache={},
            _user_cache={},
            _group_cache={},
            _member_cache={},
            _stream_ctx={},
            _stream_ctx_ts={},
            _fallback_text={},
            _fallback_text_ts={},
            _ws_task=None,
        )
        self._register_native_handlers()

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'get_message',
            'get_user_info',
            'get_friend_list',
            'get_group_info',
            'get_group_member_list',
            'get_group_member_info',
            'call_platform_api',
        ]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        raw = await self._send_content_list(str(target_type), str(target_id), await QQOfficialMessageConverter.yiri2target(message))
        return platform_events.MessageResult(raw={'results': raw})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        source = await QQOfficialEventConverter.yiri2target(message_source)
        if not isinstance(source, QQOfficialEvent):
            raise ValueError('QQOfficial reply_message requires a QQOfficialEvent source object')
        target_type, target_id = self._reply_target(source)
        raw = await self._send_content_list(
            target_type,
            target_id,
            await QQOfficialMessageConverter.yiri2target(message),
            msg_id=source.d_id,
        )
        return platform_events.MessageResult(message_id=source.d_id or source.id, raw={'results': raw})

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self, dict(params or {}))

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

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        if self.enable_webhook:
            await self.logger.info('QQ Official EBA adapter running in unified webhook mode')
            while True:
                await asyncio.sleep(1)
        else:
            await self._run_websocket()

    async def kill(self) -> bool:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    async def is_stream_output_supported(self) -> bool:
        return bool(self.config.get('enable-stream-reply') or self.config.get('enable_stream_reply'))

    async def create_message_card(self, message_id: str, event: platform_events.MessageEvent) -> bool:
        source = event.source_platform_object
        if not isinstance(source, QQOfficialEvent) or source.t != 'C2C_MESSAGE_CREATE':
            return False
        self._stream_ctx[message_id] = {
            'user_openid': source.user_openid,
            'msg_id': source.d_id,
            'stream_msg_id': None,
            'msg_seq': 1,
            'index': 0,
            'last_update_ts': 0,
            'accumulated_text': '',
            'sent_length': 0,
            'session_started': False,
        }
        self._stream_ctx_ts[message_id] = time.time()
        return True

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message: dict,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        await self._cleanup_stale_streams()
        chunk_text = '\n\n'.join(component.text for component in message if isinstance(component, platform_message.Plain))
        message_id = bot_message.get('resp_message_id') if isinstance(bot_message, dict) else getattr(bot_message, 'resp_message_id', None)
        if not message_id or message_id not in self._stream_ctx:
            if chunk_text:
                self._fallback_text[message_id] = self._fallback_text.get(message_id, '') + chunk_text
                self._fallback_text_ts[message_id] = time.time()
            if is_final:
                full_text = self._fallback_text.pop(message_id, '')
                if full_text:
                    await self.reply_message(message_source, platform_message.MessageChain([platform_message.Plain(text=full_text)]), quote_origin)
            return

        ctx = self._stream_ctx[message_id]
        if chunk_text:
            ctx['accumulated_text'] += chunk_text
        if not ctx['session_started']:
            if not ctx['accumulated_text']:
                return
            ctx['session_started'] = True

        content_to_send = ctx['accumulated_text'][ctx['sent_length'] :]
        if not content_to_send and not is_final:
            return
        now = time.time()
        if not is_final and (now - ctx['last_update_ts']) < 0.5:
            return
        ctx['last_update_ts'] = now

        resp = await self.bot.send_stream_msg(
            user_openid=ctx['user_openid'],
            content=content_to_send,
            event_id=ctx['msg_id'],
            msg_id=ctx['msg_id'],
            msg_seq=ctx['msg_seq'],
            index=ctx['index'],
            stream_msg_id=ctx['stream_msg_id'],
            input_state=10 if is_final else 1,
        )
        if isinstance(resp, dict) and resp.get('id'):
            ctx['stream_msg_id'] = resp['id']
        ctx['sent_length'] = len(ctx['accumulated_text'])
        ctx['index'] += 1
        if is_final:
            self._stream_ctx.pop(message_id, None)
            self._stream_ctx_ts.pop(message_id, None)

    def _register_native_handlers(self):
        for event_type in ('C2C_MESSAGE_CREATE', 'DIRECT_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE', 'AT_MESSAGE_CREATE'):
            self.bot.on_message(event_type)(self._handle_native_event)

    async def _handle_native_event(self, event: QQOfficialEvent):
        self.bot_account_id = self.config.get('appid', self.bot_account_id)
        try:
            if platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event)
                if legacy_event and type(legacy_event) in self.listeners:
                    await self.listeners[type(legacy_event)](legacy_event, self)

            eba_event = await self.event_converter.target2yiri(event)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in qqofficial native event: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    def _cache_event(self, event: platform_events.Event):
        if not isinstance(event, platform_events.MessageReceivedEvent):
            return
        self._message_cache[str(event.message_id)] = event
        self._user_cache[str(event.sender.id)] = event.sender
        if event.group:
            self._group_cache[str(event.group.id)] = event.group
            self._member_cache[(str(event.group.id), str(event.sender.id))] = platform_entities.UserGroupMember(
                user=event.sender,
                group_id=event.group.id,
                role=platform_entities.MemberRole.MEMBER,
                display_name=event.sender.nickname,
            )

    async def _run_websocket(self):
        await self.logger.info('QQ Official EBA adapter starting in WebSocket mode')

        async def on_ready():
            await self.logger.info('QQ Official WebSocket connected and ready')

        async def on_event(event_type: str, event_data: dict):
            if event_type not in {'C2C_MESSAGE_CREATE', 'DIRECT_MESSAGE_CREATE', 'GROUP_AT_MESSAGE_CREATE', 'AT_MESSAGE_CREATE'}:
                await self._dispatch_eba_event(QQOfficialEventConverter.platform_specific(QQOfficialEvent({'t': event_type, **(event_data or {})}), f'qqofficial.{event_type}'))
                return
            if not isinstance(event_data, dict):
                await self.logger.warning(f'Event data is not dict, skipping: {event_type} -> {type(event_data)}')
                return
            payload = {'t': event_type, 'd': event_data}
            message_data = await self.bot.get_message(payload)
            if message_data:
                await self.bot._handle_message(QQOfficialEvent.from_payload(message_data))

        async def on_error(error: Exception):
            await self.logger.error(f'QQ Official WebSocket error: {error}')

        self._ws_task = asyncio.create_task(self.bot.connect_gateway_loop(on_event, on_ready, on_error))
        try:
            await self._ws_task
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _reply_target(event: QQOfficialEvent) -> tuple[str, str]:
        if event.t == 'C2C_MESSAGE_CREATE':
            return 'person', event.user_openid
        if event.t == 'GROUP_AT_MESSAGE_CREATE':
            return 'group', event.group_openid
        if event.t == 'AT_MESSAGE_CREATE':
            return 'channel', event.channel_id
        if event.t == 'DIRECT_MESSAGE_CREATE':
            return 'channel_private', event.guild_id
        raise NotSupportedError(f'reply_message:{event.t or "unknown_event"}')

    async def _send_content_list(self, target_type: str, target_id: str, content_list: list[dict], msg_id: str | None = None) -> list[dict]:
        target_type = self._normalize_target_type(target_type)
        results: list[dict] = []
        for content in content_list:
            content_type = content.get('type', 'text')
            if target_type == 'channel':
                if content_type == 'text':
                    raw = await self.bot.send_channle_group_text_msg(target_id, content.get('content', ''), msg_id)
                    results.append({'type': content_type, 'raw': raw})
                continue
            if target_type == 'channel_private':
                if content_type == 'text':
                    raw = await self.bot.send_channle_private_text_msg(target_id, content.get('content', ''), msg_id)
                    results.append({'type': content_type, 'raw': raw})
                continue
            if content_type == 'text':
                if target_type == 'c2c':
                    raw = await self.bot.send_private_text_msg(target_id, content.get('content', ''), msg_id)
                elif target_type == 'group':
                    raw = await self.bot.send_group_text_msg(target_id, content.get('content', ''), msg_id)
                else:
                    raise NotSupportedError(f'send_message:{target_type}')
                results.append({'type': content_type, 'raw': raw})
            elif content_type == 'image':
                raw = await self.bot.send_image_msg(target_type, target_id, file_url=content.get('url'), file_data=content.get('base64'), msg_id=msg_id)
                results.append({'type': content_type, 'raw': raw})
            elif content_type == 'voice':
                raw = await self.bot.send_voice_msg(target_type, target_id, file_url=content.get('url'), file_data=content.get('base64'), msg_id=msg_id)
                results.append({'type': content_type, 'raw': raw})
            elif content_type == 'file':
                raw = await self.bot.send_file_msg(
                    target_type,
                    target_id,
                    file_url=content.get('url'),
                    file_data=content.get('base64'),
                    file_name=content.get('name', 'file'),
                    msg_id=msg_id,
                )
                results.append({'type': content_type, 'raw': raw})
        return results

    @staticmethod
    def _normalize_target_type(target_type: str) -> str:
        if target_type in {'person', 'private', 'friend', 'c2c'}:
            return 'c2c'
        if target_type in {'group', 'group_openid'}:
            return 'group'
        if target_type in {'channel', 'guild'}:
            return 'channel'
        if target_type in {'channel_private', 'direct', 'dm'}:
            return 'channel_private'
        return target_type

    async def _cleanup_stale_streams(self):
        now = time.time()
        for message_id in [key for key, ts in self._stream_ctx_ts.items() if now - ts > self._STREAM_CTX_TTL]:
            self._stream_ctx.pop(message_id, None)
            self._stream_ctx_ts.pop(message_id, None)
        for message_id in [key for key, ts in self._fallback_text_ts.items() if now - ts > self._STREAM_CTX_TTL]:
            self._fallback_text.pop(message_id, None)
            self._fallback_text_ts.pop(message_id, None)
