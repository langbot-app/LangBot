# 插件管理模块
import asyncio
import logging
import importlib
import os
import pkgutil
import sys
import shutil
import traceback

import pkg.utils.context as context
import pkg.plugin.switch as switch
import pkg.plugin.settings as settings
import pkg.qqbot.adapter as msadapter

from mirai import Mirai

__plugins__ = {}
"""插件列表

示例:
{
    "example": {
        "path": "plugins/example/main.py",
        "enabled: True,
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
}
"""

__plugins_order__ = []
"""插件顺序"""


def generate_plugin_order():
    """根据__plugin__生成插件初始顺序，无视是否启用"""
    global __plugins_order__
    __plugins_order__ = []
    for plugin_name in __plugins__:
        __plugins_order__.append(plugin_name)


def iter_plugins():
    """按照顺序迭代插件"""
    for plugin_name in __plugins_order__:
        yield __plugins__[plugin_name]


def iter_plugins_name():
    """迭代插件名"""
    for plugin_name in __plugins_order__:
        yield plugin_name


__current_module_path__ = ""


def walk_plugin_path(module, prefix='', path_prefix=''):
    global __current_module_path__
    """遍历插件路径"""
    for item in pkgutil.iter_modules(module.__path__):
        if item.ispkg:
            logging.debug("扫描插件包: plugins/{}".format(path_prefix + item.name))
            walk_plugin_path(__import__(module.__name__ + '.' + item.name, fromlist=['']),
                             prefix + item.name + '.', path_prefix + item.name + '/')
        else:
            try:
                logging.debug("扫描插件模块: plugins/{}".format(path_prefix + item.name + '.py'))
                __current_module_path__ = "plugins/"+path_prefix + item.name + '.py'

                importlib.import_module(module.__name__ + '.' + item.name)
                logging.info('加载模块: plugins/{} 成功'.format(path_prefix + item.name + '.py'))
            except:
                logging.error('加载模块: plugins/{} 失败: {}'.format(path_prefix + item.name + '.py', sys.exc_info()))
                traceback.print_exc()


def load_plugins():
    """加载插件"""
    logging.info("加载插件")
    PluginHost()
    walk_plugin_path(__import__('plugins'))

    logging.debug(__plugins__)

    # 加载开关数据
    switch.load_switch()

    # 生成初始顺序
    generate_plugin_order()
    # 加载插件顺序
    settings.load_settings()


def initialize_plugins():
    """初始化插件"""
    logging.info("初始化插件")
    import pkg.plugin.models as models
    for plugin in iter_plugins():
        # if not plugin['enabled']:
        #     continue
        try:
            models.__current_registering_plugin__ = plugin['name']
            plugin['instance'] = plugin["class"](plugin_host=context.get_plugin_host())
            logging.info("插件 {} 已初始化".format(plugin['name']))
        except:
            logging.error("插件{}初始化时发生错误: {}".format(plugin['name'], sys.exc_info()))


def unload_plugins():
    """卸载插件"""
    # 不再显式卸载插件，因为当程序结束时，插件的析构函数会被系统执行
    # for plugin in __plugins__.values():
    #     if plugin['enabled'] and plugin['instance'] is not None:
    #         if not hasattr(plugin['instance'], '__del__'):
    #             logging.warning("插件{}没有定义析构函数".format(plugin['name']))
    #         else:
    #             try:
    #                 plugin['instance'].__del__()
    #                 logging.info("卸载插件: {}".format(plugin['name']))
    #                 plugin['instance'] = None
    #             except:
    #                 logging.error("插件{}卸载时发生错误: {}".format(plugin['name'], sys.exc_info()))


def install_plugin(repo_url: str):
    """安装插件，从git储存库获取并解决依赖"""
    try:
        import pkg.utils.pkgmgr
        pkg.utils.pkgmgr.ensure_dulwich()
    except:
        pass

    try:
        import dulwich
    except ModuleNotFoundError:
        raise Exception("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")

    from dulwich import porcelain

    logging.info("克隆插件储存库: {}".format(repo_url))
    repo = porcelain.clone(repo_url, "plugins/"+repo_url.split(".git")[0].split("/")[-1]+"/", checkout=True)

    # 检查此目录是否包含requirements.txt
    if os.path.exists("plugins/"+repo_url.split(".git")[0].split("/")[-1]+"/requirements.txt"):
        logging.info("检测到requirements.txt，正在安装依赖")
        import pkg.utils.pkgmgr
        pkg.utils.pkgmgr.install_requirements("plugins/"+repo_url.split(".git")[0].split("/")[-1]+"/requirements.txt")

        import pkg.utils.log as log
        log.reset_logging()


def uninstall_plugin(plugin_name: str) -> str:
    """卸载插件"""
    if plugin_name not in __plugins__:
        raise Exception("插件不存在")
    
    # 获取文件夹路径
    plugin_path = __plugins__[plugin_name]['path'].replace("\\", "/")

    # 剪切路径为plugins/插件名
    plugin_path = plugin_path.split("plugins/")[1].split("/")[0]

    # 删除文件夹
    shutil.rmtree("plugins/"+plugin_path)
    return "plugins/"+plugin_path


