from __future__ import annotations
import typing
import re
import asyncio
import traceback

import datetime
import time

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from langbot.libs.qq_official_api.api import (
    QQ_SELECT_ACTION_PREFIX,
    QQOfficialClient,
    build_keyboard_from_form,
    build_keyboard_from_select_field,
    resolve_select_button_action,
)
from langbot.libs.qq_official_api.qqofficialevent import QQOfficialEvent
from ...utils import image
from ..logger import EventLogger


def _is_base64_data(value: str) -> bool:
    """Check if a string contains base64-encoded data rather than a URL."""
    if not value:
        return False
    # data: URI scheme (e.g. data:image/png;base64,xxx)
    if value.startswith('data:'):
        return True
    # Only treat as base64 if it doesn't look like a URL/path and has valid base64 chars
    if value.startswith(('http://', 'https://', '/', './', '../')):
        return False
    # Check if it looks like base64 (only valid chars, reasonable length)
    return bool(re.fullmatch(r'[A-Za-z0-9+/=\s]{20,}', value))


class QQOfficialMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        """将 LangBot 消息链转换为 QQ Official 消息格式列表。"""
        content_list = []
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content_list.append(
                    {
                        'type': 'text',
                        'content': msg.text,
                    }
                )
            elif type(msg) is platform_message.Image:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins (e.g. MimoTTS) store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'image',
                        'url': url,
                        'base64': b64,
                    }
                )
            elif type(msg) is platform_message.Voice:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins (e.g. MimoTTS) store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'voice',
                        'url': url,
                        'base64': b64,
                    }
                )
            elif type(msg) is platform_message.File:
                url = msg.url if hasattr(msg, 'url') and msg.url else None
                b64 = msg.base64 if hasattr(msg, 'base64') and msg.base64 else None
                # Some plugins store base64 data in the url field
                if url and not b64 and _is_base64_data(url):
                    b64 = url
                    url = None
                content_list.append(
                    {
                        'type': 'file',
                        'url': url,
                        'base64': b64,
                        'name': msg.name if hasattr(msg, 'name') else 'file',
                    }
                )

        return content_list

    @staticmethod
    async def target2yiri(message: str, message_id: str, pic_url: str, content_type):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        if pic_url is not None:
            base64_url = await image.get_qq_official_image_base64(pic_url=pic_url, content_type=content_type)
            yiri_msg_list.append(platform_message.Image(base64=base64_url))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)
        return chain


class QQOfficialEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent) -> QQOfficialEvent:
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: QQOfficialEvent):
        """
        QQ官方消息转换为LB对象
        """
        yiri_chain = await QQOfficialMessageConverter.target2yiri(
            message=event.content,
            message_id=event.d_id,
            pic_url=event.attachments,
            content_type=event.content_type,
        )

        if event.t == 'C2C_MESSAGE_CREATE':
            friend = platform_entities.Friend(
                id=event.user_openid,
                nickname=event.t,
                remark='',
            )
            return platform_events.FriendMessage(
                sender=friend,
                message_chain=yiri_chain,
                time=int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp()),
                source_platform_object=event,
            )

        if event.t == 'DIRECT_MESSAGE_CREATE':
            friend = platform_entities.Friend(
                id=event.guild_id,
                nickname=event.t,
                remark='',
            )
            return platform_events.FriendMessage(sender=friend, message_chain=yiri_chain, source_platform_object=event)
        if event.t == 'GROUP_AT_MESSAGE_CREATE':
            yiri_chain.insert(0, platform_message.At(target='justbot'))

            sender = platform_entities.GroupMember(
                id=event.group_openid,
                member_name=event.t,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.group_openid,
                    name='MEMBER',
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            )
            time = int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp())
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=yiri_chain,
                time=time,
                source_platform_object=event,
            )
        if event.t == 'AT_MESSAGE_CREATE':
            yiri_chain.insert(0, platform_message.At(target='justbot'))
            sender = platform_entities.GroupMember(
                id=event.channel_id,
                member_name=event.t,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.channel_id,
                    name='MEMBER',
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            )
            time = int(datetime.datetime.strptime(event.timestamp, '%Y-%m-%dT%H:%M:%S%z').timestamp())
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=yiri_chain,
                time=time,
                source_platform_object=event,
            )


class QQOfficialAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: QQOfficialClient
    config: dict
    bot_account_id: str
    bot_uuid: str = None
    enable_webhook: bool = False
    message_converter: QQOfficialMessageConverter = QQOfficialMessageConverter()
    event_converter: QQOfficialEventConverter = QQOfficialEventConverter()
    ap: typing.Any = None

    def __init__(self, config: dict, logger: EventLogger):
        enable_webhook = config.get('enable-webhook', False)

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
        )

        self.enable_webhook = enable_webhook
        self._ws_task: asyncio.Task = None
        self._stream_ctx: dict = {}
        self._stream_ctx_ts: dict[str, float] = {}
        self._fallback_text: dict[str, str] = {}
        self._fallback_text_ts: dict[str, float] = {}
        # Dify form-action bookkeeping for the human-input button flow.
        # session_key = "<scene>_<id>" where scene is c2c/group/channel and
        #   id is user_openid / group_openid / channel_id.
        # session_key -> {form_data, msg_id, event_id, scene, target_id,
        #                 sender_id, posted_at}
        # Set when we send a markdown+keyboard card and consulted when:
        #   (a) INTERACTION_CREATE fires — we look up the form by
        #       session_key (button's `data` carries the action_id),
        #   (b) the resumed-workflow query needs to find a passive-reply
        #       event_id (INTERACTION_CREATE id, 30-min validity).
        self._pending_forms: dict[str, dict] = {}
        # session_key -> most recent ``INTERACTION_CREATE`` event_id, used
        # as the passive event_id for the resumed query's LLM output.
        self._session_event_ids: dict[str, dict] = {}
        # Per-anchor msg_seq counter. QQ accepts up to 5 passive replies
        # per (msg_id|event_id) within 60 min, but each reuse needs a
        # fresh ``msg_seq`` — re-sending with msg_seq=1 is silently dedup'd.
        self._anchor_msg_seq: dict[str, int] = {}

        # Wire button-click handler so webhook mode catches INTERACTION_CREATE.
        # (ws mode is wired separately via on_event in _run_websocket so the
        # raw payload bypasses get_message's message-only flattening.)
        @self.bot.on_interaction()
        async def _on_interaction(event_data: dict, interaction_id: typing.Optional[str]):
            await self._handle_interaction_create(event_data, interaction_id)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        qq_official_event = await QQOfficialEventConverter.yiri2target(
            message_source,
        )

        # Synthetic event (button-click resume): no inbound platform
        # object → no msg_id. Route via the cached INTERACTION_CREATE
        # event_id (valid 30 min, no quota cost).
        if qq_official_event is None:
            await self._reply_synthetic(message_source, message)
            return

        content_list = await QQOfficialMessageConverter.yiri2target(message)

        # 确定 target_type 和 target_id
        target_type = None
        target_id = None

        if qq_official_event.t == 'C2C_MESSAGE_CREATE':
            target_type = 'c2c'
            target_id = qq_official_event.user_openid
        elif qq_official_event.t == 'GROUP_AT_MESSAGE_CREATE':
            target_type = 'group'
            target_id = qq_official_event.group_openid
        elif qq_official_event.t == 'AT_MESSAGE_CREATE':
            # 频道群聊使用频道 API，暂不支持富媒体
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_group_text_msg(
                        qq_official_event.channel_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
            return
        elif qq_official_event.t == 'DIRECT_MESSAGE_CREATE':
            # 频道私聊使用频道 API，暂不支持富媒体
            for content in content_list:
                if content['type'] == 'text':
                    await self.bot.send_channle_private_text_msg(
                        qq_official_event.guild_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
            return

        # C2C 和群聊：支持文字 + 富媒体
        for content in content_list:
            content_type = content.get('type', 'text')

            if content_type == 'text':
                if target_type == 'c2c':
                    await self.bot.send_private_text_msg(
                        target_id,
                        content['content'],
                        qq_official_event.d_id,
                    )
                elif target_type == 'group':
                    await self.bot.send_group_text_msg(
                        target_id,
                        content['content'],
                        qq_official_event.d_id,
                    )

            elif content_type == 'image':
                file_url = content.get('url')
                file_data = content.get('base64')
                if file_url or file_data:
                    await self.bot.send_image_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        msg_id=qq_official_event.d_id,
                    )

            elif content_type == 'voice':
                file_url = content.get('url')
                file_data = content.get('base64')
                if file_url or file_data:
                    await self.bot.send_voice_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        msg_id=qq_official_event.d_id,
                    )

            elif content_type == 'file':
                file_url = content.get('url')
                file_data = content.get('base64')
                file_name = content.get('name', 'file')
                if file_url or file_data:
                    await self.bot.send_file_msg(
                        target_type,
                        target_id,
                        file_url=file_url,
                        file_data=file_data,
                        file_name=file_name,
                        msg_id=qq_official_event.d_id,
                    )

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: QQOfficialEvent):
            self.bot_account_id = 'justbot'
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in qqofficial callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('DIRECT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('C2C_MESSAGE_CREATE')(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message('GROUP_AT_MESSAGE_CREATE')(on_message)
            self.bot.on_message('AT_MESSAGE_CREATE')(on_message)

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        """处理统一 webhook 请求。

        Args:
            bot_uuid: Bot 的 UUID
            path: 子路径（如果有的话）
            request: Quart Request 对象

        Returns:
            响应数据
        """
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        if not self.enable_webhook:
            await self._run_websocket()
        else:
            # 统一 webhook 模式下，不启动独立的 Quart 应用
            async def keep_alive():
                while True:
                    await asyncio.sleep(1)

            await keep_alive()

    async def _run_websocket(self):
        """以 WebSocket 模式运行网关连接"""
        await self.logger.info('QQ Official adapter starting in WebSocket mode')

        async def on_ready():
            await self.logger.info('QQ Official WebSocket connected and ready')

        async def on_event(event_type: str, event_data: dict):
            # INTERACTION_CREATE is dispatched via bot.on_interaction()
            # (registered in __init__) so we get the top-level ws_event_id
            # — needed as the passive-reply event_id. It never reaches here.
            # 只处理消息事件，忽略 READY/RESUMED 等系统事件
            message_event_types = {
                'C2C_MESSAGE_CREATE',
                'DIRECT_MESSAGE_CREATE',
                'GROUP_AT_MESSAGE_CREATE',
                'AT_MESSAGE_CREATE',
            }
            if event_type not in message_event_types:
                return
            if not isinstance(event_data, dict):
                await self.logger.warning(f'Event data is not dict, skipping: {event_type} -> {type(event_data)}')
                return
            await self.logger.info(f'Processing message event: {event_type}')
            # 构造与 webhook 模式相同的 payload 结构
            payload = {'t': event_type, 'd': event_data}
            message_data = await self.bot.get_message(payload)
            if message_data:
                event = QQOfficialEvent.from_payload(message_data)
                await self.bot._handle_message(event)

        async def on_error(error: Exception):
            await self.logger.error(f'WebSocket error: {error}')
            await self.logger.error(f'QQ Official WebSocket error: {error}')

        self._ws_task = asyncio.create_task(self.bot.connect_gateway_loop(on_event, on_ready, on_error))
        try:
            await self._ws_task
        except asyncio.CancelledError:
            pass

    async def kill(self) -> bool:
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        return True

    # --------------- 流式输出 ---------------

    _STREAM_CTX_TTL = 300  # seconds

    async def _cleanup_stale_streams(self):
        """Remove stream contexts that have not been updated for more than _STREAM_CTX_TTL seconds."""
        now = time.time()
        stale_ids = [mid for mid, ts in self._stream_ctx_ts.items() if now - ts > self._STREAM_CTX_TTL]
        for mid in stale_ids:
            self._stream_ctx.pop(mid, None)
            self._stream_ctx_ts.pop(mid, None)
        stale_fb = [mid for mid, ts in self._fallback_text_ts.items() if now - ts > self._STREAM_CTX_TTL]
        for mid in stale_fb:
            self._fallback_text.pop(mid, None)
            self._fallback_text_ts.pop(mid, None)
        if stale_ids or stale_fb:
            await self.logger.debug(f'Cleaned up {len(stale_ids)} stream contexts, {len(stale_fb)} fallback texts')

    async def is_stream_output_supported(self) -> bool:
        return self.config.get('enable-stream-reply', False)

    @staticmethod
    def _is_form_placeholder_chunk(text: str) -> bool:
        """Return True for invisible placeholder chunks used to carry forms."""

        if not text:
            return False

        cleaned = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '').strip()
        # Some Windows consoles/logs display the zero-width placeholder as
        # mojibake. Treat those variants as the same non-user-facing marker.
        return cleaned in {'', '鈥?', 'â€‹'}

    async def create_message_card(self, message_id: str, event: platform_events.MessageEvent) -> bool:
        source = event.source_platform_object
        # Synthetic events (button-click resume) have no source object —
        # they ride a cached INTERACTION_CREATE event_id, not a streamable
        # msg_id. Skip stream setup; reply_message handles the one-shot
        # send at is_final.
        if source is None:
            return False
        # Streaming API only supports C2C private chat
        if source.t != 'C2C_MESSAGE_CREATE':
            return False

        # The stream endpoint still consumes msg_seq for this inbound msg_id.
        # Keep the passive-reply counter in sync so a follow-up form card uses
        # msg_seq=2 instead of being deduplicated by QQ as another seq=1 send.
        if source.d_id:
            self._anchor_msg_seq[source.d_id] = max(self._anchor_msg_seq.get(source.d_id, 0), 1)

        ctx = {
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

        self._stream_ctx[message_id] = ctx
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
        # Periodically clean up stale stream contexts
        await self._cleanup_stale_streams()

        # Dify human-input pause: when the runner attaches `_form_data` to
        # the final chunk, finalize any in-flight stream session and send
        # a markdown + keyboard message instead. Plain-text content from
        # earlier chunks is already on the stream; we close it cleanly
        # and the buttons land as a separate reply.
        form_data = getattr(bot_message, '_form_data', None) if not isinstance(bot_message, dict) else None
        if is_final:
            _resume = getattr(bot_message, '_resume_from_form', None) if not isinstance(bot_message, dict) else None
            _open_new = getattr(bot_message, '_open_new_card', None) if not isinstance(bot_message, dict) else None
            if self.ap is not None:
                self.ap.logger.info(
                    f'QQ Official reply_message_chunk final: '
                    f'type={type(bot_message).__name__} '
                    f'is_final={is_final} '
                    f'form_data_present={form_data is not None} '
                    f'resume_from_form={_resume} open_new_card={_open_new} '
                    f'content_len={len(getattr(bot_message, "content", "") or "")}'
                )
        if form_data and is_final:
            await self._handle_form_chunk(message_source, message, form_data)
            return

        # 提取纯文本内容（当前 chunk 的文本）
        text_parts = []
        for msg in message:
            if type(msg) is platform_message.Plain:
                text_parts.append(msg.text)
        chunk_text = '\n\n'.join(text_parts)
        if self._is_form_placeholder_chunk(chunk_text):
            await self.logger.debug('QQ Official: skipped invisible form placeholder chunk')
            return

        message_id = (
            bot_message.get('resp_message_id')
            if isinstance(bot_message, dict)
            else getattr(bot_message, 'resp_message_id', None)
        )
        if not message_id or message_id not in self._stream_ctx:
            # 非流式场景（如群聊不支持流式），累积文本后一次性回复
            if chunk_text:
                # Chunks carry the latest full snapshot, not a text delta.
                self._fallback_text[message_id] = chunk_text
                self._fallback_text_ts[message_id] = time.time()
            if is_final:
                full_text = self._fallback_text.pop(message_id, '')
                if full_text:
                    fallback_msg = platform_message.MessageChain([platform_message.Plain(text=full_text)])
                    await self.reply_message(message_source, fallback_msg, quote_origin)
            return

        ctx = self._stream_ctx[message_id]

        # 累积文本
        if chunk_text:
            ctx['accumulated_text'] = chunk_text

        # 未启动会话时，等第一个有内容的 chunk 来建立会话
        if not ctx['session_started']:
            if not ctx['accumulated_text']:
                return
            # 用第一个 chunk 的文本建立会话（不发 "..." 避免污染前缀）
            ctx['session_started'] = True

        # 发送内容 = 全量累积文本
        # QQ API 的 replace 模式不允许修改已下发前缀，所以：
        # - 首次：发送全部文本，建立会话
        # - 后续：只能发送新增部分（append 行为）
        content_to_send = ctx['accumulated_text'][ctx['sent_length'] :]
        if not content_to_send and not is_final:
            return

        input_state = 10 if is_final else 1

        # Rate limiting: skip non-final updates if last update was <0.5s ago
        now = time.time()
        if not is_final and (now - ctx['last_update_ts']) < 0.5:
            return
        ctx['last_update_ts'] = now

        try:
            resp = await self.bot.send_stream_msg(
                user_openid=ctx['user_openid'],
                content=content_to_send,
                event_id=ctx['msg_id'],
                msg_id=ctx['msg_id'],
                msg_seq=ctx['msg_seq'],
                index=ctx['index'],
                stream_msg_id=ctx['stream_msg_id'],
                input_state=input_state,
            )
            if resp and isinstance(resp, dict):
                new_stream_id = resp.get('id')
                if new_stream_id:
                    ctx['stream_msg_id'] = new_stream_id
            ctx['sent_length'] = len(ctx['accumulated_text'])
            ctx['index'] += 1
            await self.logger.debug(
                f'[QQ Official] 流式 chunk 已发送, index={ctx["index"]}, '
                f'sent_len={ctx["sent_length"]}, is_final={is_final}'
            )
        except Exception as e:
            await self.logger.error(f'Failed to send stream message: {e}')

        if is_final:
            self._stream_ctx.pop(message_id, None)

    def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    # ------------------------------------------------------------------
    # Dify human-input button-interaction support
    # ------------------------------------------------------------------

    _PENDING_FORM_TTL = 1800  # 30 min — matches QQ passive-reply window.
    _MAX_REPLIES_PER_ANCHOR = 5  # QQ hard limit per msg_id / event_id.

    def _next_msg_seq(self, anchor: str) -> typing.Optional[int]:
        """Return the next msg_seq for an anchor, or ``None`` if the
        anchor has already been used 5 times (further sends would be
        silently dropped by QQ)."""
        if not anchor:
            return 1
        used = self._anchor_msg_seq.get(anchor, 0)
        if used >= self._MAX_REPLIES_PER_ANCHOR:
            return None
        self._anchor_msg_seq[anchor] = used + 1
        return used + 1

    async def _reply_synthetic(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
    ) -> None:
        """Deliver a reply for a synthetic (button-click-resume) event.

        Synthetic events have ``source_platform_object=None`` and no
        fresh inbound msg_id. The previous INTERACTION_CREATE id we
        cached in :attr:`_session_event_ids` is a valid passive-reply
        anchor (``event_id``) for up to 30 minutes — use it.
        """
        if isinstance(message_source, platform_events.GroupMessage):
            target_type = 'group'
            group = getattr(message_source, 'group', None) or (
                message_source.sender.group if hasattr(message_source.sender, 'group') else None
            )
            target_id = str(group.id) if group else None
        else:
            target_type = 'c2c'
            target_id = str(message_source.sender.id) if message_source.sender else None

        if not target_id:
            await self.logger.warning('QQ Official: synthetic reply has no target_id; dropping')
            return

        session_key = f'{target_type}_{target_id}'
        cached = self._session_event_ids.get(session_key)
        event_id = cached.get('event_id') if cached else None
        if cached and (time.time() - cached.get('posted_at', 0)) > self._PENDING_FORM_TTL:
            event_id = None

        if not event_id:
            await self.logger.warning(
                f'QQ Official: no cached event_id for {session_key}; '
                f'cannot deliver synthetic reply within passive-reply window'
            )
            return

        content_list = await QQOfficialMessageConverter.yiri2target(message)
        text_parts = [c['content'] for c in content_list if c.get('type') == 'text' and c.get('content')]
        if not text_parts:
            await self.logger.info('QQ Official: synthetic reply has no text content; skipping')
            return
        text = '\n\n'.join(text_parts)

        msg_seq = self._next_msg_seq(event_id)
        if msg_seq is None:
            await self.logger.warning(
                f'QQ Official: anchor {event_id!r} exhausted (>5 passive replies); '
                f'cannot deliver synthetic reply for {session_key}'
            )
            return

        try:
            if target_type == 'c2c':
                await self.bot.send_private_text_msg(
                    user_openid=target_id,
                    content=text,
                    event_id=event_id,
                    msg_seq=msg_seq,
                )
            elif target_type == 'group':
                await self.bot.send_group_text_msg(
                    group_openid=target_id,
                    content=text,
                    event_id=event_id,
                    msg_seq=msg_seq,
                )
        except Exception:
            await self.logger.error(f'QQ Official: synthetic reply delivery failed: {traceback.format_exc()}')

    def _resolve_target_from_source(self, source: QQOfficialEvent) -> typing.Optional[tuple[str, str]]:
        """Return ``(target_type, target_id)`` for sending a reply, or
        ``None`` if the scene cannot host a markdown+keyboard message."""
        if source is None:
            return None
        if source.t == 'C2C_MESSAGE_CREATE':
            return 'c2c', source.user_openid
        if source.t == 'GROUP_AT_MESSAGE_CREATE':
            return 'group', source.group_openid
        if source.t == 'AT_MESSAGE_CREATE':
            return 'channel', source.channel_id
        # DIRECT_MESSAGE_CREATE uses the guild DM API which does not accept
        # markdown+keyboard at the time of writing — caller falls back to text.
        return None

    def _resolve_target_from_event(
        self, message_source: platform_events.MessageEvent
    ) -> typing.Optional[tuple[str, str]]:
        """Resolve ``(target_type, target_id)`` from the public event.

        Prefers the platform-native source when present; falls back to
        the synthesized event's sender/group fields so button-click
        resume queries can still find a destination.
        """
        source = message_source.source_platform_object
        if source is not None:
            return self._resolve_target_from_source(source)
        if isinstance(message_source, platform_events.GroupMessage):
            group = getattr(message_source, 'group', None) or (
                message_source.sender.group
                if message_source.sender and hasattr(message_source.sender, 'group')
                else None
            )
            if group and getattr(group, 'id', None):
                return 'group', str(group.id)
        if isinstance(message_source, platform_events.FriendMessage):
            if message_source.sender and getattr(message_source.sender, 'id', None):
                return 'c2c', str(message_source.sender.id)
        return None

    def _prune_pending_forms(self) -> None:
        now = time.time()
        stale = [k for k, v in self._pending_forms.items() if now - v.get('posted_at', 0) > self._PENDING_FORM_TTL]
        for k in stale:
            self._pending_forms.pop(k, None)
        stale_e = [
            k for k, v in self._session_event_ids.items() if now - v.get('posted_at', 0) > self._PENDING_FORM_TTL
        ]
        for k in stale_e:
            self._session_event_ids.pop(k, None)

    async def _handle_form_chunk(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        form_data: dict,
    ) -> None:
        """Send the markdown + keyboard form prompt for a Dify pause.

        Called from ``reply_message_chunk`` when the runner attaches
        ``_form_data`` to the final chunk. Replaces what would otherwise
        be a plain-text numbered-list fallback.
        """
        if self.ap is not None:
            self.ap.logger.info(
                f'QQ Official _handle_form_chunk entered; '
                f'source_present={message_source.source_platform_object is not None} '
                f'form_actions={len(form_data.get("actions") or [])}'
            )
        self._prune_pending_forms()

        source = message_source.source_platform_object
        scene_target = self._resolve_target_from_event(message_source)
        if scene_target is None:
            # No rich-UI fit — fall through to existing text path.
            await self.logger.info('QQ Official: form chunk on unsupported scene; falling back to text')
            text_parts = [m.text for m in message if type(m) is platform_message.Plain]
            fallback_msg = platform_message.MessageChain([platform_message.Plain(text='\n\n'.join(text_parts))])
            try:
                await self.reply_message(message_source, fallback_msg)
            except Exception:
                await self.logger.error(f'QQ Official: form fallback text send failed: {traceback.format_exc()}')
            return

        target_type, target_id = scene_target
        session_key = f'{target_type}_{target_id}'

        # Cancel any in-flight stream / fallback ctx so plain-text prefix
        # doesn't continue alongside the keyboard message.
        msg_id = getattr(source, 'd_id', '') or '' if source is not None else ''
        if msg_id:
            self._stream_ctx.pop(msg_id, None)
            self._stream_ctx_ts.pop(msg_id, None)
            self._fallback_text.pop(msg_id, None)
            self._fallback_text_ts.pop(msg_id, None)

        node_title = form_data.get('node_title') or 'Confirmation needed'
        form_content = form_data.get('form_content') or ''
        is_field_step = bool(form_data.get('_current_input_field')) and not form_data.get('_action_select_only')
        parts = [f'### {node_title}']
        plain_parts = [node_title]
        if form_content.strip():
            parts.append(form_content.strip())
            plain_parts.append(form_content.strip())
        markdown_content = '\n\n'.join(parts)
        plain_content = '\n\n'.join(plain_parts)

        keyboard = build_keyboard_from_select_field(form_data) if is_field_step else None
        is_text_field_step = is_field_step and not keyboard.get('content', {}).get('rows')
        if is_text_field_step:
            keyboard = None
        if keyboard is None and not is_text_field_step:
            keyboard = build_keyboard_from_form(form_data, buttons_per_row=2)
        if keyboard is not None and not keyboard.get('content', {}).get('rows') and not is_text_field_step:
            # No actions to render — fall back to plain text.
            text_msg = platform_message.MessageChain([platform_message.Plain(text=plain_content)])
            try:
                await self.reply_message(message_source, text_msg)
            except Exception:
                await self.logger.error(f'QQ Official: empty-keyboard fallback send failed: {traceback.format_exc()}')
            return

        # Prefer the inbound msg_id (no quota cost). If the source is a
        # synthetic event from a prior click, the cached interaction id
        # serves as event_id for up to 30 min.
        event_id = None
        if not msg_id:
            cached = self._session_event_ids.get(session_key)
            if cached and (time.time() - cached.get('posted_at', 0)) < self._PENDING_FORM_TTL:
                event_id = cached.get('event_id')

        anchor = msg_id or event_id or ''
        msg_seq = self._next_msg_seq(anchor)
        if msg_seq is None:
            await self.logger.warning(
                f'QQ Official: anchor {anchor!r} exhausted (>5 passive replies); '
                f'cannot deliver form card for session={session_key}'
            )
            return

        try:
            await self.bot.send_markdown_keyboard(
                target_type=target_type,
                target_id=target_id,
                markdown_content=markdown_content,
                keyboard=keyboard,
                msg_id=msg_id if (msg_id and not event_id) else None,
                event_id=event_id,
                msg_seq=msg_seq,
            )
            if self.ap is not None:
                self.ap.logger.info(
                    f'QQ Official: form card sent '
                    f'target={target_type}/{target_id} '
                    f'msg_id={msg_id!r} event_id={event_id!r} msg_seq={msg_seq}'
                )
        except Exception:
            if self.ap is not None:
                self.ap.logger.error(
                    f'QQ Official: send_markdown_keyboard failed, falling back to text: {traceback.format_exc()}'
                )
            await self.logger.error(
                f'QQ Official: send_markdown_keyboard failed, falling back to text: {traceback.format_exc()}'
            )
            text_msg = platform_message.MessageChain([platform_message.Plain(text=plain_content)])
            try:
                await self.reply_message(message_source, text_msg)
            except Exception:
                pass
            return

        sender_id = ''
        if source is not None:
            sender_id = (
                getattr(source, 'user_openid', None)
                or getattr(source, 'member_openid', None)
                or getattr(source, 'd_author_id', None)
                or ''
            )
        if not sender_id and message_source.sender is not None:
            sender_id = str(getattr(message_source.sender, 'id', '') or '')
        self._pending_forms[session_key] = {
            'form_data': form_data,
            'msg_id': msg_id,
            'sender_id': sender_id,
            'target_type': target_type,
            'target_id': target_id,
            'source_event_t': source.t if source is not None else None,
            'posted_at': time.time(),
        }
        await self.logger.info(
            f'QQ Official: form posted session={session_key} actions={len(form_data.get("actions") or [])}'
        )

    async def _handle_interaction_create(
        self,
        event_data: dict,
        ws_event_id: typing.Optional[str] = None,
    ) -> None:
        """Handle a button-click INTERACTION_CREATE event.

        Two IDs at play (QQ keeps them separate):
            ws_event_id   top-level payload ``id`` (or webhook ``X-Bot-
                          Event-Id``). The ONLY value accepted as
                          ``event_id`` for subsequent passive replies.
            d['id']       the interaction id — used for PUT
                          /interactions/{id} ack. Cannot be reused as
                          event_id (QQ returns 40034025 if you try).

        Layout (https://bot.q.qq.com/.../msg-btn.html):
            chat_type     0 channel / 1 group / 2 c2c
            data.resolved.button_data  what we set as ``action.data``
            data.resolved.button_id    ``id`` field on the button row
        """
        import langbot_plugin.api.entities.builtin.provider.session as provider_session

        if self.ap is not None:
            self.ap.logger.info(
                f'QQ Official _handle_interaction_create entered; '
                f'ws_event_id={ws_event_id!r} '
                f'interaction_id={(event_data.get("id") if isinstance(event_data, dict) else None)!r} '
                f'chat_type={event_data.get("chat_type") if isinstance(event_data, dict) else None}'
            )

        if not isinstance(event_data, dict):
            await self.logger.warning(f'QQ Official: INTERACTION_CREATE event_data is not dict: {type(event_data)}')
            return

        # ACK uses the interaction id, NOT the ws event id.
        interaction_id = event_data.get('id') or ''
        if interaction_id:
            asyncio.create_task(self.bot.ack_interaction(interaction_id, code=0))

        resolved = (event_data.get('data') or {}).get('resolved') or {}
        action_id = str(resolved.get('button_data') or resolved.get('button_id') or '').strip()
        if not action_id:
            await self.logger.warning('QQ Official: INTERACTION_CREATE missing button_data/button_id; ignoring')
            return

        chat_type = event_data.get('chat_type')
        scene_target: typing.Optional[tuple[str, str]] = None
        if chat_type == 2 or event_data.get('user_openid'):
            scene_target = ('c2c', event_data.get('user_openid') or '')
        elif chat_type == 1 or event_data.get('group_openid'):
            scene_target = ('group', event_data.get('group_openid') or '')
        elif chat_type == 0 or event_data.get('channel_id'):
            scene_target = ('channel', event_data.get('channel_id') or '')

        if not scene_target or not scene_target[1]:
            await self.logger.warning(f'QQ Official: INTERACTION_CREATE missing scene/target; raw={event_data}')
            return

        target_type, target_id = scene_target
        session_key = f'{target_type}_{target_id}'

        self._prune_pending_forms()
        pending = self._pending_forms.get(session_key)
        if not pending:
            await self.logger.warning(
                f'QQ Official: no pending form for session {session_key}; click ignored (action_id={action_id!r})'
            )
            return

        # Cache ws_event_id so a follow-up pause / text reply can use it
        # as event_id for passive delivery (30-min window). Falls back to
        # the interaction_id only if no ws_event_id was provided (e.g.
        # tests / older payload shape) — QQ will reject that value but
        # we log so the mismatch is debuggable.
        cached_event_id = ws_event_id or interaction_id
        if cached_event_id:
            self._session_event_ids[session_key] = {
                'event_id': cached_event_id,
                'posted_at': time.time(),
            }
            # New anchor → fresh 5-reply budget.
            self._anchor_msg_seq[cached_event_id] = 0
            if self.ap is not None and not ws_event_id:
                self.ap.logger.warning(
                    'QQ Official: INTERACTION_CREATE lacked ws_event_id; '
                    'falling back to interaction_id (passive reply may be rejected)'
                )

        form_data: dict = pending.get('form_data') or {}
        actions = form_data.get('actions') or []
        select_choice = resolve_select_button_action(form_data, action_id)
        if action_id.startswith(QQ_SELECT_ACTION_PREFIX) and select_choice is None:
            await self.logger.warning(f'QQ Official: invalid select action_id={action_id!r} for {session_key}')
            return

        matched = None
        if select_choice is None:
            matched = next(
                (a for a in actions if str(a.get('id', '')) == action_id),
                None,
            )
            if matched is None:
                await self.logger.warning(
                    f'QQ Official: action_id={action_id!r} is not present on pending form for {session_key}'
                )
                return
        self._pending_forms.pop(session_key, None)
        action_title = select_choice[1] if select_choice else matched.get('title') or action_id

        initiator_id = str(pending.get('sender_id') or '')
        actor_id = str(event_data.get('member_openid') or event_data.get('user_openid') or initiator_id)

        # Build resume payload matching the shape every other adapter uses
        # (DingTalk / Lark / Telegram / WeCom). The runner's
        # _merge_pending_form_action consumes this verbatim.
        if target_type == 'group' or target_type == 'channel':
            launcher_type = provider_session.LauncherTypes.GROUP
            launcher_id = target_id
        else:
            launcher_type = provider_session.LauncherTypes.PERSON
            launcher_id = target_id

        form_action_data = {
            'form_token': form_data.get('form_token', ''),
            'workflow_run_id': form_data.get('workflow_run_id', ''),
            'action_id': '' if select_choice else action_id,
            'action_title': action_title,
            'node_title': form_data.get('node_title', ''),
            'user': f'{launcher_type.value}_{launcher_id}',
            'inputs': {'select': select_choice[1]} if select_choice else {},
        }
        if select_choice:
            form_action_data['_current_input_field'] = select_choice[0]
            form_action_data['_input_progress'] = True

        event_label = 'Form Select' if select_choice else 'Form Action'
        message_chain = platform_message.MessageChain([platform_message.Plain(text=f'[{event_label}: {action_title}]')])

        if launcher_type == provider_session.LauncherTypes.GROUP:
            synthetic_event: platform_events.MessageEvent = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=actor_id or launcher_id,
                    member_name='',
                    permission='MEMBER',
                    group=platform_entities.Group(
                        id=launcher_id,
                        name='',
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=int(time.time()),
                source_platform_object=None,
            )
        else:
            synthetic_event = platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=actor_id or launcher_id,
                    nickname='',
                    remark='',
                ),
                message_chain=message_chain,
                time=int(time.time()),
                source_platform_object=None,
            )

        if self.ap is None:
            await self.logger.error('QQ Official: ap not injected; cannot enqueue button-click query')
            return

        bot_uuid = ''
        pipeline_uuid = None
        for bot in self.ap.platform_mgr.bots:
            if bot.adapter is self:
                bot_uuid = bot.bot_entity.uuid
                pipeline_uuid = bot.bot_entity.use_pipeline_uuid
                break

        try:
            await self.ap.query_pool.add_query(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=actor_id or launcher_id,
                message_event=synthetic_event,
                message_chain=message_chain,
                adapter=self,
                pipeline_uuid=pipeline_uuid,
                variables={
                    '_dify_form_action': form_action_data,
                    '_routed_by_rule': True,
                },
            )
            await self.logger.info(
                f'QQ Official: button-click query enqueued action_id={action_id!r} '
                f'session={session_key} actor_id={actor_id}'
            )
        except Exception:
            await self.logger.error(f'QQ Official: enqueue button-click query failed: {traceback.format_exc()}')
