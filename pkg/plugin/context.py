from __future__ import annotations

import typing
import abc
import pydantic

from . import events
from ..provider.tools import entities as tools_entities
from ..core import app


def register(
    name: str,
    description: str,
    version: str,
    author: str
) -> typing.Callable[[typing.Type[BasePlugin]], typing.Type[BasePlugin]]:
    """注册插件类
    
    使用示例：

    @register(
        name="插件名称",
        description="插件描述",
        version="插件版本",
        author="插件作者"
    )
    class MyPlugin(BasePlugin):
        pass
    """
    pass

def handler(
    event: typing.Type[events.BaseEventModel]
) -> typing.Callable[[typing.Callable], typing.Callable]:
    """注册事件监听器
    
    使用示例：

    class MyPlugin(BasePlugin):
    
        @handler(NormalMessageResponded)
        async def on_normal_message_responded(self, ctx: EventContext):
            pass
    """
    pass


def llm_func(
    name: str=None,
) -> typing.Callable:
    """注册内容函数
    
    使用示例：

    class MyPlugin(BasePlugin):
    
        @llm_func("access_the_web_page")
        async def _(self, query, url: str, brief_len: int):
            \"""Call this function to search about the question before you answer any questions.
            - Do not search through google.com at any time.
            - If you need to search somthing, visit https://www.sogou.com/web?query=<something>.
            - If user ask you to open a url (start with http:// or https://), visit it directly.
            - Summary the plain content result by yourself, DO NOT directly output anything in the result you got.

            Args:
                url(str): url to visit
                brief_len(int): max length of the plain text content, recommend 1024-4096, prefer 4096

            Returns:
                str: plain text content of the web page or error message(starts with 'error:')
            \"""
    """
    pass


class BasePlugin(metaclass=abc.ABCMeta):
    """插件基类"""

    host: APIHost
    """API宿主"""

    ap: app.Application
    """应用程序对象"""

    def __init__(self, host: APIHost):
        self.host = host

    async def initialize(self):
        """初始化插件"""
        pass


class APIHost:
    """QChatGPT API 宿主"""

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        pass

    def require_ver(
        self,
        ge: str,
        le: str='v999.999.999',
    ) -> bool:
        """插件版本要求装饰器

        Args:
            ge (str): 最低版本要求
            le (str, optional): 最高版本要求

        Returns:
            bool: 是否满足要求, False时为无法获取版本号，True时为满足要求，报错为不满足要求
        """
        qchatgpt_version = ""

        try:
            qchatgpt_version = self.ap.ver_mgr.get_current_version()  # 从updater模块获取版本号
        except:
            return False

        if self.ap.ver_mgr.compare_version_str(qchatgpt_version, ge) < 0 or \
            (self.ap.ver_mgr.compare_version_str(qchatgpt_version, le) > 0):
            raise Exception("QChatGPT 版本不满足要求，某些功能（可能是由插件提供的）无法正常使用。（要求版本：{}-{}，但当前版本：{}）".format(ge, le, qchatgpt_version))

        return True


class EventContext:
    """事件上下文, 保存此次事件运行的信息"""

    eid = 0
    """事件编号"""

    host: APIHost = None
    """API宿主"""

    event: events.BaseEventModel = None
    """此次事件的对象，具体类型为handler注册时指定监听的类型，可查看events.py中的定义"""

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

    def get_return(self, key: str) -> list:
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

    def __init__(self, host: APIHost, event: events.BaseEventModel):

        self.eid = EventContext.eid
        self.host = host
        self.event = event
        self.__prevent_default__ = False
        self.__prevent_postorder__ = False
        self.__return_value__ = {}
        EventContext.eid += 1


class RuntimeContainer(pydantic.BaseModel):
    """运行时的插件容器
    
    运行期间存储单个插件的信息
    """

    plugin_name: str
    """插件名称"""

    plugin_description: str
    """插件描述"""

    plugin_version: str
    """插件版本"""

    plugin_author: str
    """插件作者"""

    plugin_source: str
    """插件源码地址"""

    main_file: str
    """插件主文件路径"""

    pkg_path: str
    """插件包路径"""

    plugin_class: typing.Type[BasePlugin] = None
    """插件类"""

    enabled: typing.Optional[bool] = True
    """是否启用"""

    priority: typing.Optional[int] = 0
    """优先级"""

    plugin_inst: typing.Optional[BasePlugin] = None
    """插件实例"""

    event_handlers: dict[typing.Type[events.BaseEventModel], typing.Callable[
        [BasePlugin, EventContext], typing.Awaitable[None]
    ]] = {}
    """事件处理器"""

    content_functions: list[tools_entities.LLMFunction] = []
    """内容函数"""

    class Config:
        arbitrary_types_allowed = True

    def to_setting_dict(self):
        return {
            'name': self.plugin_name,
            'description': self.plugin_description,
            'version': self.plugin_version,
            'author': self.plugin_author,
            'source': self.plugin_source,
            'main_file': self.main_file,
            'pkg_path': self.pkg_path,
            'priority': self.priority,
            'enabled': self.enabled,
        }

    def set_from_setting_dict(
        self,
        setting: dict
    ):
        self.plugin_source = setting['source']
        self.priority = setting['priority']
        self.enabled = setting['enabled']

        for function in self.content_functions:
            function.enable = self.enabled
