from . events import *
from . context import EventContext, APIHost as PluginHost

def emit(*args, **kwargs):
    print('插件调用了已弃用的函数 pkg.plugin.host.emit()')