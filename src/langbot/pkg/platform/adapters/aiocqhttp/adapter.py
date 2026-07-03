from __future__ import annotations

import asyncio
import traceback
import typing

import aiocqhttp
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
    bot: aiocqhttp.CQHttp = pydantic.Field(exclude=True)

    message_converter: AiocqhttpMessageConverter = AiocqhttpMessageConverter()
    event_converter: AiocqhttpEventConverter = pydantic.Field(default_factory=AiocqhttpEventConverter)

    config: dict
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        run_config = dict(config)

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        run_config['shutdown_trigger'] = shutdown_trigger_placeholder
        access_token = run_config.pop('access-token', '') or None
        bot = aiocqhttp.CQHttp(access_token=access_token)

        super().__init__(
            config=run_config,
            logger=logger,
            bot=bot,
            bot_account_id='',
            listeners={},
        )
        self._register_native_handlers()

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
        await self.bot._server_app.run_task(**self.config)

    async def kill(self) -> bool:
        return False

    def _register_native_handlers(self):
        @self.bot.on_message()
        async def on_message(event: aiocqhttp.Event):
            await self._handle_native_event(event)

        @self.bot.on_notice()
        async def on_notice(event: aiocqhttp.Event):
            await self._handle_native_event(event)

        @self.bot.on_request()
        async def on_request(event: aiocqhttp.Event):
            await self._handle_native_event(event)

        @self.bot.on_websocket_connection
        async def on_websocket_connection(event: aiocqhttp.Event):
            self.bot_account_id = str(getattr(event, 'self_id', '') or self.bot_account_id)
            await self.logger.info(f'WebSocket connection established, bot id: {self.bot_account_id}')
            await self._dispatch_native_event(event)

    async def _handle_native_event(self, event: aiocqhttp.Event):
        self.bot_account_id = str(getattr(event, 'self_id', '') or self.bot_account_id)
        if getattr(event, 'type', None) == 'message' and str(getattr(event, 'user_id', '')) == self.bot_account_id:
            return
        try:
            if getattr(event, 'type', None) == 'message' and (
                platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners
            ):
                legacy_event = await self.event_converter.target2legacy(event, self.bot)
                if legacy_event:
                    callback = self.listeners.get(type(legacy_event))
                    if callback:
                        await callback(legacy_event, self)
            await self._dispatch_native_event(event)
        except Exception:
            await self.logger.error(f'Error in aiocqhttp native event: {traceback.format_exc()}')

    async def _dispatch_native_event(self, event: aiocqhttp.Event):
        eba_event = await self.event_converter.target2yiri(event, self.bot, self.bot_account_id)
        if eba_event:
            await self._dispatch_eba_event(eba_event)

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return
