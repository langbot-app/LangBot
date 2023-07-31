from ..adapter import MessageSourceAdapter
import mirai
import mirai.models.bus
from mirai.bot import MiraiRunner

import asyncio
import typing


class YiriMiraiAdapter(MessageSourceAdapter):
    """YiriMirai适配器"""
    bot: mirai.Mirai

    def __init__(self, config: dict):
        """初始化YiriMirai的对象"""
        if 'adapter' not in config or \
            config['adapter'] == 'WebSocketAdapter':
            self.bot = mirai.Mirai(
                qq=config['qq'],
                adapter=mirai.WebSocketAdapter(
                    host=config['host'],
                    port=config['port'],
                    verify_key=config['verifyKey']
                )
            )
        elif config['adapter'] == 'HTTPAdapter':
            self.bot = mirai.Mirai(
                qq=config['qq'],
                adapter=mirai.HTTPAdapter(
                    host=config['host'],
                    port=config['port'],
                    verify_key=config['verifyKey']
                )
            )
        else:
            raise Exception('Unknown adapter for YiriMirai: ' + config['adapter'])
    
    def send_message(
        self,
        target_type: str,
        target_id: str,
        message: mirai.MessageChain
    ):
        """发送消息
        
        Args:
            target_type (str): 目标类型，`person`或`group`
            target_id (str): 目标ID
            message (mirai.MessageChain): YiriMirai库的消息链
        """
        task = None
        if target_type == 'person':
            task = self.bot.send_friend_message(int(target_id), message)
        elif target_type == 'group':
            task = self.bot.send_group_message(int(target_id), message)
        else:
            raise Exception('Unknown target type: ' + target_type)

        asyncio.run(task)

    def reply_message(
        self,
        message_source: mirai.MessageEvent,
        message: mirai.MessageChain,
        quote_origin: bool = False
    ):
        """回复消息

        Args:
            message_source (mirai.MessageEvent): YiriMirai消息源事件
            message (mirai.MessageChain): YiriMirai库的消息链
            quote_origin (bool, optional): 是否引用原消息. Defaults to False.
        """
        asyncio.run(self.bot.send(message_source, message, quote_origin))

    def is_muted(self, group_id: int) -> bool:
        result = self.bot.member_info(target=group_id, member_id=self.bot.qq).get()
        result = asyncio.run(result)
        if result.mute_time_remaining > 0:
            return True
        return False

    def register_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[[mirai.Event], None]
    ):
        """注册事件监听器
        
        Args:
            event_type (typing.Type[mirai.Event]): YiriMirai事件类型
            callback (typing.Callable[[mirai.Event], None]): 回调函数，接收一个参数，为YiriMirai事件
        """
        self.bot.on(event_type)(callback)

    def unregister_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[[mirai.Event], None]
    ):
        """注销事件监听器
        
        Args:
            event_type (typing.Type[mirai.Event]): YiriMirai事件类型
            callback (typing.Callable[[mirai.Event], None]): 回调函数，接收一个参数，为YiriMirai事件
        """
        assert isinstance(self.bot, mirai.Mirai)
        bus = self.bot.bus
        assert isinstance(bus, mirai.models.bus.ModelEventBus)
        
        bus.unsubscribe(event_type, callback)

    def run_sync(self):
        """运行YiriMirai"""

        # 创建新的
        loop = asyncio.new_event_loop()

        loop.run_until_complete(MiraiRunner(self.bot)._run())

    def kill(self) -> bool:
        return False
