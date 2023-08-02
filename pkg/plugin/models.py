import logging

import pkg.plugin.host as host
import pkg.utils.context

PersonMessageReceived = "person_message_received"
"""收到私聊消息时，在判断是否应该响应前触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        message_chain: mirai.models.message.MessageChain 消息链
"""

GroupMessageReceived = "group_message_received"
"""收到群聊消息时，在判断是否应该响应前触发（所有群消息）
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        message_chain: mirai.models.message.MessageChain 消息链
"""

PersonNormalMessageReceived = "person_normal_message_received"
"""判断为应该处理的私聊普通消息时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        text_message: str 消息文本
        
    returns (optional):
        alter: str 修改后的消息文本
        reply: list 回复消息组件列表
"""

PersonCommandSent = "person_command_sent"
"""判断为应该处理的私聊指令时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        command: str 指令
        params: list[str] 参数列表
        text_message: str 完整指令文本
        is_admin: bool 是否为管理员
    
    returns (optional):
        alter: str 修改后的完整指令文本
        reply: list 回复消息组件列表
"""

GroupNormalMessageReceived = "group_normal_message_received"
"""判断为应该处理的群聊普通消息时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        text_message: str 消息文本
        
    returns (optional):
        alter: str 修改后的消息文本
        reply: list 回复消息组件列表
"""

GroupCommandSent = "group_command_sent"
"""判断为应该处理的群聊指令时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        command: str 指令
        params: list[str] 参数列表
        text_message: str 完整指令文本
        is_admin: bool 是否为管理员
    
    returns (optional):
        alter: str 修改后的完整指令文本
        reply: list 回复消息组件列表
"""

NormalMessageResponded = "normal_message_responded"
"""获取到对普通消息的文字响应时触发
    kwargs:
        launcher_type: str 发起对象类型(group/person)
        launcher_id: int 发起对象ID(群号/QQ号)
        sender_id: int 发送者ID(QQ号)
        session: pkg.openai.session.Session 会话对象
        prefix: str 回复文字消息的前缀
        response_text: str 响应文本
        finish_reason: str 响应结束原因
        funcs_called: list[str] 此次响应中调用的函数列表
    
    returns (optional):
        prefix: str 修改后的回复文字消息的前缀
        reply: list 替换回复消息组件列表
"""

SessionFirstMessageReceived = "session_first_message_received"
"""会话被第一次交互时触发
    kwargs:
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
        default_prompt: str 预设值
"""

SessionExplicitReset = "session_reset"
"""会话被用户手动重置时触发，此事件不支持阻止默认行为
    kwargs:
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
"""

SessionExpired = "session_expired"
"""会话过期时触发
    kwargs:
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        session: pkg.openai.session.Session 会话对象
        session_expire_time: int 已设置的会话过期时间(秒)
"""

KeyExceeded = "key_exceeded"
"""api-key超额时触发
    kwargs:
        key_name: str 超额的api-key名称
        usage: dict 超额的api-key使用情况
        exceeded_keys: list[str] 超额的api-key列表
"""

KeySwitched = "key_switched"
"""api-key超额切换成功时触发，此事件不支持阻止默认行为
    kwargs:
        key_name: str 切换成功的api-key名称
        key_list: list[str] api-key列表
"""

PromptPreProcessing = "prompt_pre_processing"
"""每回合调用接口前对prompt进行预处理时触发，此事件不支持阻止默认行为
    kwargs:
        session_name: str 会话名称(<launcher_type>_<launcher_id>)
        default_prompt: list 此session使用的情景预设内容
        prompt: list 此session现有的prompt内容
        text_message: str 用户发送的消息文本
    
    returns (optional):
        default_prompt: list 修改后的情景预设内容
        prompt: list 修改后的prompt内容
        text_message: str 修改后的消息文本
"""


def on(*args, **kwargs):
    """注册事件监听器
    """
    return Plugin.on(*args, **kwargs)

def func(*args, **kwargs):
    """注册内容函数，声明此函数为一个内容函数，在对话中将发送此函数给GPT以供其调用
    此函数可以具有任意的参数，但必须按照[此文档](https://github.com/RockChinQ/CallingGPT/wiki/1.-Function-Format#function-format)
    所述的格式编写函数的docstring。
    此功能仅支持在使用gpt-3.5或gpt-4系列模型时使用。
    """
    return Plugin.func(*args, **kwargs)


__current_registering_plugin__ = ""


def require_ver(ge: str, le: str="v999.9.9") -> bool:
    """插件版本要求装饰器

    Args:
        ge (str): 最低版本要求
        le (str, optional): 最高版本要求

    Returns:
        bool: 是否满足要求, False时为无法获取版本号，True时为满足要求，报错为不满足要求
    """
    qchatgpt_version = ""
    
    from pkg.utils.updater import get_current_tag, compare_version_str

    try:
        qchatgpt_version = get_current_tag()  # 从updater模块获取版本号
    except:
        return False

    if compare_version_str(qchatgpt_version, ge) < 0 or \
        (compare_version_str(qchatgpt_version, le) > 0):
        raise Exception("QChatGPT 版本不满足要求，某些功能（可能是由插件提供的）无法正常使用。（要求版本：{}-{}，但当前版本：{}）".format(ge, le, qchatgpt_version))

    return True


class Plugin:
    """插件基类"""

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
        global __current_registering_plugin__

        def wrapper(func):
            plugin_hooks = host.__plugins__[__current_registering_plugin__]["hooks"]

            if event not in plugin_hooks:
                plugin_hooks[event] = []
            plugin_hooks[event].append(func)

            # print("registering hook: p='{}', e='{}', f={}".format(__current_registering_plugin__, event, func))

            host.__plugins__[__current_registering_plugin__]["hooks"] = plugin_hooks

            return func

        return wrapper

    @classmethod
    def func(cls, name: str=None):
        """内容函数装饰器
        """
        global __current_registering_plugin__
        from CallingGPT.entities.namespace import get_func_schema

        def wrapper(func):

            function_schema = get_func_schema(func)
            function_schema['name'] = __current_registering_plugin__ + '-' + (func.__name__ if name is None else name)

            function_schema['enabled'] = True

            host.__function_inst_map__[function_schema['name']] = function_schema['function']

            del function_schema['function']

            # logging.debug("registering content function: p='{}', f='{}', s={}".format(__current_registering_plugin__, func, function_schema))

            host.__callable_functions__.append(
                function_schema
            )

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
    # print("registering plugin: n='{}', d='{}', v={}, a='{}'".format(name, description, version, author))
    host.__plugins__[name] = {
        "name": name,
        "description": description,
        "version": version,
        "author": author,
        "hooks": {},
        "path": host.__current_module_path__,
        "enabled": True,
        "instance": None,
    }

    def wrapper(cls: Plugin):
        cls.name = name
        cls.description = description
        cls.version = version
        cls.author = author
        cls.host = pkg.utils.context.get_plugin_host()
        cls.enabled = True
        cls.path = host.__current_module_path__

        # 存到插件列表
        host.__plugins__[name]["class"] = cls

        logging.info("插件注册完成: n='{}', d='{}', v={}, a='{}' ({})".format(name, description, version, author, cls))

        return cls

    return wrapper
