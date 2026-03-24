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
from langbot.libs.wecom_ai_bot_api.api import WecomBotClient, StreamSession
from langbot.libs.wecom_ai_bot_api.ws_client import WecomBotWsClient
from ...core import app as langbot_app
from ...pipeline.monitoring_helper import FeedbackMonitor


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
    ap: langbot_app.Application = None  # Application reference for monitoring
    _bot_info: dict = None  # Bot info for monitoring (bot_id, bot_name, pipeline_id, pipeline_name)

    def __init__(self, config: dict, logger: EventLogger, ap: langbot_app.Application = None, **kwargs):
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
            **kwargs,
        )
        self.listeners = {}
        object.__setattr__(self, '_ws_mode', ws_mode)
        object.__setattr__(self, 'ap', ap)

        # Register feedback handler for monitoring
        self._register_feedback_handler()

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
        except Exception:
            print(traceback.format_exc())

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid

    def set_bot_info(
        self,
        bot_id: str,
        bot_name: str,
        pipeline_id: str,
        pipeline_name: str,
    ):
        """设置 bot 信息（用于监控记录）"""
        self._bot_info = {
            'bot_id': bot_id,
            'bot_name': bot_name,
            'pipeline_id': pipeline_id,
            'pipeline_name': pipeline_name,
        }

    def _register_feedback_handler(self):
        """注册用户反馈处理器，用于持久化反馈数据到监控服务"""

        async def handle_feedback(
            feedback_id: str,
            feedback_type: int,
            feedback_content: str,
            inaccurate_reasons: list[str],
            session: StreamSession,
        ):
            """处理用户反馈事件，持久化到监控服务"""
            if not self.ap or not self._bot_info:
                return

            try:
                # Build session_id from session info
                session_id = None
                if session.chat_id:
                    session_id = f'group_{session.chat_id}'
                elif session.user_id:
                    session_id = f'person_{session.user_id}'

                await FeedbackMonitor.record_feedback(
                    ap=self.ap,
                    feedback_id=feedback_id,
                    feedback_type=feedback_type,
                    feedback_content=feedback_content if feedback_content else None,
                    inaccurate_reasons=inaccurate_reasons if inaccurate_reasons else None,
                    bot_id=self._bot_info['bot_id'],
                    bot_name=self._bot_info['bot_name'],
                    pipeline_id=self._bot_info['pipeline_id'],
                    pipeline_name=self._bot_info['pipeline_name'],
                    session_id=session_id,
                    message_id=session.msg_id if session else None,
                    stream_id=session.stream_id if session else None,
                    user_id=session.user_id if session else None,
                    platform='wecom',
                )
            except Exception:
                await self.logger.error(f'Failed to record feedback: {traceback.format_exc()}')

        # Register the feedback handler with the bot client
        if hasattr(self.bot, 'on_feedback'):
            self.bot.on_feedback()(handle_feedback)

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
