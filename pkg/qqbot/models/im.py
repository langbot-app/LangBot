# IM 框架调用的抽象层
from mirai import MessageChain, Event


class AbstractIM:
    """IM框架抽象模型"""
    def __init__(self):
        raise NotImplementedError

    def run(self):
        """启动IM框架接口, 阻塞方法"""
        raise NotImplementedError

    def __send_private_msg__(self, user, msg: MessageChain):
        """发送私聊消息"""
        raise NotImplementedError

    def send_private_msg(self, user, msg: MessageChain):
        """发送私聊消息, 供上层调用, 解决兼容性问题后再调用__send_private_msg__, 请勿重写此方法"""
        return self.__send_private_msg__(user, self.message_chain_convertor(msg))

    def __send_group_msg__(self, group, msg: MessageChain):
        """发送群消息"""
        raise NotImplementedError

    def send_group_msg(self, group, msg: MessageChain):
        """发送群消息, 供上层调用, 解决兼容性问题后再调用__send_group_msg__, 请勿重写此方法"""
        return self.__send_group_msg__(group, self.message_chain_convertor(msg))

    def __register_handler__(self, event, handler):
        """注册事件处理器"""
        raise NotImplementedError

    def register_handler(self, event: Event, handler):
        """注册事件处理器, 供上层调用, 解决兼容性问题后再调用__register_handler__, 请勿重写此方法"""
        return self.register_handler(self.event_convertor(event), handler)

    def event_convertor(self, event: Event):
        """事件转换器"""
        raise NotImplementedError

    def message_chain_convertor(self, msg: MessageChain):
        """消息链转换器"""
        raise NotImplementedError

    def get_bot_instance(self):
        """获取IM框架机器人实例"""
        raise NotImplementedError

