from __future__ import annotations

import asyncio
import traceback
import typing

import pydantic
import quart
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    MessagingApiBlob,
    PushMessageRequest,
    ReplyMessageRequest,
)
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhooks import Event

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message

from langbot.pkg.platform.adapters.line.api_impl import LineAPIMixin
from langbot.pkg.platform.adapters.line.errors import NotSupportedError
from langbot.pkg.platform.adapters.line.event_converter import LineEventConverter
from langbot.pkg.platform.adapters.line.message_converter import LineMessageConverter
from langbot.pkg.platform.adapters.line.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.line.types import ADAPTER_NAME, MAX_MESSAGES_PER_REQUEST


class LineAdapter(LineAPIMixin, abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """LINE Messaging API adapter in unified webhook mode."""

    api_client: typing.Any = pydantic.Field(exclude=True)
    bot: typing.Any = pydantic.Field(exclude=True)
    blob_api: typing.Any = pydantic.Field(exclude=True)
    parser: typing.Any = pydantic.Field(exclude=True)

    message_converter: LineMessageConverter = LineMessageConverter()
    event_converter: LineEventConverter = LineEventConverter()

    config: dict
    config_secret: str = ''
    bot_uuid: str | None = None

    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}
    background_tasks: set = pydantic.Field(default_factory=set, exclude=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        missing_keys = [key for key in ('channel_access_token', 'channel_secret') if not config.get(key)]
        if missing_keys:
            raise ValueError(f'LINE adapter missing config: {missing_keys}')
        configuration = Configuration(access_token=config['channel_access_token'])
        api_client = ApiClient(configuration)
        bot = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)
        bot_account_id = config.get('bot_account_id', '') or ''
        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=bot_account_id,
            config_secret=config['channel_secret'],
            api_client=api_client,
            bot=bot,
            blob_api=blob_api,
            parser=WebhookParser(config['channel_secret']),
            listeners={},
            background_tasks=set(),
            message_converter=LineMessageConverter(),
            event_converter=LineEventConverter(bot_account_id=bot_account_id, blob_api=blob_api),
        )

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def get_supported_events(self) -> list[str]:
        return [
            'message.received',
            'message.deleted',
            'group.member_joined',
            'group.member_left',
            'bot.invited_to_group',
            'bot.removed_from_group',
            'platform.specific',
        ]

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'get_user_info',
            'get_group_info',
            'leave_group',
            'call_platform_api',
        ]

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        messages = await self.message_converter.yiri2target(message)
        for batch in _batches(messages):
            request = PushMessageRequest(to=str(target_id), messages=batch)
            await asyncio.to_thread(self.bot.push_message, request)
        return platform_events.MessageResult(raw={'sent': len(messages), 'target_id': str(target_id)})

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        source = await LineEventConverter.yiri2target(message_source)
        messages = await self.message_converter.yiri2target(message)
        reply_token = str(getattr(source, 'reply_token', '') or '')
        chat_id = _source_chat_id(source) or str(getattr(message_source, 'chat_id', '') or '')
        for batch in _batches(messages):
            if reply_token:
                try:
                    await asyncio.to_thread(
                        self.bot.reply_message, ReplyMessageRequest(reply_token=reply_token, messages=batch)
                    )
                    # A reply token is single-use; later batches of the same turn fall back to push.
                    reply_token = ''
                    continue
                except Exception:
                    await self.logger.warning(
                        f'LINE reply token rejected, falling back to push: {traceback.format_exc()}'
                    )
                    reply_token = ''
            if not chat_id:
                raise NotSupportedError('reply_message:line_missing_target')
            await asyncio.to_thread(self.bot.push_message, PushMessageRequest(to=chat_id, messages=batch))
        return platform_events.MessageResult(raw={'sent': len(messages)})

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

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request) -> typing.Any:
        signature = request.headers.get('X-Line-Signature')
        body = await request.get_data(as_text=True)
        if not signature:
            await self.logger.warning('LINE webhook rejected: missing X-Line-Signature header')
            return quart.Response('Missing X-Line-Signature header', status=400)
        try:
            events = self.parser.parse(body, signature)
        except InvalidSignatureError:
            await self.logger.warning(
                'LINE webhook rejected: invalid signature, check channel_access_token/channel_secret'
            )
            return quart.Response('Invalid signature', status=400)
        for event in events or []:
            task = asyncio.create_task(self._dispatch_native_event(event))
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)
        # Acknowledge immediately; LINE retries any non-200 answer.
        return quart.Response('OK', status=200)

    async def _dispatch_native_event(self, event: Event) -> None:
        try:
            if self.bot_account_id and _sender_id(event) == self.bot_account_id:
                return
            eba_event = await self.event_converter.target2yiri(event)
            if eba_event is None:
                return
            if isinstance(eba_event, platform_events.MessageReceivedEvent):
                legacy_event = eba_event.to_legacy_event()
                listener = self.listeners.get(type(legacy_event))
                if listener:
                    await listener(legacy_event, self)
            await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'LINE native event error: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.EBAEvent) -> None:
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    async def run_async(self):
        if not self.bot_account_id:
            try:
                info = await asyncio.to_thread(self.bot.get_bot_info)
                self.bot_account_id = info.user_id
                self.event_converter.bot_account_id = info.user_id
            except Exception:
                await self.logger.warning(
                    'LINE adapter could not resolve its account id; self-message filtering stays disabled'
                )
        await self.logger.info(f'{ADAPTER_NAME} adapter running in unified webhook mode')
        while True:
            await asyncio.sleep(1)

    async def kill(self) -> bool:
        for task in list(self.background_tasks):
            task.cancel()
        self.background_tasks.clear()
        await asyncio.to_thread(self.api_client.close)
        return True


def _batches(messages: list[typing.Any]) -> list[list[typing.Any]]:
    """Split a message array into LINE's per-request budget."""
    return [
        messages[index : index + MAX_MESSAGES_PER_REQUEST]
        for index in range(0, len(messages), MAX_MESSAGES_PER_REQUEST)
    ]


def _sender_id(event: Event) -> str:
    source = getattr(event, 'source', None)
    return str(getattr(source, 'user_id', '') or '')


def _source_chat_id(event: Event) -> str:
    """Chat id of the conversation a LINE event belongs to."""
    source = getattr(event, 'source', None)
    for attribute in ('group_id', 'room_id', 'user_id'):
        value = getattr(source, attribute, '') or ''
        if value:
            return str(value)
    return ''
