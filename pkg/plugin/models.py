import logging

import pkg.plugin.host as host
import pkg.utils.context

__current_registering_plugin__ = ""

PersonMessage = "person_message"
"""收到私聊消息时，在判断是否应该响应前触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        message_chain: mirai.models.message.MessageChain 消息链
"""

GroupMessage = "group_message"
"""收到群聊消息时，在判断是否应该响应前触发（所有群消息）
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        message_chain: mirai.models.message.MessageChain 消息链
"""

PersonNormalMessage = "person_normal_message"
"""判断为应该处理的私聊普通消息时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        text_message: str 消息文本
"""

PersonCommand = "person_command"
"""判断为应该处理的私聊指令时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        command: str 指令
        args: list[str] 参数列表
        text_message: str 完整指令文本
        is_admin: bool 是否为管理员
"""

GroupNormalMessage = "group_normal_message"
"""判断为应该处理的群聊普通消息时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        text_message: str 消息文本
"""

GroupCommand = "group_command"
"""判断为应该处理的群聊指令时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        command: str 指令
        args: list[str] 参数列表
        text_message: str 完整指令文本
"""

SessionFirstMessage = "session_first_message"
"""会话被第一次交互时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
        default_prompt: str 预设值
"""

SessionReset = "session_reset"
"""会话被用户手动重置时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
"""

SessionExpired = "session_expired"
"""会话过期时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
        expired_time: int 已设置的会话过期时间(秒)
"""

KeyExceeded = "key_exceeded"
"""api-key超额时触发
    kwargs:
        key_name: str 超额的api-key名称
        usage: dict 超额的api-key使用情况
        exceeded_key: list[str] 超额的api-key列表
"""

KeySwitched = "key_switched"
"""api-key超额切换成功时触发
    kwargs:
        key_name: str 切换成功的api-key名称
        key_list: list[str] api-key列表
"""


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
