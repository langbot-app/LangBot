from pkg.plugin.models import *
from pkg.plugin.host import EventContext, PluginHost

"""
基本命令的中文形式支持
"""


__mapping__ = {
    "帮助": "help",
    "重置": "reset",
    "前一次": "last",
    "后一次": "next",
    "会话内容": "prompt",
    "列出会话": "list",
    "重新回答": "resend",
    "使用量": "usage",
    "绘画": "draw",
    "版本": "version",
    "热重载": "reload",
    "热更新": "update",
    "配置": "cfg",
}


@register(name="CmdCN", description="命令中文支持", version="0.1", author="RockChinQ")
class CmdCnPlugin(Plugin):

    def __init__(self, plugin_host: PluginHost):
        pass

    # 私聊发送指令
    @on(PersonCommandSent)
    def person_command_sent(self, event: EventContext, **kwargs):
        cmd = kwargs['command']
        if cmd in __mapping__:

            # 返回替换后的指令
            event.add_return("alter", "!"+__mapping__[cmd]+" "+" ".join(kwargs['params']))

    # 群聊发送指令
    @on(GroupCommandSent)
    def group_command_sent(self, event: EventContext, **kwargs):
        cmd = kwargs['command']
        if cmd in __mapping__:

            # 返回替换后的指令
            event.add_return("alter", "!"+__mapping__[cmd]+" "+" ".join(kwargs['params']))

    def __del__(self):
        pass
