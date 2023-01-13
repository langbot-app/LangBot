import logging

import pkg.plugin.host as host

__current_registering_plugin__ = ""

import pkg.utils.context

PersonMessage = "person_message"
GroupMessage = "group_message"
PersonNormalMessage = "person_normal_message"
PersonCommand = "person_command"
GroupNormalMessage = "group_normal_message"
GroupCommand = "group_command"
SessionFirstMessage = "session_first_message"
SessionReset = "session_reset"
SessionExpired = "session_expired"
KeyExceeded = "key_exceeded"
KeySwitched = "key_switched"


class Plugin:

    host: host.PluginHost
    """插件宿主，提供插件的一些基础功能"""

    @classmethod
    def on(cls, event):
        """事件处理器装饰器

        :param
            event: 事件类型
        :return:
            None
        """

        def wrapper(func):
            plugin_hooks = host.__plugins__[__current_registering_plugin__]["hooks"]

            if event not in plugin_hooks:
                plugin_hooks[event] = []
            plugin_hooks[event].append(func)

            host.__plugins__[__current_registering_plugin__]["hooks"] = plugin_hooks

            return func

        return wrapper


def register(name: str, description: str, version: str, author: str):
    """注册插件, 此函数作为装饰器使用

    Args:
        name (str): 插件名称
        description (str): 插件描述
        version (str): 插件版本
        author (str): 插件作者

    Returns:
        None
    """
    global __current_registering_plugin__

    __current_registering_plugin__ = name

    host.__plugins__[name] = {
        "name": name,
        "description": description,
        "version": version,
        "author": author,
        "hooks": {}
    }

    def wrapper(cls: Plugin):
        cls.name = name
        cls.description = description
        cls.version = version
        cls.author = author
        cls.host = pkg.utils.context.get_plugin_host()

        # 存到插件列表
        host.__plugins__[name]["class"] = cls

        logging.info("插件注册完成: n='{}', d='{}', v={}, a='{}' ({})".format(name, description, version, author, cls))

        return cls

    return wrapper
