from __future__ import annotations
import typing
import asyncio
import traceback
import time

import datetime
import pydantic

from langbot.libs.wecom_customer_service_api.api import WecomCSClient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.libs.wecom_customer_service_api.wecomcsevent import WecomCSEvent
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from langbot_plugin.api.entities.builtin.command import errors as command_errors
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from ..wecomcs.config_resolver import resolve_wecomcs_runtime_settings
from ..wecomcs.runtime import WecomCSSchedulerRuntime


class WecomMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: WecomCSClient):
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
                content_list.append(
                    {
                        'type': 'image',
                        'media_id': await bot.get_media_id(msg),
                    }
                )
            elif type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    content_list.extend((await WecomMessageConverter.yiri2target(node.message_chain, bot)))
            else:
                content_list.append(
                    {
                        'type': 'text',
                        'content': str(msg),
                    }
                )

        return content_list

    @staticmethod
    async def target2yiri(message: str, message_id: int = -1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain

    @staticmethod
    async def target2yiri_image(picurl: str, message_id: int = -1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))
        yiri_msg_list.append(platform_message.Image(base64=picurl))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class WecomEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.Event, bot_account_id: int, bot: WecomCSClient) -> WecomCSEvent:
        # only for extracting user information

        if type(event) is platform_events.GroupMessage:
            pass

        if type(event) is platform_events.FriendMessage:
            return event.source_platform_object

    @staticmethod
    async def target2yiri(event: WecomCSEvent, bot: WecomCSClient = None):
        """
        将 WecomEvent 转换为平台的 FriendMessage 对象。

        Args:
            event (WecomEvent): 企业微信客服事件。
            bot (WecomCSClient): 企业微信客服客户端，用于获取用户信息。

        Returns:
            platform_events.FriendMessage: 转换后的 FriendMessage 对象。
        """
        import logging
        _logger = logging.getLogger('langbot')

        _logger.debug(f'[wecomcs] target2yiri开始: event.type={event.type}, user_id={event.user_id}')

        # 中文注释：昵称查询只是增强信息，不能阻塞主消息链路，因此这里做短超时保护并打印总耗时。
        nickname = str(event.user_id)
        if bot and event.user_id:
            lookup_started_at = time.perf_counter()
            try:
                _logger.debug(f'[wecomcs] 正在获取用户昵称: user_id={event.user_id}')
                timeout_seconds = float(getattr(bot, 'nickname_lookup_timeout_seconds', 30.0) or 30.0)
                customer_info = await asyncio.wait_for(bot.get_customer_info(event.user_id), timeout=timeout_seconds)
                if customer_info and customer_info.get('nickname'):
                    nickname = customer_info.get('nickname')
                elapsed_ms = (time.perf_counter() - lookup_started_at) * 1000
                _logger.debug(f'[wecomcs] 用户昵称查询完成: user_id={event.user_id}, nickname={nickname}, elapsed_ms={elapsed_ms:.2f}')
            except asyncio.TimeoutError:
                timeout_seconds = float(getattr(bot, 'nickname_lookup_timeout_seconds', 30.0) or 30.0)
                elapsed_ms = (time.perf_counter() - lookup_started_at) * 1000
                _logger.warning(
                    f'[wecomcs] 获取用户昵称超时: user_id={event.user_id}, timeout_seconds={timeout_seconds}, elapsed_ms={elapsed_ms:.2f}'
                )
            except Exception as e:
                elapsed_ms = (time.perf_counter() - lookup_started_at) * 1000
                _logger.warning(
                    f'[wecomcs] 获取用户昵称异常: user_id={event.user_id}, error_type={type(e).__name__}, error={e}, elapsed_ms={elapsed_ms:.2f}'
                )
                pass  # Fall back to user_id as nickname

        _logger.debug(f'[wecomcs] target2yiri: event.type={event.type}, message={event.message[:30] if event.message else "N/A"}...')

        # 转换消息链
        if event.type == 'text':
            yiri_chain = await WecomMessageConverter.target2yiri(event.message, event.message_id)
            friend = platform_entities.Friend(
                id=f'u{event.user_id}',
                nickname=nickname,
                remark='',
            )

            return platform_events.FriendMessage(
                sender=friend, message_chain=yiri_chain, time=event.timestamp, source_platform_object=event
            )
        elif event.type == 'image':
            friend = platform_entities.Friend(
                id=f'u{event.user_id}',
                nickname=nickname,
                remark='',
            )

            yiri_chain = await WecomMessageConverter.target2yiri_image(picurl=event.picurl, message_id=event.message_id)

            return platform_events.FriendMessage(
                sender=friend, message_chain=yiri_chain, time=event.timestamp, source_platform_object=event
            )


class WecomCSAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: WecomCSClient = pydantic.Field(exclude=True)
    message_converter: WecomMessageConverter = WecomMessageConverter()
    event_converter: WecomEventConverter = WecomEventConverter()
    bot_uuid: str = None
    scheduler_runtime: WecomCSSchedulerRuntime | None = None
    resolved_wecomcs_runtime_settings: dict = pydantic.Field(default_factory=dict, exclude=True)

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        required_keys = [
            'corpid',
            'secret',
            'token',
            'EncodingAESKey',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise command_errors.ParamNotEnoughError('企业微信客服缺少相关配置项，请查看文档或联系管理员')

        ap = getattr(logger, 'ap', None)
        global_scheduler_config = {}
        if ap is not None and getattr(ap, 'instance_config', None) is not None:
            global_scheduler_config = ap.instance_config.data.get('wecomcs_scheduler', {})
        resolved_runtime_settings = resolve_wecomcs_runtime_settings(config, global_scheduler_config)

        bot = WecomCSClient(
            corpid=config['corpid'],
            secret=config['secret'],
            token=config['token'],
            EncodingAESKey=config['EncodingAESKey'],
            logger=logger,
            unified_mode=True,
            api_base_url=config.get('api_base_url', 'https://qyapi.weixin.qq.com/cgi-bin'),
        )
        # 中文注释：昵称查询发生在消息转换阶段，不依赖 Redis 调度是否启用，所以在适配器初始化时就写入解析后的超时值。
        bot.nickname_lookup_timeout_seconds = float(resolved_runtime_settings['nickname_lookup_timeout_seconds'])

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id='',
            listeners={},
            bot=bot,
        )
        self.resolved_wecomcs_runtime_settings = resolved_runtime_settings

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        Wecom_event = await WecomEventConverter.yiri2target(message_source, self.bot_account_id, self.bot)
        content_list = await WecomMessageConverter.yiri2target(message, self.bot)

        for content in content_list:
            if content['type'] != 'text':
                continue

            try:
                await self.bot.send_text_msg(
                    open_kfid=Wecom_event.receiver_id,
                    external_userid=Wecom_event.user_id,
                    msgid=Wecom_event.message_id,
                    content=content['content'],
                )
                state_store = getattr(self.bot, 'state_store', None)
                if state_store and self.bot_uuid:
                    await state_store.mark_reply_success(self.bot_uuid, Wecom_event.receiver_id, Wecom_event.message_id)
            except Exception as exc:
                state_store = getattr(self.bot, 'state_store', None)
                if state_store and self.bot_uuid:
                    await state_store.mark_reply_failed(
                        self.bot_uuid,
                        Wecom_event.receiver_id,
                        Wecom_event.message_id,
                        error=str(exc),
                    )
                raise

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    def set_bot_uuid(self, bot_uuid: str):
        """设置 bot UUID（用于生成 webhook URL）"""
        self.bot_uuid = bot_uuid
        self.bot.bot_uuid = bot_uuid

        ap = getattr(self.logger, 'ap', None)
        if ap is None or getattr(ap, 'redis_mgr', None) is None or not ap.redis_mgr.is_available():
            return

        scheduler_config = dict(ap.instance_config.data.get('wecomcs_scheduler', {}))
        scheduler_config.update(self.resolved_wecomcs_runtime_settings)
        if not scheduler_config.get('enabled', False):
            return

        self.scheduler_runtime = WecomCSSchedulerRuntime(
            bot_uuid=bot_uuid,
            client=self.bot,
            redis_mgr=ap.redis_mgr,
            scheduler_config=scheduler_config,
            persistence_mgr=ap.persistence_mgr,
        )
        self.bot.state_store = self.scheduler_runtime.state_store

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        import logging
        _logger = logging.getLogger('langbot')

        async def on_message(event: WecomCSEvent):
            self.bot_account_id = event.receiver_id
            try:
                _logger.debug(f'[wecomcs] adapter收到消息: type={event.type}, user_id={event.user_id}')
                yiri_event = await self.event_converter.target2yiri(event, self.bot)
                _logger.debug(f'[wecomcs] 转换后事件: {type(yiri_event).__name__}, sender_id={yiri_event.sender.id if yiri_event else "N/A"}')
                result = await callback(yiri_event, self)
                _logger.debug(f'[wecomcs] callback完成: result={result}')
                return result
            except Exception as e:
                _logger.error(f'[wecomcs] adapter回调异常: {traceback.format_exc()}')
                print(f'[wecomcs] adapter回调异常: {e}', flush=True)

        if event_type == platform_events.FriendMessage:
            _logger.debug(f'[wecomcs] 注册 FriendMessage 监听器, 当前handlers: {list(self.bot._message_handlers.keys())}')
            self.bot.on_message('text')(on_message)
            self.bot.on_message('image')(on_message)
            _logger.debug(f'[wecomcs] 注册后 handlers: {list(self.bot._message_handlers.keys())}')
        elif event_type == platform_events.GroupMessage:
            pass

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
        if self.scheduler_runtime is not None:
            await self.scheduler_runtime.run()
            return

        # 统一 webhook 模式下，不启动独立的 Quart 应用
        # 保持运行但不启动独立端口
        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await keep_alive()

    async def kill(self) -> bool:
        if self.scheduler_runtime is not None:
            await self.scheduler_runtime.stop()
        return False

    async def is_muted(self, group_id: int) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)
