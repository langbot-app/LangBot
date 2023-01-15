import pkg.plugin.models as models
from pkg.plugin.host import *


@models.register(name="ExamplePlugin", description="用于展示QChatGPT插件支持功能的插件", version="0.0.1", author="RockChinQ")
class ExamplePlugin(models.Plugin):

    def __init__(self):
        pass
    #
    # @models.on(models.PersonMessageReceived)
    # def on_person_message_received(self, host: PluginHost, event: EventContext, **kwargs):
    #     """收到个人消息时触发"""
    #     host.send_person_message(kwargs['sender_id'], "你好，我是一个插件")
    #     event.prevent_default()

    @models.on(models.KeySwitched)
    def on_key_switched(self, host: PluginHost, event: EventContext, **kwargs):
        """按键事件"""
        host.send_person_message(1010553892, "按键事件")

    def __del__(self):
        pass
