from __future__ import annotations
import typing
import asyncio
import traceback

import datetime
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ..logger import EventLogger
from langbot.libs.wecom_ai_bot_api.wecombotevent import WecomBotEvent
from langbot.libs.wecom_ai_bot_api.api import WecomBotClient
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient


class WecomBotMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        content = ''
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                content += msg.text
        return content

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
        )
        self.listeners = {}

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        content = await self.message_converter.yiri2target(message)
        _ws_mode = not self.config.get('enable-webhook', False)

        if _ws_mode:
            event = message_source.source_platform_object
            req_id = event.get('req_id', '')
            if req_id:
                await self.bot.reply_text(req_id, content)
            else:
                await self.bot.set_message(event.message_id, content)
        else:
            await self.bot.set_message(message_source.source_platform_object.message_id, content)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        content = await self.message_converter.yiri2target(message)
        msg_id = message_source.source_platform_object.message_id
        _ws_mode = not self.config.get('enable-webhook', False)

        if _ws_mode:
            success = await self.bot.push_stream_chunk(msg_id, content, is_final=is_final)
            if not success and is_final:
                event = message_source.source_platform_object
                req_id = event.get('req_id', '')
                if req_id:
                    await self.bot.reply_text(req_id, content)
            return {'stream': success}
        else:
            success = await self.bot.push_stream_chunk(msg_id, content, is_final=is_final)
            if not success and is_final:
                await self.bot.set_message(msg_id, content)
            return {'stream': success}

    async def is_stream_output_supported(self) -> bool:
        """Whether streaming output is enabled for this bot instance."""
        return self.config.get('enable-stream-reply', True)

    async def send_message(self, target_type, target_id, message):
        _ws_mode = not self.config.get('enable-webhook', False)
        if _ws_mode:
            content = await self.message_converter.yiri2target(message)
            await self.bot.send_message(target_id, content)
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
                stream_id=stream_id,
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