class EventContext:
    """事件上下文"""
    eid = 0
    """事件编号"""

    name = ""

    __prevent_default__ = False
    """是否阻止默认行为"""

    __prevent_postorder__ = False
    """是否阻止后续插件的执行"""

    __return_value__ = {}
    """ 返回值 
    示例:
    {
        "example": [
            'value1',
            'value2',
            3,
            4,
            {
                'key1': 'value1',
            },
            ['value1', 'value2']
        ]
    }
    """

    def add_return(self, key: str, ret):
        """添加返回值"""
        if key not in self.__return_value__:
            self.__return_value__[key] = []
        self.__return_value__[key].append(ret)

    def get_return(self, key: str):
        """获取key的所有返回值"""
        if key in self.__return_value__:
            return self.__return_value__[key]
        return None

    def get_return_value(self, key: str):
        """获取key的首个返回值"""
        if key in self.__return_value__:
            return self.__return_value__[key][0]
        return None

    def prevent_default(self):
        """阻止默认行为"""
        self.__prevent_default__ = True

    def prevent_postorder(self):
        """阻止后续插件执行"""
        self.__prevent_postorder__ = True

    def is_prevented_default(self):
        """是否阻止默认行为"""
        return self.__prevent_default__

    def is_prevented_postorder(self):
        """是否阻止后序插件执行"""
        return self.__prevent_postorder__

    def __init__(self, name: str):
        self.name = name
        self.eid = EventContext.eid
        self.__prevent_default__ = False
        self.__prevent_postorder__ = False
        self.__return_value__ = {}
        EventContext.eid += 1


def emit(event_name: str, **kwargs) -> EventContext:
    """触发事件"""
    import pkg.utils.context as context
    if context.get_plugin_host() is None:
        return None
    return context.get_plugin_host().emit(event_name, **kwargs)


class PluginHost:
    """插件宿主"""

    def __init__(self):
        context.set_plugin_host(self)

    def get_runtime_context(self) -> context:
        """获取运行时上下文（pkg.utils.context模块的对象）

        此上下文用于和主程序其他模块交互（数据库、QQ机器人、OpenAI接口等）
        详见pkg.utils.context模块
        其中的context变量保存了其他重要模块的类对象，可以使用这些对象进行交互
        """
        return context

    def get_bot(self) -> Mirai:
        """获取机器人对象"""
        return context.get_qqbot_manager().bot

    def get_bot_adapter(self) -> msadapter.MessageSourceAdapter:
        """获取消息源适配器"""
        return context.get_qqbot_manager().adapter

    def send_person_message(self, person, message):
        """发送私聊消息"""
        asyncio.run(self.get_bot().send_friend_message(person, message))

    def send_group_message(self, group, message):
        """发送群消息"""
        asyncio.run(self.get_bot().send_group_message(group, message))

    def notify_admin(self, message):
        """通知管理员"""
        context.get_qqbot_manager().notify_admin(message)

    def emit(self, event_name: str, **kwargs) -> EventContext:
        """触发事件"""
        import json

        event_context = EventContext(event_name)
        logging.debug("触发事件: {} ({})".format(event_name, event_context.eid))
        for plugin in iter_plugins():
            
            if not plugin['enabled']:
                continue

            # if plugin['instance'] is None:
            #     # 从关闭状态切到开启状态之后，重新加载插件
            #     try:
            #         plugin['instance'] = plugin["class"](plugin_host=self)
            #         logging.info("插件 {} 已初始化".format(plugin['name']))
            #     except:
            #         logging.error("插件 {} 初始化时发生错误: {}".format(plugin['name'], sys.exc_info()))
            #         continue

            if 'hooks' not in plugin or event_name not in plugin['hooks']:
                continue

            hooks = []
            if event_name in plugin["hooks"]:
                hooks = plugin["hooks"][event_name]
            for hook in hooks:
                try:
                    already_prevented_default = event_context.is_prevented_default()

                    kwargs['host'] = context.get_plugin_host()
                    kwargs['event'] = event_context

                    hook(plugin['instance'], **kwargs)

                    if event_context.is_prevented_default() and not already_prevented_default:
                        logging.debug("插件 {} 已要求阻止事件 {} 的默认行为".format(plugin['name'], event_name))

                except Exception as e:
                    logging.error("插件{}触发事件{}时发生错误".format(plugin['name'], event_name))
                    logging.error(traceback.format_exc())

            # print("done:{}".format(plugin['name']))
            if event_context.is_prevented_postorder():
                logging.debug("插件 {} 阻止了后序插件的执行".format(plugin['name']))
                break

        logging.debug("事件 {} ({}) 处理完毕，返回值: {}".format(event_name, event_context.eid,
                                                                event_context.__return_value__))

        return event_context
