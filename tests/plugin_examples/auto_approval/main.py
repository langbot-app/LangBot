from mirai import Mirai

import pkg.qqbot.manager
from pkg.plugin.models import *
from pkg.plugin.host import PluginHost

from mirai.models import MemberJoinRequestEvent

"""
加群自动审批
"""

__group_id__ = 1025599757
__application_contains__ = ['github', 'gitee', 'Github', 'Gitee', 'GitHub']


# 注册插件
@register(name="加群审批", description="自动审批加群申请", version="0.1", author="RockChinQ")
class AutoApproval(Plugin):

    bot: Mirai = None

    # 插件加载时触发
    def __init__(self, plugin_host: PluginHost):
        qqmgr = plugin_host.get_runtime_context().get_qqbot_manager()
        assert isinstance(qqmgr, pkg.qqbot.manager.QQBotManager)
        self.bot = qqmgr.bot

        # 向YiriMirai注册 加群申请 事件处理函数
        @qqmgr.bot.on(MemberJoinRequestEvent)
        async def process(event: MemberJoinRequestEvent):
            assert isinstance(qqmgr, pkg.qqbot.manager.QQBotManager)
            if event.group_id == __group_id__:
                if any([x in event.message for x in __application_contains__]):
                    logging.info("自动同意加群申请")
                    await qqmgr.bot.allow(event)

        self.process = process

    # 插件卸载时触发
    def __del__(self):
        # 关闭时向YiriMirai注销 加群申请 事件处理函数
        if self.bot is not None:
            self.bot.bus.unsubscribe(MemberJoinRequestEvent, self.process)
