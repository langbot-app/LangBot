from __future__ import annotations

import asyncio
import json
import traceback
import typing
import zlib

import aiohttp
import pydantic
import websockets

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.kook.api_impl import KookAPIMixin
from langbot.pkg.platform.adapters.kook.event_converter import KookEventConverter
from langbot.pkg.platform.adapters.kook.message_converter import KookMessageConverter
from langbot.pkg.platform.adapters.kook.platform_api import PLATFORM_API_MAP
from langbot.pkg.platform.adapters.kook.errors import NotSupportedError
from langbot.pkg.utils import httpclient
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events


BasePlatformAdapter = getattr(
    abstract_platform_adapter,
    'AbstractPlatformAdapter',
    abstract_platform_adapter.AbstractMessagePlatformAdapter,
)


class KookAdapter(KookAPIMixin, BasePlatformAdapter):
    message_converter: KookMessageConverter = KookMessageConverter()
    event_converter: KookEventConverter = KookEventConverter()

    config: dict
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    ws: typing.Any = pydantic.Field(exclude=True, default=None)
    ws_task: typing.Optional[asyncio.Task] = pydantic.Field(exclude=True, default=None)
    heartbeat_task: typing.Optional[asyncio.Task] = pydantic.Field(exclude=True, default=None)
    running: bool = pydantic.Field(exclude=True, default=False)
    session_id: str = pydantic.Field(exclude=True, default='')
    current_sn: int = pydantic.Field(exclude=True, default=0)
    gateway_url: str = pydantic.Field(exclude=True, default='')
    http_session: typing.Optional[aiohttp.ClientSession] = pydantic.Field(exclude=True, default=None)

    _message_cache: dict[str, platform_events.MessageReceivedEvent] = {}
    _user_cache: dict[str, platform_entities.User] = {}
    _group_cache: dict[str, platform_entities.UserGroup] = {}

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        if not config.get('token'):
            raise Exception('KOOK adapter requires "token" in config')

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id='',
            listeners={},
            running=False,
            session_id='',
            current_sn=0,
            gateway_url='',
            http_session=None,
            _message_cache={},
            _user_cache={},
            _group_cache={},
            **kwargs,
        )

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
            'get_group_info',
            'get_group_list',
            'get_group_member_info',
            'get_user_info',
            'get_friend_list',
            'upload_file',
            'get_file_url',
            'delete_message',
            'forward_message',
            'call_platform_api',
        ]

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self, params)

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter],
            None,
        ],
    ):
        registered = self.listeners.get(event_type)
        if registered is callback:
            self.listeners.pop(event_type, None)

    async def run_async(self):
        self.running = True
        self.http_session = httpclient.get_session()
        await self.logger.info('KOOK EBA adapter starting')

        try:
            bot_info = await self._get_bot_user_info()
            self.bot_account_id = str(bot_info.get('id') or '')
        except Exception as e:
            await self.logger.error(f'Failed to get KOOK bot user info: {e}')

        self.ws_task = asyncio.create_task(self._websocket_loop())
        try:
            await self.ws_task
        finally:
            self.running = False

    async def kill(self) -> bool:
        self.running = False
        for task in (self.heartbeat_task, self.ws_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self.ws:
            await self.ws.close()
        await self.logger.info('KOOK EBA adapter stopped')
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    async def _handle_hello(self, data: dict):
        self.session_id = str(data.get('session_id') or '')
        await self.logger.info(f'KOOK WebSocket HELLO received, session_id: {self.session_id}')

    async def _handle_event(self, data: dict, sn: int):
        self.current_sn = max(self.current_sn, sn)

        event_type = int(data.get('type', 0) or 0)
        channel_type = data.get('channel_type')
        author_id = str(data.get('author_id') or '')
        is_message_event = event_type in KookEventConverter.MESSAGE_TYPES and channel_type in {'GROUP', 'PERSON'}

        if is_message_event and self.bot_account_id and author_id == self.bot_account_id:
            return

        try:
            if is_message_event and (
                platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners
            ):
                legacy_event = await self.event_converter.target2legacy(data, self.bot_account_id)
                callback = self.listeners.get(type(legacy_event))
                if callback:
                    await callback(legacy_event, self)

            eba_event = await self.event_converter.target2yiri(data, self.bot_account_id)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error handling KOOK event: {traceback.format_exc()}')

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

    async def _websocket_loop(self):
        retry_count = 0
        max_retries = int(self.config.get('max_retries', 3))

        while self.running and retry_count < max_retries:
            try:
                if not self.gateway_url:
                    self.gateway_url = await self._get_gateway_url()

                async with websockets.connect(self.gateway_url) as ws:
                    self.ws = ws
                    await self.logger.info('Connected to KOOK WebSocket')
                    self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    hello_msg = await asyncio.wait_for(ws.recv(), timeout=6.0)
                    hello_data = json.loads(self._decode_ws_message(hello_msg))
                    if hello_data.get('s') != 1:
                        raise Exception(f'Expected KOOK HELLO signal, got {hello_data.get("s")}')
                    await self._handle_hello(hello_data.get('d') or {})
                    retry_count = 0

                    async for message in ws:
                        msg_data = json.loads(self._decode_ws_message(message))
                        signal = msg_data.get('s')
                        if signal == 0:
                            await self._handle_event(msg_data.get('d') or {}, int(msg_data.get('sn') or 0))
                        elif signal == 5:
                            break
            except websockets.exceptions.ConnectionClosed:
                retry_count += 1
                await self.logger.warning('KOOK WebSocket connection closed, reconnecting')
                await asyncio.sleep(min(2**retry_count, 30))
            except asyncio.CancelledError:
                raise
            except Exception:
                retry_count += 1
                await self.logger.error(f'KOOK WebSocket error: {traceback.format_exc()}')
                await asyncio.sleep(min(2**retry_count, 30))
            finally:
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    try:
                        await self.heartbeat_task
                    except asyncio.CancelledError:
                        pass
                self.ws = None

        if retry_count >= max_retries:
            await self.logger.error(f'Failed to connect to KOOK after {max_retries} retries')

    async def _heartbeat_loop(self):
        try:
            while self.running and self.ws:
                await asyncio.sleep(30)
                if self.ws:
                    await self.ws.send(json.dumps({'s': 2, 'sn': self.current_sn}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.logger.error(f'KOOK heartbeat error: {e}')

    async def _get_gateway_url(self) -> str:
        raw = await self._request('GET', '/gateway/index', params={'compress': 1})
        return str(raw['data']['url'])

    async def _get_bot_user_info(self) -> dict:
        raw = await self._request('GET', '/user/me')
        return raw.get('data') or {}

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        data: dict | None = None,
        filename: str | None = None,
    ) -> dict:
        session = self.http_session or httpclient.get_session()
        self.http_session = session
        url = f'https://www.kookapp.cn/api/v3{endpoint}'
        headers = {'Authorization': f'Bot {self.config["token"]}'}

        request_kwargs: dict[str, typing.Any] = {'params': params, 'headers': headers}
        if json is not None:
            request_kwargs['json'] = json
        if data is not None and filename is not None:
            form = aiohttp.FormData()
            form.add_field('file', data['file'], filename=filename)
            request_kwargs['data'] = form
        elif data is not None:
            request_kwargs['data'] = data

        async with session.request(method, url, **request_kwargs) as response:
            payload = await response.json(content_type=None)
            if response.status != 200:
                raise Exception(f'KOOK API HTTP {response.status}: {payload}')
            if payload.get('code') != 0:
                raise Exception(f'KOOK API error {payload.get("code")}: {payload.get("message")}')
            return payload

    @staticmethod
    def _decode_ws_message(message) -> str:
        if isinstance(message, bytes):
            try:
                return zlib.decompress(message).decode('utf-8')
            except Exception:
                return message.decode('utf-8')
        return str(message)
