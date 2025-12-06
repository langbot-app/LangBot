from __future__ import annotations

import typing
import asyncio
import json
import base64
import zlib
import traceback
import time

import aiohttp
import websockets
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class KookMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Convert between LangBot MessageChain and KOOK message format"""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> tuple[str, int]:
        """
        Convert LangBot MessageChain to KOOK message format

        Returns:
            tuple: (content, message_type)
                - content: message content string
                - message_type: 1=text, 2=image, 4=file, 9=KMarkdown
        """
        content_parts = []
        message_type = 1  # Default to text

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                content_parts.append(component.text)
            elif isinstance(component, platform_message.At):
                # KOOK mention format: (met)user_id(met)
                if component.target:
                    content_parts.append(f'(met){component.target}(met)')
            elif isinstance(component, platform_message.AtAll):
                # KOOK @all format: (met)all(met)
                content_parts.append('(met)all(met)')
            elif isinstance(component, platform_message.Image):
                # For images, we need to upload first via KOOK's asset API
                # For now, we'll send the image URL if available
                if component.url:
                    content_parts.append(component.url)
                    message_type = 2  # Image message type
            elif isinstance(component, platform_message.Forward):
                # Handle forward messages by concatenating content
                for node in component.node_list:
                    forward_content, _ = await KookMessageConverter.yiri2target(node.message_chain)
                    content_parts.append(forward_content)
            # Ignore Source and other components

        content = ''.join(content_parts)
        return content, message_type

    @staticmethod
    async def target2yiri(kook_message: dict, bot_account_id: str = '') -> platform_message.MessageChain:
        """
        Convert KOOK message format to LangBot MessageChain

        Args:
            kook_message: KOOK message event data dict
            bot_account_id: Bot's account ID for handling role mentions
        """
        components = []

        msg_type = kook_message.get('type', 1)
        content = kook_message.get('content', '')
        extra = kook_message.get('extra', {})

        # Handle mentions
        mentions = extra.get('mention', [])
        mention_all = extra.get('mention_all', False)
        mention_roles = extra.get('mention_roles', [])

        if mention_all:
            components.append(platform_message.AtAll())

        for mention_id in mentions:
            components.append(platform_message.At(target=str(mention_id)))

        # Handle role mentions (when bot is mentioned via role)
        # In KOOK, when a role that the bot has is mentioned, we receive it as a role mention
        # We need to convert this to an At with the bot's account ID for the pipeline to recognize it
        if mention_roles and bot_account_id:
            # Add an At component with the bot's account ID when any role is mentioned
            # This is because KOOK bots are often assigned roles and @role mentions should trigger responses
            components.append(platform_message.At(target=bot_account_id))

        # Strip mention patterns from content
        # Remove user mention patterns: (met)USER_ID(met)
        for mention_id in mentions:
            content = content.replace(f'(met){mention_id}(met)', '')

        # Remove @all pattern
        if mention_all:
            content = content.replace('(met)all(met)', '')

        # Remove role mention patterns: (rol)ROLE_ID(rol)
        for role_id in mention_roles:
            content = content.replace(f'(rol){role_id}(rol)', '')

        # Clean up extra whitespace
        content = content.strip()

        # Handle different message types
        if msg_type == 1:  # Text message
            if content:
                components.append(platform_message.Plain(text=content))
        elif msg_type == 2:  # Image message
            # Image content is typically a URL
            if content:
                # Download image and convert to base64
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(content) as response:
                            if response.status == 200:
                                image_bytes = await response.read()
                                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                                # Detect image format
                                content_type = response.headers.get('Content-Type', 'image/png')
                                components.append(
                                    platform_message.Image(base64=f'data:{content_type};base64,{image_base64}')
                                )
                except Exception:
                    # If download fails, just add as plain text
                    components.append(platform_message.Plain(text=f'[Image: {content}]'))
        elif msg_type == 4:  # File message
            # For file messages, content is typically the file URL
            attachments = extra.get('attachments', {})
            file_name = attachments.get('name', 'file')
            components.append(platform_message.File(url=content, name=file_name))
        elif msg_type == 8:  # Audio message
            # For audio messages, content is typically the audio URL
            attachments = extra.get('attachments', {})
            components.append(platform_message.Voice(url=content))
        elif msg_type == 9:  # KMarkdown message
            # Note: content is already stripped of mention patterns above
            if content:
                components.append(platform_message.Plain(text=content))
        elif msg_type == 10:  # Card message
            # Card messages are complex, for now just indicate it's a card
            components.append(platform_message.Plain(text='[Card Message]'))
        else:
            # Other message types, just use content as plain text
            if content:
                components.append(platform_message.Plain(text=content))

        return platform_message.MessageChain(components)


class KookEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Convert between LangBot events and KOOK events"""

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        """Convert LangBot event to KOOK event (not implemented)"""
        pass

    @staticmethod
    async def target2yiri(kook_event: dict, bot_account_id: str = '') -> platform_events.MessageEvent:
        """
        Convert KOOK event to LangBot MessageEvent

        Args:
            kook_event: KOOK event data dict containing channel_type, type, etc.
            bot_account_id: Bot's account ID for handling role mentions

        Returns:
            FriendMessage or GroupMessage depending on channel_type
        """
        channel_type = kook_event.get('channel_type')
        author_id = kook_event.get('author_id')
        target_id = kook_event.get('target_id')
        msg_timestamp = kook_event.get('msg_timestamp', int(time.time() * 1000))
        extra = kook_event.get('extra', {})

        # Convert message to MessageChain
        message_chain = await KookMessageConverter.target2yiri(kook_event, bot_account_id)

        # Convert timestamp from milliseconds to seconds
        event_time = msg_timestamp / 1000.0

        if channel_type == 'PERSON':
            # Direct/Private message
            author = extra.get('author', {})
            author_name = author.get('nickname', author.get('username', str(author_id)))

            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=str(author_id),
                    nickname=author_name,
                    remark=str(author_id),
                ),
                message_chain=message_chain,
                time=event_time,
                source_platform_object=kook_event,
            )
        elif channel_type == 'GROUP':
            # Guild/Server channel message
            author = extra.get('author', {})
            author_name = author.get('nickname', author.get('username', str(author_id)))

            # guild_id = extra.get('guild_id', '')
            channel_name = extra.get('channel_name', str(target_id))

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=str(author_id),
                    member_name=author_name,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=str(target_id),  # Channel ID
                        name=channel_name,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=event_time,
                source_platform_object=kook_event,
            )
        else:
            # Fallback to FriendMessage for unknown channel types
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=str(author_id),
                    nickname=str(author_id),
                    remark=str(author_id),
                ),
                message_chain=message_chain,
                time=event_time,
                source_platform_object=kook_event,
            )


class KookAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """KOOK platform adapter for LangBot"""

    config: dict
    message_converter: KookMessageConverter = KookMessageConverter()
    event_converter: KookEventConverter = KookEventConverter()
    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    # WebSocket connection
    ws: typing.Optional[websockets.WebSocketClientProtocol] = pydantic.Field(exclude=True, default=None)
    ws_task: typing.Optional[asyncio.Task] = pydantic.Field(exclude=True, default=None)
    heartbeat_task: typing.Optional[asyncio.Task] = pydantic.Field(exclude=True, default=None)
    running: bool = pydantic.Field(exclude=True, default=False)

    # Connection state
    session_id: str = pydantic.Field(exclude=True, default='')
    current_sn: int = pydantic.Field(exclude=True, default=0)
    gateway_url: str = pydantic.Field(exclude=True, default='')

    # HTTP session
    http_session: typing.Optional[aiohttp.ClientSession] = pydantic.Field(exclude=True, default=None)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        # Debug: Track init
        with open('/tmp/kook_adapter_init.txt', 'w') as f:
            f.write(f'KOOK adapter __init__ called at {time.time()}\n')

        # Validate required config
        if 'token' not in config:
            raise Exception('KOOK adapter requires "token" in config')

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id='',  # Will be set after connection
            listeners={},
            **kwargs,
        )

    async def _get_gateway_url(self) -> str:
        """Get WebSocket gateway URL from KOOK API"""
        base_url = 'https://www.kookapp.cn/api/v3/gateway/index'

        # Always use compression for better performance
        params = {'compress': 1}

        headers = {
            'Authorization': f'Bot {self.config["token"]}',
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == 0:
                        gateway_url = data['data']['url']
                        return gateway_url
                    else:
                        raise Exception(f'Failed to get gateway URL: {data.get("message")}')
                else:
                    raise Exception(f'Failed to get gateway URL: HTTP {response.status}')

    async def _get_bot_user_info(self) -> dict:
        """Get bot's own user information from KOOK API"""
        base_url = 'https://www.kookapp.cn/api/v3/user/me'

        headers = {
            'Authorization': f'Bot {self.config["token"]}',
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == 0:
                        user_info = data['data']
                        return user_info
                    else:
                        raise Exception(f'Failed to get bot user info: {data.get("message")}')
                else:
                    raise Exception(f'Failed to get bot user info: HTTP {response.status}')

    async def _handle_hello(self, data: dict):
        """Handle HELLO signal (signal 1)"""
        session_id = data.get('session_id', '')
        self.session_id = session_id
        await self.logger.info(f'KOOK WebSocket HELLO received, session_id: {session_id}')

    async def _handle_event(self, data: dict, sn: int):
        """Handle EVENT signal (signal 0)"""
        self.current_sn = max(self.current_sn, sn)

        # Check if this is a message event
        event_type = data.get('type')
        channel_type = data.get('channel_type')
        author_id = data.get('author_id')

        # Ignore messages from bot itself to prevent infinite loops
        if self.bot_account_id and str(author_id) == self.bot_account_id:
            return

        # Only process text messages (type 1, 2, 4, 8, 9, 10) in GROUP or PERSON channels
        if event_type in [1, 2, 4, 8, 9, 10] and channel_type in ['GROUP', 'PERSON']:
            try:
                # Convert to LangBot event
                lb_event = await self.event_converter.target2yiri(data, self.bot_account_id)

                # Call registered listener
                event_class = type(lb_event)
                if event_class in self.listeners:
                    await self.listeners[event_class](lb_event, self)
            except Exception as e:
                await self.logger.error(f'Error handling KOOK event: {e}\n{traceback.format_exc()}')

    async def _handle_pong(self, data: dict):
        """Handle PONG signal (signal 3)"""
        # PONG received, connection is healthy
        pass

    async def _heartbeat_loop(self):
        """Send PING every 30 seconds"""
        try:
            while self.running and self.ws:
                await asyncio.sleep(30)

                if self.ws:
                    try:
                        ping_msg = {
                            's': 2,  # PING signal
                            'sn': self.current_sn,
                        }
                        await self.ws.send(json.dumps(ping_msg))
                    except Exception:
                        # Connection closed or send failed, exit loop
                        break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.logger.error(f'Heartbeat error: {e}')

    async def _websocket_loop(self):
        """Main WebSocket event loop"""
        retry_count = 0
        max_retries = 3

        while self.running and retry_count < max_retries:
            try:
                # Get gateway URL if not already retrieved
                if not self.gateway_url:
                    self.gateway_url = await self._get_gateway_url()

                # Connect to WebSocket
                async with websockets.connect(self.gateway_url) as ws:
                    await self.logger.info(f'Connected to KOOK WebSocket: {self.gateway_url}')
                    self.ws = ws

                    # Start heartbeat
                    self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    # Wait for HELLO within 6 seconds
                    try:
                        hello_msg = await asyncio.wait_for(ws.recv(), timeout=6.0)

                        # Handle compressed messages (same as main message loop)
                        if isinstance(hello_msg, bytes):
                            # Decompress if compressed
                            try:
                                hello_msg = zlib.decompress(hello_msg).decode('utf-8')
                            except Exception:
                                # Not compressed or decompression failed
                                hello_msg = hello_msg.decode('utf-8')

                        hello_data = json.loads(hello_msg)

                        if hello_data.get('s') == 1:  # HELLO signal
                            await self._handle_hello(hello_data['d'])
                        else:
                            raise Exception(f'Expected HELLO signal, got signal {hello_data.get("s")}')
                    except asyncio.TimeoutError:
                        raise Exception('Did not receive HELLO within 6 seconds')

                    # Reset retry count on successful connection
                    retry_count = 0

                    # Main message loop
                    async for message in ws:
                        if isinstance(message, bytes):
                            # Decompress if compressed
                            try:
                                message = zlib.decompress(message).decode('utf-8')
                            except Exception:
                                # Not compressed or decompression failed
                                message = message.decode('utf-8')

                        try:
                            msg_data = json.loads(message)
                            signal = msg_data.get('s')

                            if signal == 0:  # EVENT
                                data = msg_data.get('d', {})
                                sn = msg_data.get('sn', 0)
                                await self._handle_event(data, sn)
                            elif signal == 3:  # PONG
                                await self._handle_pong(msg_data.get('d', {}))
                            elif signal == 5:  # RECONNECT
                                # await self.logger.info('Received RECONNECT signal')
                                break  # Break to reconnect
                            elif signal == 6:  # RESUME ACK
                                # await self.logger.info('Resume successful')
                                pass
                        except json.JSONDecodeError:
                            await self.logger.error(f'Failed to parse message: {message}')
                        except Exception as e:
                            await self.logger.error(f'Error processing message: {e}\n{traceback.format_exc()}')

            except websockets.exceptions.ConnectionClosed:
                await self.logger.warning('KOOK WebSocket connection closed, reconnecting...')
                retry_count += 1
                await asyncio.sleep(2**retry_count)  # Exponential backoff
            except Exception as e:
                await self.logger.error(f'KOOK WebSocket error: {e}\n{traceback.format_exc()}')
                retry_count += 1
                await asyncio.sleep(2**retry_count)
            finally:
                # Stop heartbeat
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                    try:
                        await self.heartbeat_task
                    except asyncio.CancelledError:
                        pass
                self.ws = None

        if retry_count >= max_retries:
            await self.logger.error(f'Failed to connect after {max_retries} retries')

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """Send a message to a channel or user"""
        content, msg_type = await self.message_converter.yiri2target(message)

        # Determine endpoint based on target_type
        if target_type == 'GROUP':
            # Send to channel
            url = 'https://www.kookapp.cn/api/v3/message/create'
            payload = {
                'target_id': target_id,
                'content': content,
                'type': msg_type,
            }
        else:  # PERSON or default
            # Send direct message
            url = 'https://www.kookapp.cn/api/v3/direct-message/create'
            payload = {
                'target_id': target_id,
                'content': content,
                'type': msg_type,
            }

        headers = {
            'Authorization': f'Bot {self.config["token"]}',
            'Content-Type': 'application/json',
        }

        try:
            if not self.http_session:
                self.http_session = aiohttp.ClientSession()

            async with self.http_session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 0:
                        await self.logger.debug(f'Message sent successfully to {target_id}')
                    else:
                        await self.logger.error(f'Failed to send message: {result.get("message")}')
                else:
                    await self.logger.error(f'Failed to send message: HTTP {response.status}')
        except Exception as e:
            await self.logger.error(f'Error sending message: {e}')

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to a message"""
        content, msg_type = await self.message_converter.yiri2target(message)

        kook_event = message_source.source_platform_object
        channel_type = kook_event.get('channel_type')
        target_id = kook_event.get('target_id')
        msg_id = kook_event.get('msg_id')

        # Determine endpoint based on channel_type
        if channel_type == 'GROUP':
            url = 'https://www.kookapp.cn/api/v3/message/create'
            payload = {
                'target_id': target_id,
                'content': content,
                'type': msg_type,
            }
        else:  # PERSON
            url = 'https://www.kookapp.cn/api/v3/direct-message/create'
            # For direct messages, we need the chat_code or target_id
            author_id = kook_event.get('author_id')
            extra = kook_event.get('extra', {})
            chat_code = extra.get('code', '')

            payload = {
                'content': content,
                'type': msg_type,
            }

            if chat_code:
                payload['chat_code'] = chat_code
            else:
                payload['target_id'] = str(author_id)

        # Add quote if requested
        if quote_origin and msg_id:
            payload['quote'] = msg_id

        payload['reply_msg_id'] = msg_id

        headers = {
            'Authorization': f'Bot {self.config["token"]}',
            'Content-Type': 'application/json',
        }

        try:
            if not self.http_session:
                self.http_session = aiohttp.ClientSession()

            async with self.http_session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 0:
                        await self.logger.debug('Reply sent successfully')
                    else:
                        await self.logger.error(f'Failed to send reply: {result.get("message")}')
                else:
                    await self.logger.error(f'Failed to send reply: HTTP {response.status}')
        except Exception as e:
            await self.logger.error(f'Error sending reply: {e}')

    async def is_muted(self, group_id: int) -> bool:
        """Check if bot is muted in a group (not implemented for KOOK)"""
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        """Register an event listener"""
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        """Unregister an event listener"""
        self.listeners.pop(event_type, None)

    async def run_async(self):
        """Start the KOOK adapter"""
        # Debug: Track run_async
        with open('/tmp/kook_adapter_run.txt', 'w') as f:
            f.write(f'KOOK adapter run_async called at {time.time()}\n')

        self.running = True

        try:
            # Create HTTP session
            self.http_session = aiohttp.ClientSession()

            await self.logger.info('Starting KOOK adapter')

            # Get bot's user information and set bot_account_id
            try:
                bot_info = await self._get_bot_user_info()
                self.bot_account_id = str(bot_info.get('id', ''))
            except Exception as e:
                await self.logger.error(f'Failed to get bot user info: {e}')
                # Continue anyway, but bot will process its own messages

            # Start WebSocket connection
            self.ws_task = asyncio.create_task(self._websocket_loop())

            # Keep running
            await self.ws_task
        except Exception as e:
            await self.logger.error(f'KOOK adapter error: {e}\n{traceback.format_exc()}')
        finally:
            self.running = False

    async def kill(self) -> bool:
        """Stop the KOOK adapter"""
        self.running = False

        # Cancel tasks
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass

        if self.ws_task:
            self.ws_task.cancel()
            try:
                await self.ws_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass  # Already closed or error during close

        # Close HTTP session
        if self.http_session:
            await self.http_session.close()

        await self.logger.info('KOOK adapter stopped')
        return True
