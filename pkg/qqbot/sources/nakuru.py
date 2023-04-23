import mirai

from ..adapter import MessageSourceAdapter, MessageConverter, EventConverter
import nakuru

import asyncio
import typing


class NakuruProjectMessageConverter(MessageConverter):
    @staticmethod
    def yiri2target(message_chain: mirai.MessageChain) -> list:
        pass

    @staticmethod
    def target2yiri(message_chain: typing.Any) -> mirai.MessageChain:
        pass


class NakuruProjectEventConverter(EventConverter):
    @staticmethod
    def yiri2target(event: typing.Type[mirai.Event]):
        if event is mirai.GroupMessage:
            return "GroupMessage"
        elif event is mirai.FriendMessage:
            return "FriendMessage"
        elif event is mirai.StrangerMessage:
            return "FriendMessage"
        else:
            raise Exception("Unknown event type: " + str(event))

    @staticmethod
    def target2yiri(event: typing.Any) -> mirai.Event:
        pass


class NakuruProjectAdapter(MessageSourceAdapter):
    """nakuru-project适配器"""
    bot: nakuru.CQHTTP

    message_converter: NakuruProjectMessageConverter
    event_converter: NakuruProjectEventConverter

    def __init__(self, config: dict):
        """初始化nakuru-project的对象"""
        self.bot = nakuru.CQHTTP(**config)

    def send_message(
        self,
        target_type: str,
        target_id: str,
        message: mirai.MessageChain
    ):
        task = None
        if target_type == "group":
            task = self.bot.sendGroupMessage(int(target_id), self.message_converter.yiri2target(message))
        elif target_type == "person":
            task = self.bot.sendFriendMessage(int(target_id), self.message_converter.yiri2target(message))
        else:
            raise Exception("Unknown target type: " + target_type)

        asyncio.run(task)

    def reply_message(
        self,
        message_source: mirai.MessageEvent,
        message: mirai.MessageChain,
        quote_origin: bool = False
    ):
        pass

    def is_muted(self, group_id: int) -> bool:
        pass

    def register_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[[mirai.Event], None]
    ):
        def listener_wrapper(app: nakuru.CQHTTP, source: nakuru.GroupMessage):
            callback(self.event_converter.target2yiri(source))

        self.bot.receiver(self.event_converter.yiri2target(event_type))(listener_wrapper)

    def unregister_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[[mirai.Event], None]
    ):
        pass

    def run_sync(self):
        self.bot.run()

    def kill(self) -> bool:
        return False
