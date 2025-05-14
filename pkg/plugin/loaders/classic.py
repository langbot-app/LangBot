from __future__ import annotations

import typing
import pkgutil
import importlib
import traceback

from .. import loader, events, context, models
from ...core import entities as core_entities
from ...provider.tools import entities as tools_entities
from ...utils import funcschema
from ...discover import engine as discover_engine


class PluginLoader(loader.PluginLoader):
    """加载 plugins/ 目录下的插件"""

    _current_pkg_path = ''

    _current_module_path = ''

    _current_container: context.RuntimeContainer = None

    plugins: list[context.RuntimeContainer] = []

    def __init__(self, ap):
        self.ap = ap
        self.plugins = []
        self._current_pkg_path = ''
        self._current_module_path = ''
        self._current_container = None

    async def initialize(self):
        """初始化"""

    def register(
        self, name: str, description: str, version: str, author: str
    ) -> typing.Callable[[typing.Type[context.BasePlugin]], typing.Type[context.BasePlugin]]:
        self.ap.logger.debug(f'注册插件 {name} {version} by {author}')
        container = context.RuntimeContainer(
            plugin_name=name,
            plugin_label=discover_engine.I18nString(en_US=name, zh_Hans=name),
            plugin_description=discover_engine.I18nString(en_US=description, zh_Hans=description),
            plugin_version=version,
            plugin_author=author,
            plugin_repository='',
            pkg_path=self._current_pkg_path,
            main_file=self._current_module_path,
            event_handlers={},
            tools=[],
        )

        self._current_container = container

        def wrapper(cls: context.BasePlugin) -> typing.Type[context.BasePlugin]:
            container.plugin_class = cls
            return cls

        return wrapper

    # 过时
    # 最早将于 v3.4 版本移除
    def on(self, event: typing.Type[events.BaseEventModel]) -> typing.Callable[[typing.Callable], typing.Callable]:
        """注册过时的事件处理器"""
        self.ap.logger.debug(f'注册事件处理器 {event.__name__}')

        def wrapper(func: typing.Callable) -> typing.Callable:
            async def handler(plugin: context.BasePlugin, ctx: context.EventContext) -> None:
                args = {
                    'host': ctx.host,
                    'event': ctx,
                }

                # 把 ctx.event 所有的属性都放到 args 里
                # for k, v in ctx.event.dict().items():
                #     args[k] = v
                for attr_name in ctx.event.__dict__.keys():
                    args[attr_name] = getattr(ctx.event, attr_name)

                func(plugin, **args)

            self._current_container.event_handlers[event] = handler

            return func

        return wrapper

    # 过时
    # 最早将于 v3.4 版本移除
    def func(
        self,
        name: str = None,
    ) -> typing.Callable:
        """注册过时的内容函数"""
        self.ap.logger.debug(f'注册内容函数 {name}')

        def wrapper(func: typing.Callable) -> typing.Callable:
            function_schema = funcschema.get_func_schema(func)
            function_name = self._current_container.plugin_name + '-' + (func.__name__ if name is None else name)

            async def handler(plugin: context.BasePlugin, query: core_entities.Query, *args, **kwargs):
                return func(*args, **kwargs)

            llm_function = tools_entities.LLMFunction(
                name=function_name,
                human_desc='',
                description=function_schema['description'],
                parameters=function_schema['parameters'],
                func=handler,
            )

            self._current_container.tools.append(llm_function)

            return func

        return wrapper

    def handler(self, event: typing.Type[events.BaseEventModel]) -> typing.Callable[[typing.Callable], typing.Callable]:
        """注册事件处理器"""
        self.ap.logger.debug(f'注册事件处理器 {event.__name__}')

        def wrapper(func: typing.Callable) -> typing.Callable:
            if (
                self._current_container is None
            ):  # None indicates this plugin is registered through manifest, so ignore it here
                return func

            self._current_container.event_handlers[event] = func

            return func

        return wrapper

    def llm_func(
        self,
        name: str = None,
    ) -> typing.Callable:
        """注册内容函数"""
        self.ap.logger.debug(f'注册内容函数 {name}')

        def wrapper(func: typing.Callable) -> typing.Callable:
            if (
                self._current_container is None
            ):  # None indicates this plugin is registered through manifest, so ignore it here
                return func

            function_schema = funcschema.get_func_schema(func)
            function_name = self._current_container.plugin_name + '-' + (func.__name__ if name is None else name)

            llm_function = tools_entities.LLMFunction(
                name=function_name,
                human_desc='',
                description=function_schema['description'],
                parameters=function_schema['parameters'],
                func=func,
            )

            self._current_container.tools.append(llm_function)

            return func

        return wrapper

    async def _walk_plugin_path(self, module, prefix='', path_prefix=''):
        """遍历插件路径"""
        for item in pkgutil.iter_modules(module.__path__):
            if item.ispkg:
                await self._walk_plugin_path(
                    __import__(module.__name__ + '.' + item.name, fromlist=['']),
                    prefix + item.name + '.',
                    path_prefix + item.name + '/',
                )
            else:
                try:
                    self._current_pkg_path = 'plugins/' + path_prefix
                    self._current_module_path = 'plugins/' + path_prefix + item.name + '.py'

                    self._current_container = None

                    importlib.import_module(module.__name__ + '.' + item.name)

                    if self._current_container is not None:
                        self.plugins.append(self._current_container)
                        self.ap.logger.debug(f'插件 {self._current_container} 已加载')
                except Exception:
                    self.ap.logger.error(f'加载插件模块 {prefix + item.name} 时发生错误')
                    traceback.print_exc()

    async def load_plugins(self):
        """加载插件"""
        setattr(models, 'register', self.register)
        setattr(models, 'on', self.on)
        setattr(models, 'func', self.func)

        setattr(context, 'register', self.register)
        setattr(context, 'handler', self.handler)
        setattr(context, 'llm_func', self.llm_func)
        await self._walk_plugin_path(__import__('plugins', fromlist=['']))
