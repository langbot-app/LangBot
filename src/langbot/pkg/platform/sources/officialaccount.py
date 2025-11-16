from __future__ import annotations
import typing
import asyncio
import traceback
import pydantic
import datetime
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
from langbot.libs.official_account_api.oaevent import OAEvent
from langbot.libs.official_account_api.api import OAClient
from langbot.libs.official_account_api.api import OAClientForLongerResponse
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
from langbot.pkg.platform.logger import EventLogger


class OAMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain):
        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                return msg.text

    @staticmethod
    async def target2yiri(message: str, message_id=-1):
        yiri_msg_list = []
        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        yiri_msg_list.append(platform_message.Plain(text=message))
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class OAEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def target2yiri(event: OAEvent):
        if event.type == 'text':
            yiri_chain = await OAMessageConverter.target2yiri(event.message, event.message_id)

            friend = platform_entities.Friend(
                id=event.user_id,
                nickname=str(event.user_id),
                remark='',
            )

            return platform_events.FriendMessage(
                sender=friend,
                message_chain=yiri_chain,
                time=event.timestamp,
                source_platform_object=event,
            )
        else:
            return None


class OfficialAccountAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    message_converter: OAMessageConverter = OAMessageConverter()
    event_converter: OAEventConverter = OAEventConverter()
    bot: typing.Union[OAClient, OAClientForLongerResponse] = pydantic.Field(exclude=True)

    def __init__(self, config: dict, logger: EventLogger):
        required_keys = ['token', 'EncodingAESKey', 'AppSecret', 'AppID', 'Mode']
        missing_keys = [k for k in required_keys if k not in config]
        if missing_keys:
            raise Exception(f'OfficialAccount 缺少配置项: {missing_keys}')

        if config['Mode'] == 'drop':
            bot = OAClient(
                token=config['token'],
                EncodingAESKey=config['EncodingAESKey'],
                Appsecret=config['AppSecret'],
                AppID=config['AppID'],
                logger=logger,
            )
        elif config['Mode'] == 'passive':
            bot = OAClientForLongerResponse(
                token=config['token'],
                EncodingAESKey=config['EncodingAESKey'],
                Appsecret=config['AppSecret'],
                AppID=config['AppID'],
                LoadingMessage=config.get('LoadingMessage', ''),
                logger=logger,
            )
        else:
            raise KeyError('请设置微信公众号通信模式')

        bot_account_id = config.get('AppID', '')

        super().__init__(
            bot=bot,
            bot_account_id=bot_account_id,
            config=config,
            logger=logger,
        )

    async def reply_message(
        self,
        message_source: platform_events.FriendMessage,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        content = await OAMessageConverter.yiri2target(message)
        if isinstance(self.bot, OAClient):
            await self.bot.set_message(message_source.message_chain.message_id, content)
        elif isinstance(self.bot, OAClientForLongerResponse):
            from_user = message_source.sender.id
            await self.bot.set_message(from_user, message_source.message_chain.message_id, content)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        pass

    def register_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: OAEvent):
            self.bot_account_id = event.receiver_id
            try:
                return await callback(await self.event_converter.target2yiri(event), self)
            except Exception:
                await self.logger.error(f'Error in officialaccount callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('text')(on_message)
        elif event_type == platform_events.GroupMessage:
            pass

    async def run_async(self):
        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        await self.bot.run_task(
            host=self.config['host'],
            port=self.config['port'],
            shutdown_trigger=shutdown_trigger_placeholder,
        )

    async def kill(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    async def is_muted(
        self,
        group_id: str,
    ) -> bool:
        pass
