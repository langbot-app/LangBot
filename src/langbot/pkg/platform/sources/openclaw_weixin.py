"""OpenClaw WeChat adapter for LangBot.

Uses the OpenClaw WeChat HTTP JSON API (long-poll getUpdates + sendMessage)
to integrate personal WeChat accounts with LangBot.

Reference: https://github.com/epiral/weixin-bot
"""

from __future__ import annotations

import asyncio
import base64
import traceback
import typing

import pydantic
import sqlalchemy

from langbot.libs.openclaw_weixin_api.client import (
    DEFAULT_BASE_URL,
    SESSION_EXPIRED_ERRCODE,
    OpenClawWeixinClient,
)
from langbot.libs.openclaw_weixin_api.types import (
    MessageItem,
    WeixinMessage,
)
from langbot.pkg.entity.persistence import bot as persistence_bot

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message


class OpenClawWeixinMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Converts between LangBot MessageChain and OpenClaw WeChat message items."""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> list[dict]:
        """Convert LangBot MessageChain to a list of OpenClaw message item dicts."""
        items = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                items.append({'type': MessageItem.TEXT, 'text_item': {'text': component.text}})
            elif isinstance(component, platform_message.Image):
                # OpenClaw WeChat only supports text messages without CDN upload.
                # For images, we send a placeholder text with the URL if available.
                if component.url:
                    items.append(
                        {
                            'type': MessageItem.TEXT,
                            'text_item': {'text': f'[Image: {component.url}]'},
                        }
                    )
                elif component.base64:
                    items.append(
                        {
                            'type': MessageItem.TEXT,
                            'text_item': {'text': '[Image]'},
                        }
                    )
            elif isinstance(component, platform_message.File):
                if component.name:
                    items.append(
                        {
                            'type': MessageItem.TEXT,
                            'text_item': {'text': f'[File: {component.name}]'},
                        }
                    )
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        items.extend(await OpenClawWeixinMessageConverter.yiri2target(node.message_chain))
        return items

    @staticmethod
    async def target2yiri(
        msg: WeixinMessage,
    ) -> platform_message.MessageChain:
        """Convert an OpenClaw WeixinMessage to LangBot MessageChain."""
        components: list[platform_message.MessageComponent] = []

        if not msg.item_list:
            return platform_message.MessageChain(components)

        for item in msg.item_list:
            if item.type == MessageItem.TEXT and item.text_item and item.text_item.text:
                text = item.text_item.text

                # Handle quoted messages
                if item.ref_msg:
                    ref_parts = []
                    if item.ref_msg.title:
                        ref_parts.append(item.ref_msg.title)
                    if item.ref_msg.message_item:
                        ref_item = item.ref_msg.message_item
                        if ref_item.text_item and ref_item.text_item.text:
                            ref_parts.append(ref_item.text_item.text)
                    if ref_parts:
                        components.append(
                            platform_message.Quote(
                                sender_id='',
                                origin=platform_message.MessageChain(
                                    [platform_message.Plain(text=' | '.join(ref_parts))]
                                ),
                            )
                        )

                components.append(platform_message.Plain(text=text))

            elif item.type == MessageItem.IMAGE and item.image_item:
                if hasattr(item.image_item, '_downloaded_bytes') and item.image_item._downloaded_bytes:
                    b64 = base64.b64encode(item.image_item._downloaded_bytes).decode('utf-8')
                    components.append(platform_message.Image(base64=f'data:image/jpeg;base64,{b64}'))
                else:
                    components.append(platform_message.Unknown(text='[Image]'))

            elif item.type == MessageItem.VOICE and item.voice_item:
                # Voice with speech-to-text: use the transcribed text
                if item.voice_item.text:
                    components.append(platform_message.Plain(text=item.voice_item.text))
                else:
                    components.append(platform_message.Unknown(text='[Voice]'))

            # TODO: enable after full testing
            # elif item.type == MessageItem.VOICE and item.voice_item:
            #     if item.voice_item.text:
            #         components.append(platform_message.Plain(text=item.voice_item.text))
            #     elif hasattr(item.voice_item, '_downloaded_bytes') and item.voice_item._downloaded_bytes:
            #         b64 = base64.b64encode(item.voice_item._downloaded_bytes).decode('utf-8')
            #         components.append(
            #             platform_message.Voice(
            #                 base64=b64,
            #                 length=item.voice_item.playtime or 0,
            #             )
            #         )
            #     else:
            #         components.append(
            #             platform_message.Voice(
            #                 length=item.voice_item.playtime or 0,
            #             )
            #         )

            elif item.type == MessageItem.FILE and item.file_item:
                components.append(platform_message.Unknown(text=f'[File: {item.file_item.file_name or ""}]'))

            # TODO: enable after full testing
            # elif item.type == MessageItem.FILE and item.file_item:
            #     file_name = item.file_item.file_name or ''
            #     file_size = int(item.file_item.len) if item.file_item.len else 0
            #     if hasattr(item.file_item, '_downloaded_bytes') and item.file_item._downloaded_bytes:
            #         b64 = base64.b64encode(item.file_item._downloaded_bytes).decode('utf-8')
            #         components.append(
            #             platform_message.File(
            #                 name=file_name,
            #                 size=file_size,
            #                 base64=b64,
            #             )
            #         )
            #     else:
            #         components.append(
            #             platform_message.File(
            #                 name=file_name,
            #                 size=file_size,
            #             )
            #         )

            elif item.type == MessageItem.VIDEO and item.video_item:
                components.append(platform_message.Unknown(text='[Video]'))

            # TODO: enable after full testing
            # elif item.type == MessageItem.VIDEO and item.video_item:
            #     if hasattr(item.video_item, '_downloaded_bytes') and item.video_item._downloaded_bytes:
            #         b64 = base64.b64encode(item.video_item._downloaded_bytes).decode('utf-8')
            #         components.append(
            #             platform_message.File(
            #                 name='video.mp4',
            #                 size=item.video_item.video_size or 0,
            #                 base64=b64,
            #             )
            #         )
            #     else:
            #         components.append(
            #             platform_message.File(
            #                 name='video.mp4',
            #                 size=item.video_item.video_size or 0,
            #             )
            #         )

            else:
                components.append(platform_message.Unknown(text='[Unknown message type]'))

        return platform_message.MessageChain(components)


class OpenClawWeixinEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Converts OpenClaw WeChat messages to LangBot events."""

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(msg: WeixinMessage) -> typing.Optional[platform_events.MessageEvent]:
        """Convert an inbound WeixinMessage to a LangBot event."""
        if msg.message_type != WeixinMessage.TYPE_USER:
            return None

        from_user_id = msg.from_user_id or ''
        if not from_user_id:
            return None

        message_chain = await OpenClawWeixinMessageConverter.target2yiri(msg)
        if not message_chain:
            return None

        timestamp = (msg.create_time_ms or 0) / 1000.0

        return platform_events.FriendMessage(
            sender=platform_entities.Friend(
                id=from_user_id,
                nickname=from_user_id,
                remark='',
            ),
            message_chain=message_chain,
            time=timestamp,
            source_platform_object=msg,
        )


class OpenClawWeixinAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """LangBot adapter for OpenClaw WeChat (long-poll based)."""

    name: str = 'openclaw-weixin'

    client: OpenClawWeixinClient = pydantic.Field(exclude=True)

    config: dict

    message_converter: OpenClawWeixinMessageConverter = OpenClawWeixinMessageConverter()
    event_converter: OpenClawWeixinEventConverter = OpenClawWeixinEventConverter()

    # context_token cache: from_user_id -> context_token
    _context_tokens: dict[str, str] = pydantic.PrivateAttr(default_factory=dict)

    _polling: bool = pydantic.PrivateAttr(default=False)
    _poll_task: typing.Optional[asyncio.Task] = pydantic.PrivateAttr(default=None)
    _bot_uuid: typing.Optional[str] = pydantic.PrivateAttr(default=None)

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        client = OpenClawWeixinClient(
            base_url=config.get('base_url', DEFAULT_BASE_URL),
            token=config.get('token', ''),
        )
        super().__init__(
            config=config,
            logger=logger,
            client=client,
            bot_account_id='',
            listeners={},
            name='openclaw-weixin',
        )

    def set_bot_uuid(self, bot_uuid: str):
        """Called by BotManager to provide the bot's UUID for config persistence."""
        self._bot_uuid = bot_uuid

    async def _persist_config(self) -> None:
        """Persist current self.config to the database so token survives restart."""
        if not self._bot_uuid:
            return
        try:
            ap = self.logger.ap
            await ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_bot.Bot)
                .where(persistence_bot.Bot.uuid == self._bot_uuid)
                .values(adapter_config=self.config)
            )
        except Exception as e:
            await self.logger.warning(f'Failed to persist adapter config: {e}')

    async def _do_login(self) -> None:
        """Run the QR code login flow via client.login() and update config."""
        adapter_logger = self.logger

        async def _on_qrcode(qr_base64: str, _qr_url: str):
            await adapter_logger.info(
                f'Please scan the QR code to login WeChat: {_qr_url}',
                images=[platform_message.Image(base64=qr_base64)],
            )

        login_result = await self.client.login(
            on_qrcode=_on_qrcode,
        )

        # client.login() already updates client.token and client.base_url
        self.config['token'] = login_result.token
        self.config['base_url'] = login_result.base_url
        if login_result.account_id:
            self.config['account_id'] = login_result.account_id

        await self.logger.info(f'WeChat login successful! account_id={login_result.account_id}')

        # Persist token to database so it survives restart
        await self._persist_config()

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ):
        """Send a message to a user."""
        context_token = self._context_tokens.get(target_id, '')

        for component in message:
            try:
                if isinstance(component, platform_message.Plain):
                    if component.text:
                        await self.client.send_text(target_id, component.text, context_token)

                elif isinstance(component, platform_message.Image):
                    img_bytes, _ = await component.get_bytes()
                    await self.client.send_image(target_id, img_bytes, context_token)

                elif isinstance(component, platform_message.File):
                    file_bytes = await self._get_component_bytes(component)
                    if file_bytes:
                        await self.client.send_file(target_id, file_bytes, component.name or 'file', context_token)

                elif isinstance(component, platform_message.Voice):
                    voice_bytes = await self._get_component_bytes(component)
                    if voice_bytes:
                        await self.client.send_voice(target_id, voice_bytes, component.length or 0, context_token)

                elif isinstance(component, platform_message.Forward):
                    for node in component.node_list:
                        if node.message_chain:
                            await self.send_message(target_type, target_id, node.message_chain)

            except Exception:
                await self.logger.error(
                    f'Failed to send component {type(component).__name__}: {traceback.format_exc()}'
                )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to a received message."""
        source_msg = message_source.source_platform_object
        if isinstance(source_msg, WeixinMessage):
            target_id = source_msg.from_user_id or ''
            if target_id:
                await self.send_message('friend', target_id, message)

    async def is_muted(self, group_id: int) -> bool:
        return False

    @staticmethod
    async def _get_component_bytes(component: platform_message.MessageComponent) -> typing.Optional[bytes]:
        """Extract raw bytes from a File or Voice component."""
        b64_val = getattr(component, 'base64', None)
        url_val = getattr(component, 'url', None)
        path_val = getattr(component, 'path', None)

        if b64_val:
            return base64.b64decode(b64_val)
        elif url_val and url_val.startswith(('http://', 'https://')):
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url_val) as resp:
                    if resp.status == 200:
                        return await resp.read()
        elif path_val:
            import asyncio

            with open(path_val, 'rb') as f:
                return await asyncio.to_thread(f.read)
        return None

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
        self.listeners.pop(event_type, None)

    async def run_async(self):
        """Start the adapter. If no token is configured, trigger QR code login first."""
        base_url = self.config.get('base_url', DEFAULT_BASE_URL)
        token = self.config.get('token', '')

        await self.logger.info('OpenClaw WeChat adapter starting...')

        # QR code login flow when no token is provided
        if not token:
            await self.logger.info('No token configured, starting QR code login...')
            try:
                await self._do_login()
            except Exception as e:
                await self.logger.error(f'QR code login failed: {e}')
                raise

        # Rebuild client with the (possibly updated) config
        self.client = OpenClawWeixinClient(
            base_url=self.config.get('base_url', base_url),
            token=self.config.get('token', token),
        )
        self.bot_account_id = self.config.get('account_id', 'openclaw-weixin')
        self._polling = True

        # Start the long-poll loop
        self._poll_task = asyncio.create_task(self._poll_loop())
        await self.logger.info('OpenClaw WeChat adapter running')

        try:
            await self._poll_task
        except asyncio.CancelledError:
            pass

    async def _poll_loop(self):
        """Long-poll loop: call getUpdates continuously.

        Error handling follows the weixin-bot SDK pattern:
        - Exponential backoff (1s -> 10s max) on failures
        - Session expired (errcode -14) triggers automatic re-login
        """
        get_updates_buf = ''
        poll_timeout = float(self.config.get('poll_timeout', 35))

        backoff_delay = 1.0
        max_backoff = 10.0

        while self._polling:
            try:
                resp = await self.client.get_updates(
                    get_updates_buf=get_updates_buf,
                    timeout=poll_timeout + 5,
                )

                if resp.longpolling_timeout_ms and resp.longpolling_timeout_ms > 0:
                    poll_timeout = resp.longpolling_timeout_ms / 1000.0

                is_api_error = (resp.ret is not None and resp.ret != 0) or (
                    resp.errcode is not None and resp.errcode != 0
                )
                if is_api_error:
                    is_session_expired = resp.errcode == SESSION_EXPIRED_ERRCODE or resp.ret == SESSION_EXPIRED_ERRCODE

                    if is_session_expired:
                        await self.logger.error('OpenClaw WeChat session expired, attempting re-login...')
                        try:
                            await self._do_login()
                            # Rebuild client with new credentials
                            self.client = OpenClawWeixinClient(
                                base_url=self.config.get('base_url', DEFAULT_BASE_URL),
                                token=self.config.get('token', ''),
                            )
                            self._context_tokens.clear()
                            get_updates_buf = ''
                            backoff_delay = 1.0
                            continue
                        except Exception:
                            await self.logger.error(f'Re-login failed: {traceback.format_exc()}')
                            break

                    await self.logger.error(
                        f'OpenClaw getUpdates failed: ret={resp.ret} errcode={resp.errcode} errmsg={resp.errmsg}'
                    )
                    await asyncio.sleep(backoff_delay)
                    backoff_delay = min(backoff_delay * 2, max_backoff)
                    continue

                backoff_delay = 1.0

                if resp.get_updates_buf:
                    get_updates_buf = resp.get_updates_buf

                for msg in resp.msgs:
                    try:
                        await self._handle_inbound_message(msg)
                    except Exception:
                        await self.logger.error(f'Error handling message: {traceback.format_exc()}')

            except asyncio.CancelledError:
                break
            except Exception:
                await self.logger.error(f'OpenClaw poll error: {traceback.format_exc()}')
                await asyncio.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 2, max_backoff)

    async def _handle_inbound_message(self, msg: WeixinMessage):
        """Process a single inbound message from getUpdates."""
        if msg.context_token and msg.from_user_id:
            self._context_tokens[msg.from_user_id] = msg.context_token

        # Download CDN media (files, images) before converting to LangBot events
        await self._download_media_items(msg)

        event = await OpenClawWeixinEventConverter.target2yiri(msg)
        if event is None:
            return

        if type(event) in self.listeners:
            await self.listeners[type(event)](event, self)

    async def _download_media_items(self, msg: WeixinMessage):
        """Download CDN media for image items in the message."""
        if not msg.item_list:
            return

        for item in msg.item_list:
            try:
                if item.type == MessageItem.IMAGE and item.image_item:
                    if (
                        item.image_item.media
                        and item.image_item.media.encrypt_query_param
                        and item.image_item.media.aes_key
                    ):
                        img_bytes = await self.client.download_media(item.image_item.media)
                        item.image_item._downloaded_bytes = img_bytes

                # TODO: enable after full testing
                # elif item.type == MessageItem.FILE and item.file_item and item.file_item.media:
                #     if item.file_item.media.encrypt_query_param and item.file_item.media.aes_key:
                #         file_bytes = await self.client.download_media(item.file_item.media)
                #         item.file_item._downloaded_bytes = file_bytes
                #
                # elif item.type == MessageItem.VOICE and item.voice_item and item.voice_item.media:
                #     if item.voice_item.media.encrypt_query_param and item.voice_item.media.aes_key:
                #         voice_bytes = await self.client.download_media(item.voice_item.media)
                #         item.voice_item._downloaded_bytes = voice_bytes
                #
                # elif item.type == MessageItem.VIDEO and item.video_item and item.video_item.media:
                #     if item.video_item.media.encrypt_query_param and item.video_item.media.aes_key:
                #         video_bytes = await self.client.download_media(item.video_item.media)
                #         item.video_item._downloaded_bytes = video_bytes

            except Exception:
                await self.logger.warning(f'Failed to download CDN media: {traceback.format_exc()}')

    async def kill(self) -> bool:
        """Stop the adapter."""
        self._polling = False
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await self.client.close()
        await self.logger.info('OpenClaw WeChat adapter stopped')
        return True
