# MessageSource的适配器
import typing

import mirai


class MessageSourceAdapter:
    def __init__(self, config: dict):
        pass

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
        raise NotImplementedError

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
        raise NotImplementedError

    def is_muted(self, group_id: int) -> bool:
        """获取账号是否在指定群被禁言"""
        raise NotImplementedError

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
        raise NotImplementedError
    
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
        raise NotImplementedError

    def run_sync(self):
        """以阻塞的方式运行适配器"""
        raise NotImplementedError

    def kill(self) -> bool:
        """关闭适配器
        
        Returns:
            bool: 是否成功关闭，热重载时若此函数返回False则不会重载MessageSource底层
        """
        raise NotImplementedError
    