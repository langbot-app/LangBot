from __future__ import annotations

import asyncio
import json
import re
import typing
from urllib.parse import urlsplit, urlunsplit

import aiohttp

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


_MATTERMOST_MAX_POST_LENGTH = 16_383
_MENTION_BOUNDARY = r'(?<![\w.-])@{username}(?![\w.-])'


def _normalize_server_url(server_url: str) -> str:
    """Return a validated Mattermost server URL without a trailing slash."""

    url = server_url.strip().rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Mattermost server_url must be an absolute HTTP(S) URL')
    return url


def _websocket_url(server_url: str) -> str:
    parsed = urlsplit(server_url)
    scheme = 'wss' if parsed.scheme == 'https' else 'ws'
    return urlunsplit((scheme, parsed.netloc, f'{parsed.path}/api/v4/websocket', '', ''))


class MattermostMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Translate Mattermost post text to and from LangBot message chains."""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> str:
        parts: list[str] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                parts.append(component.text)
            elif isinstance(component, platform_message.Image) and component.url:
                # Mattermost renders image URLs in Markdown messages.
                parts.append(component.url)
            elif isinstance(component, platform_message.File) and component.url:
                parts.append(component.url)
        return ''.join(parts)

    @staticmethod
    async def target2yiri(post: dict, bot_username: str) -> platform_message.MessageChain:
        text = str(post.get('message') or '')
        components: list[typing.Any] = [
            platform_message.Source(
                id=str(post.get('id') or ''),
                time=float(post.get('create_at') or 0) / 1000,
            )
        ]
        if bot_username:
            mention_pattern = re.compile(_MENTION_BOUNDARY.format(username=re.escape(bot_username)), re.IGNORECASE)
            if mention_pattern.search(text):
                components.append(platform_message.At(target=bot_username))
                text = mention_pattern.sub('', text).strip()
        if text:
            components.append(platform_message.Plain(text=text))
        return platform_message.MessageChain(components)


class MattermostEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(
        post: dict,
        channel: dict,
        sender_name: str,
        bot_username: str,
    ) -> platform_events.MessageEvent:
        message_chain = await MattermostMessageConverter.target2yiri(post, bot_username)
        timestamp = float(post.get('create_at') or 0) / 1000
        sender_id = str(post.get('user_id') or '')
        channel_type = channel.get('type')

        if channel_type == 'D':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(id=sender_id, nickname=sender_name or sender_id, remark=''),
                message_chain=message_chain,
                time=timestamp,
                source_platform_object={'post': post, 'channel': channel},
            )

        return platform_events.GroupMessage(
            sender=platform_entities.GroupMember(
                id=sender_id,
                member_name=sender_name or sender_id,
                permission=platform_entities.Permission.Member,
                group=platform_entities.Group(
                    id=str(post.get('channel_id') or ''),
                    name=str(channel.get('display_name') or channel.get('name') or post.get('channel_id') or ''),
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            ),
            message_chain=message_chain,
            time=timestamp,
            source_platform_object={'post': post, 'channel': channel},
        )


class MattermostAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Mattermost Bot Account adapter using the v4 REST and WebSocket APIs."""

    server_url: str = ''
    access_token: str = ''
    session: aiohttp.ClientSession | None = None
    listeners: dict[typing.Type[platform_events.Event], typing.Callable] = {}
    channel_cache: dict[str, dict] = {}
    stream_post_ids: dict[str, str] = {}
    bot_username: str = ''
    _running: bool = False

    message_converter: MattermostMessageConverter = MattermostMessageConverter()
    event_converter: MattermostEventConverter = MattermostEventConverter()

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        server_url = _normalize_server_url(str(config.get('server_url') or ''))
        access_token = str(config.get('access_token') or '').strip()
        if not access_token:
            raise ValueError('Mattermost adapter requires an access_token')

        super().__init__(
            config=config,
            logger=logger,
            server_url=server_url,
            access_token=access_token,
            bot_account_id='',
            session=None,
            listeners={},
            channel_cache={},
            stream_post_ids={},
            bot_username='',
            _running=False,
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={'Authorization': f'Bearer {self.access_token}'},
                raise_for_status=False,
            )
        return self.session

    async def _api_request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
    ) -> dict:
        session = await self._get_session()
        async with session.request(method, f'{self.server_url}/api/v4{path}', json=payload) as response:
            raw_body = await response.text()
            if response.status >= 400:
                # Mattermost returns a useful JSON error, but never include request headers/tokens in errors.
                try:
                    error = json.loads(raw_body).get('message', raw_body)
                except json.JSONDecodeError:
                    error = raw_body
                raise RuntimeError(f'Mattermost API {method} {path} failed ({response.status}): {error}')
            if not raw_body:
                return {}
            return json.loads(raw_body)

    async def _load_bot_identity(self) -> None:
        user = await self._api_request('GET', '/users/me')
        self.bot_account_id = str(user.get('id') or '')
        self.bot_username = str(user.get('username') or '')
        if not self.bot_account_id:
            raise RuntimeError('Mattermost API did not return a bot user ID')

    async def _get_channel(self, channel_id: str) -> dict:
        if channel_id not in self.channel_cache:
            self.channel_cache[channel_id] = await self._api_request('GET', f'/channels/{channel_id}')
        return self.channel_cache[channel_id]

    async def _post_message(self, channel_id: str, text: str, root_id: str = '') -> dict:
        if not text:
            return {}
        if len(text) > _MATTERMOST_MAX_POST_LENGTH:
            raise ValueError(f'Mattermost messages cannot exceed {_MATTERMOST_MAX_POST_LENGTH} characters')
        payload = {'channel_id': channel_id, 'message': text}
        if root_id:
            payload['root_id'] = root_id
        return await self._api_request('POST', '/posts', payload=payload)

    async def _get_direct_channel_id(self, user_id: str) -> str:
        if not self.bot_account_id:
            await self._load_bot_identity()
        channel = await self._api_request(
            'POST',
            '/channels/direct',
            payload={'user_ids': [self.bot_account_id, user_id]},
        )
        channel_id = str(channel.get('id') or '')
        if not channel_id:
            raise RuntimeError('Mattermost did not return a direct-message channel ID')
        self.channel_cache[channel_id] = channel
        return channel_id

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        if target_type not in {'person', 'group'}:
            raise ValueError("Mattermost target_type must be 'person' or 'group'")
        text = await self.message_converter.yiri2target(message)
        channel_id = str(target_id)
        if target_type == 'person':
            channel_id = await self._get_direct_channel_id(channel_id)
        await self._post_message(channel_id, text)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        source = await self.event_converter.yiri2target(message_source)
        post = source['post']
        text = await self.message_converter.yiri2target(message)
        # A message received inside a Mattermost thread must remain in that thread. When
        # quote_origin is requested, make the response a reply to the source root post.
        root_id = str(post.get('root_id') or '')
        if quote_origin and not root_id:
            root_id = str(post.get('id') or '')
        await self._post_message(str(post['channel_id']), text, root_id)

    async def create_message_card(self, message_id: str, event: platform_events.MessageEvent) -> bool:
        source = await self.event_converter.yiri2target(event)
        post = source['post']
        root_id = str(post.get('root_id') or post.get('id') or '')
        created = await self._post_message(str(post['channel_id']), 'Thinking…', root_id)
        if created.get('id'):
            self.stream_post_ids[str(message_id)] = str(created['id'])
            return True
        return False

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        response_id = str(bot_message.resp_message_id)
        text = await self.message_converter.yiri2target(message)
        if not text:
            return

        post_id = self.stream_post_ids.get(response_id)
        if post_id:
            await self._api_request('PUT', f'/posts/{post_id}', payload={'id': post_id, 'message': text})
        else:
            source = await self.event_converter.yiri2target(message_source)
            post = source['post']
            root_id = str(post.get('root_id') or '')
            if quote_origin and not root_id:
                root_id = str(post.get('id') or '')
            created = await self._post_message(str(post['channel_id']), text, root_id)
            post_id = str(created.get('id') or '')
            if post_id:
                self.stream_post_ids[response_id] = post_id

        if is_final and getattr(bot_message, 'tool_calls', None) is None:
            self.stream_post_ids.pop(response_id, None)

    async def is_stream_output_supported(self) -> bool:
        return bool(self.config.get('enable_stream_reply', True))

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], typing.Awaitable[None]
        ],
    ):
        self.listeners.pop(event_type, None)

    async def _dispatch_post(self, payload: dict) -> None:
        data = payload.get('data') or {}
        try:
            post = json.loads(data.get('post') or '{}')
        except (TypeError, json.JSONDecodeError):
            await self.logger.error('Mattermost received a posted event with an invalid post payload')
            return

        if not post or str(post.get('user_id') or '') == self.bot_account_id:
            return
        channel_id = str(post.get('channel_id') or '')
        if not channel_id:
            return

        try:
            channel = await self._get_channel(channel_id)
            event = await self.event_converter.target2yiri(
                post,
                channel,
                str(data.get('sender_name') or post.get('user_id') or ''),
                self.bot_username,
            )
            callback = self.listeners.get(type(event))
            if callback:
                result = callback(event, self)
                if asyncio.iscoroutine(result):
                    await result
        except Exception as exc:
            await self.logger.error(f'Error handling Mattermost post: {exc}')

    async def _run_websocket_once(self) -> None:
        session = await self._get_session()
        async with session.ws_connect(_websocket_url(self.server_url), heartbeat=30) as websocket:
            await websocket.send_json(
                {
                    'seq': 1,
                    'action': 'authentication_challenge',
                    'data': {'token': self.access_token},
                }
            )
            async for message in websocket:
                if message.type == aiohttp.WSMsgType.TEXT:
                    try:
                        payload = json.loads(message.data)
                    except json.JSONDecodeError:
                        continue
                    if payload.get('event') == 'posted':
                        await self._dispatch_post(payload)
                elif message.type in {aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR}:
                    break

    async def run_async(self):
        self._running = True
        await self._load_bot_identity()
        await self.logger.info(f'Mattermost bot connected: @{self.bot_username} ({self.bot_account_id})')

        retry_delay = 1
        while self._running:
            try:
                await self._run_websocket_once()
                retry_delay = 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._running:
                    await self.logger.error(f'Mattermost WebSocket disconnected: {exc}')
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)

    async def kill(self) -> bool:
        self._running = False
        if self.session and not self.session.closed:
            await self.session.close()
        return True
