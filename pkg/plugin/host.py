# 插件管理模块
import logging
import importlib
import pkgutil
import sys

import pkg.utils.context as context

__plugins__ = {}
"""{
    "example": {
        "name": "example",
        "description": "example",
        "version": "0.0.1",
        "author": "RockChinQ",
        "class": <class 'plugins.example.ExamplePlugin'>,
        "hooks": {
            "person_message": [
                <function ExamplePlugin.person_message at 0x0000020E1D1B8D38>
            ]
        },
        "instance": None
    }
}"""


def walk_plugin_path(module, prefix=''):
    """遍历插件路径"""
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            walk_plugin_path(__import__(module.__name__ + '.' + item.name, fromlist=['']), prefix + item.name + '.')
        else:
            logging.info('加载模块: {}'.format(prefix + item.name))

            importlib.import_module(module.__name__ + '.' + item.name)


def load_plugins():
    """ 加载插件 """
    logging.info("加载插件")
    PluginHost()
    walk_plugin_path(__import__('plugins'))

    logging.debug(__plugins__)


def initialize_plugins():
    """ 初始化插件 """
    logging.info("初始化插件")
    for plugin in __plugins__.values():
        try:
            plugin['instance'] = plugin["class"]()
        except:
            logging.error("插件{}初始化时发生错误: {}".format(plugin['name'], sys.exc_info()))


def unload_plugins():
    """ 卸载插件 """
    for plugin in __plugins__.values():
        if plugin['instance'] is not None:
            if not hasattr(plugin['instance'], '__del__'):
                logging.warning("插件{}没有定义析构函数".format(plugin['name']))
            else:
                try:
                    plugin['instance'].__del__()
                    logging.info("卸载插件: {}".format(plugin['name']))
                except:
                    logging.error("插件{}卸载时发生错误: {}".format(plugin['name'], sys.exc_info()))


def emit(event: str, **kwargs):
    """ 触发事件 """
    for plugin in __plugins__.values():
        for hook in plugin['hooks'].get(event, []):
            try:
                kwargs['plugin_host'] = context.get_plugin_host()
                hook(plugin['instance'], **kwargs)
            except:
                logging.error("插件{}触发事件{}时发生错误: {}".format(plugin['name'], event, sys.exc_info()))


class PluginHost:
    """插件宿主"""

    def __init__(self):
        context.set_plugin_host(self)

    def prevent_default(self):
        """阻止默认行为"""

    def get_runtime_context(self) -> context:
        """获取运行时上下文"""
        return context
