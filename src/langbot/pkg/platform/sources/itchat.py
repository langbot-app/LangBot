"""itchat-uos adapter for LangBot.

Uses the itchat-uos WeChat Web library to integrate personal WeChat accounts
with LangBot via QR code login.

Reference: https://github.com/littlecodersh/ItChat
UOS fork: https://github.com/why2lyj/ItChat-uos
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import threading
import traceback
import typing

from itchat.content import TEXT, PICTURE, RECORDING, VIDEO, SHARING

import pydantic

from itchat.core import Core as ItchatCore

try:
    import queue
except ImportError:
    import Queue as queue

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot.pkg.platform.logger import EventLogger


class ItchatMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Converts between LangBot MessageChain and itchat message dicts."""

    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> list[dict]:
        """LangBot MessageChain -> list of itchat-sendable items.

        Each item is a dict with 'type' and the relevant content field.
        The adapter's send_message() will call itchat.send() accordingly.
        """
        items: list[dict] = []
        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                if component.text:
                    items.append({'type': 'text', 'content': component.text})

            elif isinstance(component, platform_message.Image):
                if component.base64:
                    items.append({'type': 'image', 'base64': component.base64})
                elif component.url:
                    items.append({'type': 'image', 'url': component.url})

            elif isinstance(component, platform_message.Voice):
                if component.base64:
                    items.append({'type': 'voice', 'base64': component.base64})
                elif component.url:
                    items.append({'type': 'voice', 'url': component.url})

            elif isinstance(component, platform_message.File):
                if component.base64:
                    items.append({'type': 'file', 'base64': component.base64, 'name': component.name or 'file'})
                elif component.url:
                    items.append({'type': 'file', 'url': component.url, 'name': component.name or 'file'})

            elif isinstance(component, platform_message.At):
                items.append({'type': 'text', 'content': f'@{component.target} '})

            elif isinstance(component, platform_message.AtAll):
                items.append({'type': 'text', 'content': '@所有人 '})

            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    if node.message_chain:
                        items.extend(await ItchatMessageConverter.yiri2target(node.message_chain))

            elif isinstance(component, platform_message.Unknown):
                pass  # skip unknown outbound

        return items

    @staticmethod
    def target2yiri(msg: dict) -> platform_message.MessageChain:
        """Convert an itchat msg dict to a LangBot MessageChain."""
        components: list[platform_message.MessageComponent] = []
        msg_type = msg.get('Type', '')

        if msg_type == 'Text':
            text = msg.get('Text', '')
            if text:
                components.append(platform_message.Plain(text=text))

        elif msg_type == 'Picture':
            try:
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, msg.get('FileName', 'image.jpg'))
                msg.download(file_path)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        img_bytes = f.read()
                    b64 = base64.b64encode(img_bytes).decode('utf-8')
                    components.append(platform_message.Image(base64=f'data:image/jpeg;base64,{b64}'))
                    os.remove(file_path)
                else:
                    components.append(platform_message.Unknown(text='[Image download failed]'))
            except Exception:
                components.append(platform_message.Unknown(text='[Image download failed]'))

        elif msg_type == 'Recording':
            try:
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, msg.get('FileName', 'voice.mp3'))
                msg.download(file_path)
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        voice_bytes = f.read()
                    b64 = base64.b64encode(voice_bytes).decode('utf-8')
                    components.append(platform_message.Voice(base64=b64))
                    os.remove(file_path)
                else:
                    components.append(platform_message.Unknown(text='[Voice download failed]'))
            except Exception:
                components.append(platform_message.Unknown(text='[Voice download failed]'))

        elif msg_type == 'Sharing':
            text = msg.get('Text', '')
            url = msg.get('Url', '')
            content = text
            if url and url not in text:
                content = f'{text}\n{url}' if text else url
            if content:
                components.append(platform_message.Plain(text=content))

        elif msg_type == 'Video':
            components.append(platform_message.Unknown(text='[Video]'))

        elif msg_type == 'Map':
            components.append(platform_message.Unknown(text='[Location]'))

        elif msg_type == 'Card':
            components.append(platform_message.Unknown(text='[Contact Card]'))

        elif msg_type == 'Note':
            text = msg.get('Text', '')
            if text:
                components.append(platform_message.Unknown(text=f'[Note: {text}]'))

        else:
            text = msg.get('Text', '')
            if text:
                components.append(platform_message.Plain(text=text))
            else:
                components.append(platform_message.Unknown(text=f'[Unsupported message type: {msg_type}]'))

        return platform_message.MessageChain(components)


class ItchatEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Converts itchat msg dicts to LangBot events."""

    def __init__(self, adapter_ref: typing.Callable[[], typing.Any]):
        """adapter_ref is a callable returning the ItchatAdapter instance."""
        self._get_adapter = adapter_ref

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> dict:
        return event.source_platform_object

    def target2yiri(self, msg: dict) -> typing.Optional[platform_events.MessageEvent]:
        """Convert itchat msg to FriendMessage or GroupMessage."""
        from_user = msg.get('FromUserName', '')
        if not from_user:
            return None

        adapter = self._get_adapter()
        bot_account_id = adapter.bot_account_id
        bot_nickname = adapter._bot_nickname

        message_chain = ItchatMessageConverter.target2yiri(msg)
        if not message_chain:
            return None

        # Determine if this is a group message
        # itchat uses '@@' prefix for chatroom IDs (not '@chatroom' suffix)
        is_group = '@@' in from_user
        timestamp = msg.get('CreateTime', 0)

        if is_group:
            # Actual sender within the group
            actual_user = msg.get('ActualUserName', '')
            actual_nick = msg.get('ActualNickName', '')
            if not actual_nick:
                actual_nick = actual_user

            # Prepend @bot if the bot was mentioned
            # itchat uses 'IsAt' (capital I, capital A) in produce_group_chat
            if msg.get('IsAt', False):
                # Strip @bot_nickname from the text content to avoid LLM confusion
                if bot_nickname:
                    at_pattern = '@' + bot_nickname + (' ' if ' ' in msg.get('Content', '') else ' ')
                    for component in message_chain:
                        if isinstance(component, platform_message.Plain):
                            if component.text.startswith(at_pattern):
                                component.text = component.text[len(at_pattern) :]
                            elif at_pattern in component.text:
                                component.text = component.text.replace(at_pattern, '')
                            break
                message_chain = platform_message.MessageChain(
                    [platform_message.At(target=bot_account_id)] + list(message_chain)
                )

            # Try to get group display name
            group_obj = msg.get('User', {})
            group_name = ''
            if hasattr(group_obj, 'NickName'):
                group_name = group_obj.NickName
            elif isinstance(group_obj, dict):
                group_name = group_obj.get('NickName', '')

            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=actual_nick or actual_user,  # use nickname for @ mention
                    member_name=actual_nick or actual_user,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=from_user,
                        name=group_name or from_user,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=timestamp,
                source_platform_object=msg,
            )
        else:
            # Private / friend message
            sender_nick = ''
            user_obj = msg.get('User', {})
            if hasattr(user_obj, 'NickName'):
                sender_nick = user_obj.NickName
            elif isinstance(user_obj, dict):
                sender_nick = user_obj.get('NickName', '')

            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=from_user,
                    nickname=sender_nick or from_user,
                    remark='',
                ),
                message_chain=message_chain,
                time=timestamp,
                source_platform_object=msg,
            )


class ItchatAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """LangBot adapter for itchat-uos (WeChat Web)."""

    name: str = 'itchat'

    config: dict
    logger: EventLogger

    message_converter: ItchatMessageConverter
    event_converter: ItchatEventConverter

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    _loop: typing.Optional[asyncio.AbstractEventLoop] = pydantic.PrivateAttr(default=None)
    _logged_in: typing.Optional[threading.Event] = pydantic.PrivateAttr(default=None)
    _itchat_thread: typing.Optional[threading.Thread] = pydantic.PrivateAttr(default=None)
    _core: typing.Optional[ItchatCore] = pydantic.PrivateAttr(default=None)
    _bot_nickname: str = pydantic.PrivateAttr(default='')
    _bot_uuid: typing.Optional[str] = pydantic.PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        message_converter = ItchatMessageConverter()
        # Event converter needs a reference to self for bot_account_id + nickname
        event_converter = ItchatEventConverter(adapter_ref=lambda: self)

        super().__init__(
            config=config,
            logger=logger,
            message_converter=message_converter,
            event_converter=event_converter,
            listeners={},
            bot_account_id='',
        )

        # Initialize private attributes (can't be class-level defaults due to pickle)
        self._loop = None
        self._logged_in = threading.Event()
        self._itchat_thread = None
        self._core = ItchatCore()

    def _on_login(self):
        """Called by itchat after successful QR code login."""
        try:
            # Refresh contacts
            self._core.get_friends(update=True)
            self._core.get_chatrooms(update=True)

            # Get bot's own WeChat info from loginInfo['User']
            user_info = self._core.loginInfo.get('User', {})
            nick_name = (
                getattr(user_info, 'NickName', '') or user_info.get('NickName', '')
                if isinstance(user_info, dict)
                else ''
            )
            user_name = (
                getattr(user_info, 'UserName', '') or user_info.get('UserName', '')
                if isinstance(user_info, dict)
                else ''
            )

            # bot_account_id: config override or auto-detected wxid
            # Used by AtBotRule for matching At.target
            configured_id = self.config.get('account_id', '').strip()
            self.bot_account_id = configured_id or user_name or nick_name or 'itchat-bot'
            # _bot_nickname: config override or auto-detected nickname
            configured_nick = self.config.get('nickname', '').strip()
            self._bot_nickname = configured_nick or nick_name

            # Log available groups
            chatrooms = self._core.search_chatrooms()
            group_names = []
            for c in chatrooms:
                name = getattr(c, 'NickName', '') or c.get('NickName', '') if isinstance(c, dict) else str(c)
                if name:
                    group_names.append(name)

            if group_names:
                self._log_sync(
                    f'itchat login as {nick_name} ({user_name}) | Groups ({len(group_names)}): {", ".join(group_names[:10])}{"..." if len(group_names) > 10 else ""}'
                )
            else:
                self._log_sync(f'itchat login as {nick_name} ({user_name}) | No groups found')
        except Exception as e:
            self.bot_account_id = f'WeChat Bot (Error: {e})'
        finally:
            self._logged_in.set()

    def _log_sync(self, msg: str, level: str = 'info'):
        """Thread-safe logging from itchat's sync thread."""
        try:
            if self._loop and not self._loop.is_closed():
                log_fn = getattr(self.logger, level)
                asyncio.run_coroutine_threadsafe(log_fn(msg), self._loop)
        except Exception:
            pass

    def _drain_msglist(self):
        """Clear all stale messages from the msgList queue.

        itchat's load_login_status fetches old messages via get_msg() and
        pushes them into msgList. We drain them to avoid replaying history.
        """
        try:
            q = self._core.msgList
            while True:
                q.get_nowait()
        except queue.Empty:
            pass

    def _on_qr_callback(self, **kwargs):
        """Called by itchat when QR code is generated or status changes.

        Args:
            uuid: QR code uuid
            status: '200' = logged in, '201' = confirmed on phone, '408' = timeout
            qrcode: raw bytes of the QR code PNG image
        """
        status = kwargs.get('status', '')
        qr_bytes = kwargs.get('qrcode', b'')

        if status == '200':
            # Login success, no need to show QR
            return

        # Only show QR on new QR generation (status='0') to avoid spamming
        if not qr_bytes or status != '0':
            return

        try:
            b64 = base64.b64encode(qr_bytes).decode('utf-8')
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.logger.info(
                        'Please scan the QR code to login WeChat:',
                        images=[platform_message.Image(base64=f'data:image/png;base64,{b64}')],
                    ),
                    self._loop,
                )
        except Exception:
            pass

    def _on_exit(self):
        """Called by itchat on exit."""
        self._log_sync('itchat session exited')

    def _register_itchat_handlers(self):
        """Register itchat message decorators by re-registering handlers."""

        @self._core.msg_register([TEXT])
        def _on_text(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([TEXT], isGroupChat=True)
        def _on_group_text(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([PICTURE])
        def _on_picture(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([PICTURE], isGroupChat=True)
        def _on_group_picture(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([RECORDING])
        def _on_recording(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([RECORDING], isGroupChat=True)
        def _on_group_recording(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([SHARING])
        def _on_sharing(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([SHARING], isGroupChat=True)
        def _on_group_sharing(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([VIDEO])
        def _on_video(msg):
            self._dispatch_itchat_message(msg)

        @self._core.msg_register([VIDEO], isGroupChat=True)
        def _on_group_video(msg):
            self._dispatch_itchat_message(msg)

    def _dispatch_itchat_message(self, msg: dict):
        """Bridge itchat callback (sync, in itchat thread) to async listener."""
        try:
            event = self.event_converter.target2yiri(msg)
            if event is None:
                return

            event_type = type(event)
            if event_type in self.listeners and self._loop:
                callback = self.listeners[event_type]
                asyncio.run_coroutine_threadsafe(
                    callback(event, self),
                    self._loop,
                )
        except Exception:
            self.logger.error(f'Error dispatching itchat message: {traceback.format_exc()}')

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ):
        """Send a message to a user or group via itchat."""
        items = await self.message_converter.yiri2target(message)
        loop = asyncio.get_event_loop()

        # Merge consecutive text items to avoid splitting messages
        merged = []
        for item in items:
            if item['type'] == 'text' and merged and merged[-1]['type'] == 'text':
                merged[-1]['content'] += item['content']
            else:
                merged.append(item)

        for item in merged:
            try:
                if item['type'] == 'text':
                    await loop.run_in_executor(None, self._core.send, item['content'], target_id)
                elif item['type'] == 'image':
                    # Save to temp file then send
                    temp_path = self._save_to_temp(item, 'image')
                    if temp_path:
                        await loop.run_in_executor(None, self._core.send, f'@img@{temp_path}', target_id)
                        self._cleanup_temp(temp_path)
                elif item['type'] == 'voice':
                    temp_path = self._save_to_temp(item, 'voice')
                    if temp_path:
                        await loop.run_in_executor(None, self._core.send, f'@fil@{temp_path}', target_id)
                        self._cleanup_temp(temp_path)
                elif item['type'] == 'file':
                    temp_path = self._save_to_temp(item, 'file')
                    if temp_path:
                        await loop.run_in_executor(None, self._core.send, f'@fil@{temp_path}', target_id)
                        self._cleanup_temp(temp_path)
            except Exception:
                self.logger.error(f'Failed to send itchat message: {traceback.format_exc()}')

    def _save_to_temp(self, item: dict, prefix: str) -> typing.Optional[str]:
        """Save base64 or URL data to a temp file and return the path."""
        try:
            if 'base64' in item:
                b64_data = item['base64']
                # Strip data URI prefix if present
                if ',' in b64_data:
                    b64_data = b64_data.split(',', 1)[1]
                file_bytes = base64.b64decode(b64_data)
                suffix = '.jpg' if prefix == 'image' else ('.mp3' if prefix == 'voice' else '.bin')
                fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=f'itchat_{prefix}_')
                with os.fdopen(fd, 'wb') as f:
                    f.write(file_bytes)
                return temp_path
            elif 'url' in item:
                import requests

                resp = requests.get(item['url'], timeout=30)
                if resp.status_code == 200:
                    suffix = '.jpg' if prefix == 'image' else ('.mp3' if prefix == 'voice' else '.bin')
                    fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=f'itchat_{prefix}_')
                    with os.fdopen(fd, 'wb') as f:
                        f.write(resp.content)
                    return temp_path
        except Exception:
            self.logger.error(f'Failed to save temp file: {traceback.format_exc()}')
        return None

    def _cleanup_temp(self, path: str):
        """Remove a temp file."""
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to a received message."""
        source_msg = message_source.source_platform_object
        if not source_msg:
            return

        # For group messages, reply to the group; for private, reply to the sender
        from_user = source_msg.get('FromUserName', '')
        if not from_user:
            return

        await self.send_message('friend', from_user, message)

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
        self.listeners.pop(event_type, None)

    async def run_async(self):
        """Start the itchat adapter.

        If a cached session file (itchat.pkl) exists from a previous QR login,
        itchat will reuse it without requiring a new QR scan.
        """
        self._loop = asyncio.get_running_loop()

        await self.logger.info('itchat adapter starting...')

        # Register itchat message handlers BEFORE calling itchat.auto_login()
        self._register_itchat_handlers()

        # Run itchat in a daemon thread (it blocks)
        def _run_itchat():
            try:
                # Use hotReload to reuse the cached session from QR login
                # If no cache exists, fail fast instead of triggering QR login
                result = self._core.load_login_status(
                    'itchat.pkl', loginCallback=self._on_login, exitCallback=self._on_exit
                )
                if result['BaseResponse']['Ret'] != 0:
                    self.logger.error(
                        'No cached WeChat session found. Please scan the QR code in the bot config page first.'
                    )
                    self._logged_in.set()
                    return

                # Session loaded, start message loop
                self._log_sync('WeChat session loaded from cache')

                # Clear stale messages that itchat fetched during hot-reload
                self._drain_msglist()

                self._core.run(blockThread=True)
            except Exception as e:
                self._log_sync(f'itchat run error: {e}', 'error')
                self._logged_in.set()

        self._itchat_thread = threading.Thread(target=_run_itchat, daemon=True, name='itchat-thread')
        self._itchat_thread.start()

        # Wait for login to complete (with timeout)
        await asyncio.get_event_loop().run_in_executor(None, lambda: self._logged_in.wait(timeout=300))

        if not self._logged_in.is_set():
            raise RuntimeError('itchat login timed out (300s)')

        await self.logger.info(f'itchat adapter running, bot: {self.bot_account_id}')

        # Keep the adapter alive
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            pass

    async def kill(self) -> bool:
        """Stop the itchat adapter."""
        try:
            self._core.alive = False
            self._core.isLogging = False
        except Exception:
            pass
        await self.logger.info('itchat adapter stopped')
        return True
