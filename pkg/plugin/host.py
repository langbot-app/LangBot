# 此模块已过时
# 请从 pkg.plugin.context 引入 BasePlugin, EventContext 和 APIHost
# 最早将于 v3.4 移除此模块

from .events import *


def emit(*args, **kwargs):
    print('插件调用了已弃用的函数 pkg.plugin.host.emit()')
