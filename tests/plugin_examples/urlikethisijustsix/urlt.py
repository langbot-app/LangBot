import random

from mirai import Plain

from pkg.plugin.models import *
from pkg.plugin.host import EventContext, PluginHost

"""
私聊或群聊消息为以下列出的一些冒犯性词语时，自动回复__random_reply__中的一句话
"""


__words__ = ['sb', "傻逼", "dinner", "操你妈", "cnm", "fuck you", "fuckyou",
             "f*ck you", "弱智", "若智", "答辩", "依托答辩", "低能儿", "nt", "脑瘫", "闹谈", "老坛"]

__random_reply__ = ['好好好', "啊对对对", "好好好好", "你说得对", "谢谢夸奖"]


@register(name="啊对对对", description="你都这样了，我就顺从你吧", version="0.1", author="RockChinQ")
class AdddPlugin(Plugin):

    def __init__(self, plugin_host: PluginHost):
        pass

    # 绑定私聊消息事件和群消息事件
    @on(PersonNormalMessageReceived)
    @on(GroupNormalMessageReceived)
    def normal_message_received(self, event: EventContext, **kwargs):
        msg = kwargs['text_message']

        # 如果消息中包含关键词
        if msg in __words__:
            # 随机一个回复
            idx = random.randint(0, len(__random_reply__)-1)

            # 返回回复的消息
            event.add_return("reply", [Plain(__random_reply__[idx])])

            # 阻止向接口获取回复
            event.prevent_default()
            event.prevent_postorder()

    def __del__(self):
        pass
