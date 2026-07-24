from __future__ import annotations
import typing
import asyncio
import time
import traceback
import base64

import datetime

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ..logger import EventLogger
from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.libs.wecom_ai_bot_api.api import (
    WecomBotClient,
    extract_template_card_action,
    extract_template_card_event_payload,
    extract_template_card_selections,
    parse_select_button_action,
)
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient


class WecomBotMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        """Convert a MessageChain into a list of component dicts.

        Each dict has a ``type`` key (``'text'``, ``'image'``,
        ``'voice'``, ``'file'``). Text items carry ``text``; media
        items carry ``base64`` (may include a ``data:...;base64,``
        prefix) and optionally ``name``.
        """
        items: list[dict] = []
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                items.append({'type': 'text', 'text': msg.text})
            elif type(msg) is platform_message.Image:
                items.append({'type': 'image', 'base64': msg.base64 or ''})
            elif type(msg) is platform_message.Voice:
                items.append({'type': 'voice', 'base64': msg.base64 or ''})
            elif type(msg) is platform_message.File:
                items.append({'type': 'file', 'base64': msg.base64 or '', 'name': msg.name or ''})
        return items

    @staticmethod
    async def target2yiri(event: WecomBotEvent, bot_name: str = ''):
        yiri_msg_list = []
        if event.type == 'group':
            yiri_msg_list.append(platform_message.At(target=event.ai_bot_id))

        yiri_msg_list.append(platform_message.Source(id=event.message_id, time=datetime.datetime.now()))

        if event.content:
            content = event.content
            if bot_name:
                content = content.replace(f'@{bot_name}', '').strip()
            yiri_msg_list.append(platform_message.Plain(text=content))

        images = []
        if event.images:
            images.extend([img for img in event.images if img])
        if not images and event.picurl:
            images.append(event.picurl)
        for image_base64 in images:
            if image_base64:
                yiri_msg_list.append(platform_message.Image(base64=image_base64))

        file_info = event.file or {}
        if file_info:
            file_url = (
                file_info.get('download_url')
                or file_info.get('url')
                or file_info.get('fileurl')
                or file_info.get('path')
            )
            file_base64 = file_info.get('base64')
            file_name = file_info.get('filename') or file_info.get('name')
            file_size = file_info.get('filesize') or file_info.get('size')
            file_data = file_url or file_base64
            if file_data or file_name:
                file_kwargs = {}
                if file_data:
                    file_kwargs['url'] = file_data
                if file_name:
                    file_kwargs['name'] = file_name
                if file_size is not None:
                    file_kwargs['size'] = file_size
                try:
                    yiri_msg_list.append(platform_message.File(**file_kwargs))
                except Exception:
                    # 兜底
                    yiri_msg_list.append(platform_message.Unknown(text='[file message unsupported]'))

        voice_info = event.voice or {}
        if voice_info:
            voice_payload = voice_info.get('base64') or voice_info.get('url')
            if voice_payload:
                if voice_info.get('base64') and not voice_payload.startswith('data:'):
                    voice_payload = f'data:audio/mpeg;base64,{voice_info.get("base64")}'
                try:
                    yiri_msg_list.append(platform_message.Voice(base64=voice_payload))
                except Exception:
                    try:
                        voice_kwargs = {'url': voice_payload}
                        voice_name = voice_info.get('filename') or voice_info.get('name')
                        voice_size = voice_info.get('filesize') or voice_info.get('size')
                        if voice_name:
                            voice_kwargs['name'] = voice_name
                        if voice_size is not None:
                            voice_kwargs['size'] = voice_size
                        yiri_msg_list.append(platform_message.File(**voice_kwargs))
                    except Exception:
                        yiri_msg_list.append(platform_message.Unknown(text='[voice message unsupported]'))

        video_info = event.video or {}
        if video_info:
            video_payload = (
                video_info.get('base64')
                or video_info.get('url')
                or video_info.get('download_url')
                or video_info.get('fileurl')
            )
            if video_payload:
                video_kwargs = {'url': video_payload}
                video_name = video_info.get('filename') or video_info.get('name')
                video_size = video_info.get('filesize') or video_info.get('size')
                if video_name:
                    video_kwargs['name'] = video_name
                if video_size is not None:
                    video_kwargs['size'] = video_size
                try:
                    # 没有专门的视频类型，沿用 File 传递给上层
                    yiri_msg_list.append(platform_message.File(**video_kwargs))
                except Exception:
                    yiri_msg_list.append(platform_message.Unknown(text='[video message unsupported]'))

        if event.msgtype == 'link' and event.link:
            link = event.link
            summary = '\n'.join(
                filter(
                    None,
                    [link.get('title', ''), link.get('description') or link.get('digest', ''), link.get('url', '')],
                )
            )
            if summary:
                yiri_msg_list.append(platform_message.Plain(text=summary))

        # Handle quoted message (引用消息) - important for group chat file references
        # Extract files/images/voice from quote and add them as top-level components
        # so that plugins like FileReader can process them the same way as direct messages
        quote_info = event.quote or {}
        if quote_info:
            # Process quote text content - add as Plain for context
            if quote_info.get('content'):
                yiri_msg_list.append(platform_message.Plain(text=f'[引用消息] {quote_info.get("content")}'))

            # Process quote images - add as top-level Image components
            quote_images = quote_info.get('images', [])
            if not quote_images and quote_info.get('picurl'):
                quote_images = [quote_info.get('picurl')]
            for img_data in quote_images:
                if img_data:
                    yiri_msg_list.append(platform_message.Image(base64=img_data))

            # Process quote file - add as top-level File component (same as private chat)
            quote_file = quote_info.get('file') or {}
            if quote_file:
                file_url = (
                    quote_file.get('base64')
                    or quote_file.get('download_url')
                    or quote_file.get('url')
                    or quote_file.get('fileurl')
                )
                file_name = quote_file.get('filename') or quote_file.get('name')
                file_size = quote_file.get('filesize') or quote_file.get('size')
                if file_url or file_name:
                    file_kwargs = {}
                    if file_url:
                        file_kwargs['url'] = file_url
                    if file_name:
                        file_kwargs['name'] = file_name
                    if file_size is not None:
                        file_kwargs['size'] = file_size
                    try:
                        yiri_msg_list.append(platform_message.File(**file_kwargs))
                    except Exception:
                        yiri_msg_list.append(platform_message.Unknown(text='[quoted file unsupported]'))

            # Process quote voice - add as top-level Voice/File component
            quote_voice = quote_info.get('voice') or {}
            if quote_voice:
                voice_payload = quote_voice.get('base64') or quote_voice.get('url')
                if voice_payload:
                    if quote_voice.get('base64') and not voice_payload.startswith('data:'):
                        voice_payload = f'data:audio/mpeg;base64,{quote_voice.get("base64")}'
                    try:
                        yiri_msg_list.append(platform_message.Voice(base64=voice_payload))
                    except Exception:
                        try:
                            voice_kwargs = {'url': voice_payload}
                            voice_name = quote_voice.get('filename') or quote_voice.get('name')
                            voice_size = quote_voice.get('filesize') or quote_voice.get('size')
                            if voice_name:
                                voice_kwargs['name'] = voice_name
                            if voice_size is not None:
                                voice_kwargs['size'] = voice_size
                            yiri_msg_list.append(platform_message.File(**voice_kwargs))
                        except Exception:
                            yiri_msg_list.append(platform_message.Unknown(text='[quoted voice unsupported]'))

            # Process quote video - add as top-level File component
            quote_video = quote_info.get('video') or {}
            if quote_video:
                video_payload = (
                    quote_video.get('base64')
                    or quote_video.get('url')
                    or quote_video.get('download_url')
                    or quote_video.get('fileurl')
                )
                if video_payload:
                    video_kwargs = {'url': video_payload}
                    video_name = quote_video.get('filename') or quote_video.get('name')
                    video_size = quote_video.get('filesize') or quote_video.get('size')
                    if video_name:
                        video_kwargs['name'] = video_name
                    if video_size is not None:
                        video_kwargs['size'] = video_size
                    try:
                        yiri_msg_list.append(platform_message.File(**video_kwargs))
                    except Exception:
                        yiri_msg_list.append(platform_message.Unknown(text='[quoted video unsupported]'))

            # Process quote link - add as Plain text
            quote_link = quote_info.get('link') or {}
            if quote_link:
                link_summary = '\n'.join(
                    filter(
                        None,
                        [
                            quote_link.get('title', ''),
                            quote_link.get('description') or quote_link.get('digest', ''),
                            quote_link.get('url', ''),
                        ],
                    )
                )
                if link_summary:
                    yiri_msg_list.append(platform_message.Plain(text=f'[引用链接] {link_summary}'))

        has_content_element = any(
            not isinstance(element, (platform_message.Source, platform_message.At)) for element in yiri_msg_list
        )
        if not has_content_element:
            fallback_type = event.msgtype or 'unknown'
            yiri_msg_list.append(platform_message.Unknown(text=f'[unsupported wecom msgtype: {fallback_type}]'))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class WecomBotEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self, bot_name: str = ''):
        self.bot_name = bot_name

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        return event.source_platform_object

    async def target2yiri(self, event: WecomBotEvent):
        message_chain = await WecomBotMessageConverter.target2yiri(event, bot_name=self.bot_name)
        if event.type == 'single':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.userid,
                    nickname=event.username,
                    remark='',
                ),
                message_chain=message_chain,
                time=datetime.datetime.now().timestamp(),
                source_platform_object=event,
            )
        elif event.type == 'group':
            try:
                sender = platform_entities.GroupMember(
                    id=event.userid,
                    permission='MEMBER',
                    member_name=event.username,
                    group=platform_entities.Group(
                        id=str(event.chatid),
                        name=event.chatname,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                )
                time = datetime.datetime.now().timestamp()
                return platform_events.GroupMessage(
                    sender=sender,
                    message_chain=message_chain,
                    time=time,
                    source_platform_object=event,
                )
            except Exception:
                print(traceback.format_exc())


class WecomBotAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: typing.Union[WecomBotClient, WecomBotWsClient]
    bot_account_id: str
    message_converter: WecomBotMessageConverter = WecomBotMessageConverter()
    event_converter: WecomBotEventConverter
    config: dict
    bot_uuid: str = None
    _ws_mode: bool = False
    bot_name: str = ''
    listeners: dict = {}
    _stream_to_monitoring_msg: dict = {}  # Maps stream_id to (monitoring_message_id, timestamp)
    _STREAM_MAPPING_TTL = 600  # 10 minutes
    ap: typing.Any = None

    def __init__(self, config: dict, logger: EventLogger):
        enable_webhook = config.get('enable-webhook', False)
        bot_name = config.get('robot_name', '')

        if not enable_webhook:
            bot = WecomBotWsClient(
                bot_id=config['BotId'],
                secret=config['Secret'],
                logger=logger,
                encoding_aes_key=config.get('EncodingAESKey', ''),
            )
        else:
            # Webhook callback mode
            required_keys = ['Token', 'EncodingAESKey', 'Corpid']
            missing_keys = [key for key in required_keys if key not in config or not config[key]]
            if missing_keys:
                raise Exception(f'WecomBot webhook mode missing config: {missing_keys}')

            bot = WecomBotClient(
                Token=config['Token'],
                EnCodingAESKey=config['EncodingAESKey'],
                Corpid=config['Corpid'],
                logger=logger,
                unified_mode=True,
            )

        bot_account_id = config.get('BotId', '')
        event_converter = WecomBotEventConverter(bot_name=bot_name)
        super().__init__(
            config=config,
            logger=logger,
            bot=bot,
            bot_account_id=bot_account_id,
            bot_name=bot_name,
            event_converter=event_converter,
            listeners={},
            _stream_to_monitoring_msg={},
        )

        # Both WecomBotClient (webhook) and WecomBotWsClient (ws long-conn)
        # expose ``set_card_action_callback``. Wire the click handler so
        # Dify human-input button taps resume the workflow on either mode.
        if hasattr(self.bot, 'set_card_action_callback'):
            self.bot.set_card_action_callback(self._on_card_action)

        # Hand the client a `source` block so every interactive
        # template_card it emits carries the LangBot logo + name at the
        # top — the WeCom analogue of DingTalk's Avatar header.
        # Always on; icon_url accepts plain HTTPS URLs (no upload needed).
        if hasattr(self.bot, 'set_card_source'):
            self.bot.set_card_source(
                {
                    'icon_url': 'https://raw.githubusercontent.com/RockChinQ/LangBot/master/res/logo-blue.png',
                    'desc': 'LangBot',
                    'desc_color': 0,
                }
            )

    @staticmethod
    def _join_text_components(items: list[dict]) -> str:
        """Concatenate ``text`` items in order, leaving media items alone."""
        return ''.join(item['text'] for item in items if item.get('type') == 'text')

    @staticmethod
    def _iter_media_components(items: list[dict]):
        """Yield non-text items in order."""
        for item in items:
            if item.get('type') in {'image', 'voice', 'file'}:
                yield item

    async def _send_media(
        self,
        bot,
        req_id: str,
        item: dict,
    ) -> bool:
        """Upload *item* to the WeCom AI Bot CDN and send it as a media reply.

        Returns True on success. Falls back to a no-op (with a warning log)
        if the SDK does not yet implement ``upload_media`` /
        ``reply_image`` / ``reply_file`` / ``reply_voice`` — the framework
        will keep working, just without image delivery.
        """
        kind = item.get('type')
        upload = getattr(bot, 'upload_media', None)
        if upload is None:
            await self.logger.warning(f'_send_media: bot has no upload_media method, kind={kind}')
            return False
        b64_text = item.get('base64') or ''
        if not b64_text:
            await self.logger.warning(f'_send_media: empty base64 for kind={kind}')
            return False
        if b64_text.startswith('data:') and ',' in b64_text:
            b64_text = b64_text.split(',', 1)[1]
        try:
            data = base64.b64decode(b64_text, validate=False)
        except Exception as e:
            await self.logger.warning(f'_send_media: base64 decode failed: {e}')
            return False
        if not data:
            await self.logger.warning(f'_send_media: decoded data is empty, kind={kind}')
            return False
        try:
            upload_result = await upload(data, item.get('name') or f'attachment.{kind}', media_type=kind)
        except Exception as e:
            await self.logger.warning(f'_send_media: upload_media raised: {e}')
            return False
        media_id = getattr(upload_result, 'media_id', None) or (
            isinstance(upload_result, dict) and upload_result.get('media_id')
        )
        if not media_id:
            await self.logger.warning(f'_send_media: no media_id in upload result: {upload_result!r}')
            return False
        reply_fn = {
            'image': getattr(bot, 'reply_image', None),
            'file': getattr(bot, 'reply_file', None),
            'voice': getattr(bot, 'reply_voice', None),
        }.get(kind)
        if reply_fn is None:
            await self.logger.warning(f'_send_media: no reply_{kind} method on bot')
            return False
        try:
            await reply_fn(req_id, media_id)
            await self.logger.info(f'_send_media: sent {kind} media_id={media_id} req_id={req_id}')
            return True
        except Exception as e:
            await self.logger.warning(f'_send_media: reply_{kind} raised: {e}')
            return False

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        items = await self.message_converter.yiri2target(message)
        text = self._join_text_components(items)
        _ws_mode = not self.config.get('enable-webhook', False)

        event = message_source.source_platform_object
        # Synthetic events (button-click resume queries) have no inbound
        # platform object. Fall back to a proactive send so error
        # messages and one-shot replies still reach the user.
        if event is None:
            if _ws_mode:
                if isinstance(message_source, platform_events.GroupMessage):
                    chat_id = str(message_source.group.id)
                else:
                    chat_id = str(message_source.sender.id)
                try:
                    await self.bot.send_message(chat_id, text)
                except Exception:
                    await self.logger.error(
                        f'WeComBot: proactive reply for synthetic event failed: {traceback.format_exc()}'
                    )
            else:
                await self.logger.warning(
                    'WeComBot webhook mode cannot reply to a synthetic event '
                    '(no req_id and no proactive-send credentials); dropping.'
                )
            return

        if _ws_mode:
            req_id = event.get('req_id', '') if isinstance(event, dict) else getattr(event, 'req_id', '')
            if text:
                if req_id:
                    await self.bot.reply_text(req_id, text)
                else:
                    await self.bot.set_message(event.message_id, text)
            for item in self._iter_media_components(items):
                await self._send_media(self.bot, req_id, item)
        else:
            await self.bot.set_message(event.message_id, text)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        items = await self.message_converter.yiri2target(message)
        text = self._join_text_components(items)
        _ws_mode = not self.config.get('enable-webhook', False)

        # Synthetic events (e.g. button-click triggered form resume) have
        # no inbound platform message — no msg_id, no req_id, no stream
        # session. The output must go via the proactive-send path instead
        # of the stream/reply path.
        spo = message_source.source_platform_object
        if spo is None:
            return await self._handle_synthetic_chunk(message_source, bot_message, text, is_final, _ws_mode)

        msg_id = spo.message_id

        # Dify human-input pause: when the runner attaches `_form_data` to
        # the final chunk, hand the button_interaction card off to the
        # underlying client. In webhook mode the card is queued for the
        # next followup poll; in ws mode it's sent as a reply frame
        # immediately. Falls back to plain text when the bot has no active
        # stream session for this msg_id (rare).
        form_data = getattr(bot_message, '_form_data', None)
        if form_data and is_final:
            if hasattr(self.bot, 'push_form_pause'):
                ok, stream_id, task_id = await self.bot.push_form_pause(msg_id, form_data)
                if ok:
                    await self.logger.info(
                        f'WeComBot: pending button_interaction registered '
                        f'stream_id={stream_id} task_id={task_id} ws_mode={_ws_mode}'
                    )
                    return {'stream': True, 'form': True, 'task_id': task_id}
            await self.logger.warning(
                'WeComBot: cannot register form pause (no active stream session); falling back to plain text'
            )
            try:
                from langbot.pkg.provider.runners.difysvapi import _format_human_input_text

                fallback = _format_human_input_text(
                    form_data.get('node_title', ''),
                    form_data.get('form_content', ''),
                    form_data.get('actions', []) or [],
                )
            except Exception:
                fallback = text or '（人工输入）'
            if _ws_mode:
                event = message_source.source_platform_object
                req_id = event.get('req_id', '') if isinstance(event, dict) else getattr(event, 'req_id', '')
                if req_id:
                    await self.bot.reply_text(req_id, fallback)
            else:
                await self.bot.set_message(msg_id, fallback)
            return {'stream': False, 'form': True, 'fallback': True}

        if _ws_mode:
            success = await self.bot.push_stream_chunk(msg_id, text, is_final=is_final)
            if not success and is_final:
                event = message_source.source_platform_object
                req_id = event.get('req_id', '')
                if req_id:
                    await self.bot.reply_text(req_id, text)
            if is_final:
                event = message_source.source_platform_object
                req_id = event.get('req_id', '')
                for item in self._iter_media_components(items):
                    await self._send_media(self.bot, req_id, item)
            return {'stream': success}
        else:
            success = await self.bot.push_stream_chunk(msg_id, text, is_final=is_final)
            if not success and is_final:
                await self.bot.set_message(msg_id, text)
            return {'stream': success}

    async def is_stream_output_supported(self) -> bool:
        """Whether streaming output is enabled for this bot instance."""
        return self.config.get('enable-stream-reply', True)

    async def _handle_synthetic_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        content: str,
        is_final: bool,
        ws_mode: bool,
    ) -> dict:
        """Handle reply_message_chunk for synthetic events (button clicks).

        Synthetic events have no inbound message → no msg_id, no req_id,
        no stream session. We can't do incremental streaming, so we
        buffer chunks per-conversation and flush on ``is_final`` via the
        proactive send path.

        Buffer keyed by ``(launcher_type, launcher_id)`` from the
        synthetic event itself. Only ws mode has a usable proactive-send
        path right now (``ws_client.send_message`` /
        ``ws_client.send_template_card``); webhook mode requires a
        corpid/secret we don't have, so it logs and drops.
        """
        if isinstance(message_source, platform_events.GroupMessage):
            chat_id = str(message_source.group.id)
        else:
            chat_id = str(message_source.sender.id)

        form_data = getattr(bot_message, '_form_data', None)

        # Buffer streaming content until is_final.
        buf_key = chat_id
        if not hasattr(self, '_synthetic_buffers'):
            # Attribute-not-declared trick: pydantic forbids dynamic attrs
            # on the model, but plain instance dicts via object.__setattr__
            # do work. Lazy-create on first call.
            object.__setattr__(self, '_synthetic_buffers', {})
        buffers: dict[str, str] = self._synthetic_buffers
        if content and not form_data:
            previous = buffers.get(buf_key, '')
            if previous and content.startswith(previous):
                buffers[buf_key] = content
            elif previous and previous.endswith(content):
                buffers[buf_key] = previous
            else:
                buffers[buf_key] = previous + content

        if not is_final:
            return {'stream': True, 'synthetic': True, 'buffered': True}

        final_content = buffers.pop(buf_key, '')
        if content:
            if final_content and content.startswith(final_content):
                final_content = content
            elif final_content and final_content.endswith(content):
                pass
            else:
                final_content = final_content + content

        if not ws_mode:
            await self.logger.warning(
                'WeComBot webhook mode cannot proactively push synthetic-event '
                'output (no corpid/secret); the resume reply is dropped. '
                f'content_len={len(final_content)} form_data_present={form_data is not None}'
            )
            return {'stream': False, 'synthetic': True, 'dropped': True}

        # ws mode: proactive send.
        try:
            if form_data:
                # Determine user_id / chat_id for the routing context of any
                # subsequent click on this card.
                if isinstance(message_source, platform_events.GroupMessage):
                    routing_chat_id = str(message_source.group.id)
                    routing_user_id = str(message_source.sender.id)
                else:
                    routing_chat_id = ''
                    routing_user_id = str(message_source.sender.id)
                payload = self._build_button_interaction_payload_from_form(
                    form_data,
                    user_id=routing_user_id,
                    chat_id=routing_chat_id,
                )
                await self.bot.send_template_card(chat_id, payload)
                await self.logger.info(
                    f'WeComBot ws: proactively sent template_card for synthetic event '
                    f'chat_id={chat_id} form_token={form_data.get("form_token")!r} '
                    f'workflow_run_id={form_data.get("workflow_run_id")!r}'
                )
            elif final_content:
                await self.bot.send_message(chat_id, final_content)
                await self.logger.info(
                    f'WeComBot ws: proactively sent text for synthetic event chat_id={chat_id} len={len(final_content)}'
                )
        except Exception:
            await self.logger.error(f'WeComBot: synthetic event proactive send failed: {traceback.format_exc()}')
            return {'stream': False, 'synthetic': True, 'error': True}

        return {'stream': True, 'synthetic': True}

    def _build_button_interaction_payload_from_form(
        self, form_data: dict, *, user_id: str = '', chat_id: str = ''
    ) -> dict:
        """Build a button_interaction payload + track task_id for click resolution.

        Unlike the inbound-event path (where push_form_pause registers the
        task_id with the active stream session), proactive sends still
        need the task_id registered so button clicks find pending_form.
        For ws mode we stash it directly on the ws_client's pending dict.
        """
        from langbot.libs.wecom_ai_bot_api.api import build_human_input_template_card_payload
        import secrets as _secrets

        task_id = f'dify-{_secrets.token_hex(12)}'
        source = getattr(self.bot, 'card_source', None)
        payload = build_human_input_template_card_payload(
            form_data,
            task_id,
            source=source,
            select_as_buttons=not self.config.get('enable-webhook', False),
        )

        # Register task_id → form_data so the click callback can find it.
        # user_id / chat_id are required so _on_card_action can route the
        # resulting synthetic query back to the right user. msg_id / req_id
        # / stream_id are intentionally empty — synthetic cards have no
        # inbound message to anchor on.
        if hasattr(self.bot, '_pending_forms_by_task'):
            self.bot._pending_forms_by_task[task_id] = {
                'form_data': form_data,
                'msg_id': '',
                'user_id': user_id,
                'chat_id': chat_id,
                'stream_id': '',
                'req_id': '',
            }
        return payload

    async def send_message(self, target_type, target_id, message):
        _ws_mode = not self.config.get('enable-webhook', False)
        if _ws_mode:
            items = await self.message_converter.yiri2target(message)
            text = self._join_text_components(items)
            await self.bot.send_message(target_id, text)
        else:
            pass

    async def on_message(self, event: WecomBotEvent):
        try:
            lb_event = await self.event_converter.target2yiri(event)
            if lb_event:
                await self.listeners[type(lb_event)](lb_event, self)
        except Exception:
            await self.logger.error(f'Error in wecombot callback: {traceback.format_exc()}')
            print(traceback.format_exc())

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

        try:
            if event_type == platform_events.FriendMessage:
                self.bot.on_message('single')(self.on_message)
            elif event_type == platform_events.GroupMessage:
                self.bot.on_message('group')(self.on_message)
            elif event_type == platform_events.FeedbackEvent:
                if hasattr(self.bot, 'on_feedback'):
                    self.bot.on_feedback()(self._on_feedback)
        except Exception:
            print(traceback.format_exc())

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

    async def on_monitoring_message_created(self, query, monitoring_message_id: str):
        """Called by pipeline after monitoring message is created, to map stream_id to monitoring message ID."""
        try:
            stream_id = query.message_event.source_platform_object.stream_id
            if stream_id:
                self._stream_to_monitoring_msg[stream_id] = (monitoring_message_id, time.time())
                self._cleanup_stream_mapping()
        except Exception as e:
            await self.logger.debug(f'Failed to map stream_id to monitoring message: {e}')

    def _cleanup_stream_mapping(self):
        """Remove entries older than TTL from the stream_id to monitoring message mapping."""
        now = time.time()
        expired = [k for k, (_, ts) in self._stream_to_monitoring_msg.items() if now - ts > self._STREAM_MAPPING_TTL]
        for k in expired:
            del self._stream_to_monitoring_msg[k]

    async def _on_feedback(self, **kwargs):
        """Handle feedback event from WeChat Work AI Bot SDK and dispatch as FeedbackEvent."""
        try:
            feedback_id = kwargs.get('feedback_id', '')
            feedback_type = kwargs.get('feedback_type', 0)
            feedback_content = kwargs.get('feedback_content', '') or None
            inaccurate_reasons = kwargs.get('inaccurate_reasons', []) or None
            # WeChat Work returns integer reason codes, but FeedbackEvent expects strings
            if inaccurate_reasons:
                inaccurate_reasons = [str(r) for r in inaccurate_reasons]
            session = kwargs.get('session')

            session_id = None
            user_id = None
            message_id = None
            stream_id = None
            if session:
                if session.chat_id:
                    session_id = f'group_{session.chat_id}'
                elif session.user_id:
                    session_id = f'person_{session.user_id}'
                user_id = session.user_id
                message_id = session.msg_id
                stream_id = session.stream_id

            # Resolve stream_id to LangBot monitoring message ID if available
            monitoring_msg_id = None
            if stream_id and stream_id in self._stream_to_monitoring_msg:
                monitoring_msg_id = self._stream_to_monitoring_msg[stream_id][0]

            await self.logger.info(
                f'Feedback event: feedback_id={feedback_id}, type={feedback_type}, '
                f'session_id={session_id}, user_id={user_id}, message_id={message_id}'
            )

            event = platform_events.FeedbackEvent(
                feedback_id=feedback_id,
                feedback_type=feedback_type,
                feedback_content=feedback_content,
                inaccurate_reasons=inaccurate_reasons,
                user_id=user_id,
                session_id=session_id,
                message_id=message_id,
                stream_id=monitoring_msg_id or stream_id,
                source_platform_object=session,
            )

            if platform_events.FeedbackEvent in self.listeners:
                await self.listeners[platform_events.FeedbackEvent](event, self)
        except Exception:
            await self.logger.error(f'Error in wecombot feedback callback: {traceback.format_exc()}')

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        _ws_mode = not self.config.get('enable-webhook', False)
        if _ws_mode:
            return None
        return await self.bot.handle_unified_webhook(request)

    async def run_async(self):
        _ws_mode = not self.config.get('enable-webhook', False)
        if _ws_mode:
            await self.bot.connect()
        else:

            async def keep_alive():
                while True:
                    await asyncio.sleep(1)

            await keep_alive()

    async def kill(self) -> bool:
        _ws_mode = not self.config.get('enable-webhook', False)
        if _ws_mode:
            await self.bot.disconnect()
            return True
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    async def is_muted(self, group_id: int) -> bool:
        pass

    # ------------------------------------------------------------------
    # Dify human-input button-interaction click handling
    # ------------------------------------------------------------------

    async def _on_card_action(self, session, action_id: str, task_id: str, raw_event: dict) -> None:
        """Translate a button click on a button_interaction card into a
        synthetic ``_dify_form_action`` query enqueued on the pool.

        Pattern mirrors DingTalk / Lark / Telegram so the runner's
        ``_merge_pending_form_action`` path resumes the workflow.
        """
        import langbot_plugin.api.entities.builtin.provider.session as provider_session

        form = session.pending_form or {}
        await self.logger.info(
            f'WeComBot _on_card_action: task_id={task_id} action_id={action_id!r} '
            f'form_token={form.get("form_token")!r} workflow_run_id={form.get("workflow_run_id")!r} '
            f'session.user_id={session.user_id!r} session.chat_id={session.chat_id!r}'
        )

        actions = form.get('actions') or []
        tce = extract_template_card_event_payload(raw_event) if isinstance(raw_event, dict) else {}
        _, _, card_type = extract_template_card_action(tce)
        selections = extract_template_card_selections(tce, form)
        if not selections:
            selections = parse_select_button_action(action_id, form)
        await self.logger.info(
            f'WeComBot template_card selections: task_id={task_id} card_type={card_type} selections={selections}'
        )
        if card_type == 'multiple_interaction' and not selections:
            await self.logger.warning(
                f'WeComBot: multiple_interaction callback has no parseable selections; raw={str(tce)[:1000]}'
            )
            return
        is_select_submit = card_type == 'multiple_interaction' or bool(selections)

        clean_action_id = '' if is_select_submit else (action_id or '').strip()
        action_title = clean_action_id
        for a in actions:
            if str(a.get('id', '')) == clean_action_id:
                action_title = a.get('title') or clean_action_id
                break

        inputs = dict(form.get('inputs') or {})
        inputs.update(selections)

        def _missing_fields_after_select() -> list[str]:
            missing: list[str] = []
            for field in form.get('input_defs') or form.get('all_input_defs') or []:
                field_name = str(field.get('output_variable_name') or '').strip()
                if not field_name:
                    continue
                if inputs.get(field_name) in (None, '', []):
                    missing.append(field_name)
            return missing

        input_progress = False
        if is_select_submit:
            missing_fields = _missing_fields_after_select()
            if not missing_fields and len(actions) == 1:
                action = actions[0]
                clean_action_id = str(action.get('id') or '').strip()
                action_title = action.get('title') or clean_action_id
            elif not missing_fields and len(actions) > 1:
                if not self.config.get('enable-webhook', False):
                    action_form_data = {
                        'form_content': form.get('raw_form_content') or form.get('form_content') or '',
                        'raw_form_content': form.get('raw_form_content') or form.get('form_content') or '',
                        'input_defs': [],
                        'all_input_defs': form.get('all_input_defs') or form.get('input_defs') or [],
                        'inputs': inputs,
                        'actions': actions,
                        'node_title': form.get('node_title', ''),
                        'workflow_run_id': form.get('workflow_run_id', ''),
                        'form_token': form.get('form_token', ''),
                        'pipeline_uuid': form.get('pipeline_uuid', ''),
                        '_action_select_only': True,
                    }
                    target_chat_id = session.chat_id or session.user_id or ''
                    try:
                        payload = self._build_button_interaction_payload_from_form(
                            action_form_data,
                            user_id=session.user_id or '',
                            chat_id=session.chat_id or '',
                        )
                        await self.bot.send_template_card(target_chat_id, payload)
                        await self.logger.info(
                            f'WeComBot: sent action-select button card after select submit '
                            f'task_id={task_id} action_count={len(actions)}'
                        )
                    except Exception:
                        await self.logger.error(
                            f'WeComBot: failed to send action-select button card: {traceback.format_exc()}'
                        )
                    return
                await self.logger.warning(
                    'WeComBot webhook mode cannot proactively send action-select button card after select submit'
                )
                return
            else:
                input_progress = True
                action_title = 'Submit'

        launcher_id = session.user_id or session.chat_id or ''
        sender_user_id = session.user_id or launcher_id
        # WeCom AI bot has both single-chat and group-chat; chat_id present
        # indicates group context.
        if session.chat_id:
            launcher_type = provider_session.LauncherTypes.GROUP
            launcher_id = session.chat_id
        else:
            launcher_type = provider_session.LauncherTypes.PERSON
            launcher_id = session.user_id or ''

        form_action_data = {
            'form_token': form.get('form_token', ''),
            'workflow_run_id': form.get('workflow_run_id', ''),
            'action_id': clean_action_id,
            'action_title': action_title,
            'node_title': form.get('node_title', ''),
            'user': f'{launcher_type.value}_{launcher_id}',
            'inputs': inputs,
        }
        if input_progress:
            form_action_data['_input_progress'] = True

        message_chain = platform_message.MessageChain([platform_message.Plain(text=f'[Form Action: {action_title}]')])

        if launcher_type == provider_session.LauncherTypes.GROUP:
            synthetic_event = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_user_id,
                    member_name='',
                    permission=platform_entities.Permission.Member,
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
                    id=sender_user_id,
                    nickname='',
                    remark='',
                ),
                message_chain=message_chain,
                time=int(time.time()),
                source_platform_object=None,
            )

        if self.ap is None:
            await self.logger.error('WeComBot: ap not injected; cannot enqueue button-click query')
            return

        bot_uuid = ''
        pipeline_uuid = form.get('pipeline_uuid') or None
        for bot in self.ap.platform_mgr.bots:
            if bot.adapter is self:
                bot_uuid = bot.bot_entity.uuid
                pipeline_uuid = pipeline_uuid or bot.bot_entity.use_pipeline_uuid
                break

        try:
            await self.ap.query_pool.add_query(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
                sender_id=sender_user_id,
                message_event=synthetic_event,
                message_chain=message_chain,
                adapter=self,
                pipeline_uuid=pipeline_uuid,
                variables={
                    '_dify_form_action': form_action_data,
                    '_routed_by_rule': True,
                },
            )
            await self.logger.info(f'WeComBot: button-click query enqueued action_id={clean_action_id!r}')
        except Exception:
            await self.logger.error(f'WeComBot: enqueue button-click query failed: {traceback.format_exc()}')
