from __future__ import annotations

# MessageSource的适配器
import typing
import abc

import mirai

from ..core import app


preregistered_adapters: list[typing.Type[MessageSourceAdapter]] = []

def adapter_class(
    name: str
):
    """消息平台适配器类装饰器

    Args:
        name (str): 适配器名称

    Returns:
        typing.Callable[[typing.Type[MessageSourceAdapter]], typing.Type[MessageSourceAdapter]]: 装饰器
    """
    def decorator(cls: typing.Type[MessageSourceAdapter]) -> typing.Type[MessageSourceAdapter]:
        cls.name = name
        preregistered_adapters.append(cls)
        return cls
    return decorator


class MessageSourceAdapter(metaclass=abc.ABCMeta):
    """消息平台适配器基类"""

    name: str

    bot_account_id: int
    """机器人账号ID，需要在初始化时设置"""
    
    config: dict

    ap: app.Application

    def __init__(self, config: dict, ap: app.Application):
        """初始化适配器

        Args:
            config (dict): 对应的配置
            ap (app.Application): 应用上下文
        """
        self.config = config
        self.ap = ap

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: mirai.MessageChain
    ):
        """主动发送消息
        
        Args:
            target_type (str): 目标类型，`person`或`group`
            target_id (str): 目标ID
            message (mirai.MessageChain): YiriMirai库的消息链
        """
        raise NotImplementedError

    async def reply_message(
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

    async def is_muted(self, group_id: int) -> bool:
        """获取账号是否在指定群被禁言"""
        raise NotImplementedError

    def register_listener(
        self,
        event_type: typing.Type[mirai.Event],
        callback: typing.Callable[[mirai.Event, MessageSourceAdapter], None]
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
        callback: typing.Callable[[mirai.Event, MessageSourceAdapter], None]
    ):
        """注销事件监听器
        
        Args:
            event_type (typing.Type[mirai.Event]): YiriMirai事件类型
            callback (typing.Callable[[mirai.Event], None]): 回调函数，接收一个参数，为YiriMirai事件
        """
        raise NotImplementedError

    async def run_async(self):
        """异步运行"""
        raise NotImplementedError

    async def kill(self) -> bool:
        """关闭适配器
        
        Returns:
            bool: 是否成功关闭，热重载时若此函数返回False则不会重载MessageSource底层
        """
        raise NotImplementedError


class MessageConverter:
    """消息链转换器基类"""
    @staticmethod
    def yiri2target(message_chain: mirai.MessageChain):
        """将YiriMirai消息链转换为目标消息链

        Args:
            message_chain (mirai.MessageChain): YiriMirai消息链

        Returns:
            typing.Any: 目标消息链
        """
        raise NotImplementedError

    @staticmethod
    def target2yiri(message_chain: typing.Any) -> mirai.MessageChain:
        """将目标消息链转换为YiriMirai消息链

        Args:
            message_chain (typing.Any): 目标消息链

        Returns:
            mirai.MessageChain: YiriMirai消息链
        """
        raise NotImplementedError


class EventConverter:
    """事件转换器基类"""

    @staticmethod
    def yiri2target(event: typing.Type[mirai.Event]):
        """将YiriMirai事件转换为目标事件

        Args:
            event (typing.Type[mirai.Event]): YiriMirai事件

        Returns:
            typing.Any: 目标事件
        """
        raise NotImplementedError

    @staticmethod
    def target2yiri(event: typing.Any) -> mirai.Event:
        """将目标事件的调用参数转换为YiriMirai的事件参数对象

        Args:
            event (typing.Any): 目标事件

        Returns:
            typing.Type[mirai.Event]: YiriMirai事件
        """
        raise NotImplementedError
