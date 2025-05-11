from __future__ import annotations

import typing
import os
import traceback

from ...core import app
from .. import context, events
from .. import loader
from ...utils import funcschema
from ...provider.tools import entities as tools_entities


class PluginManifestLoader(loader.PluginLoader):
    """通过插件清单发现插件"""

    _current_container: context.RuntimeContainer = None

    def __init__(self, ap: app.Application):
        super().__init__(ap)

    def handler(self, event: typing.Type[events.BaseEventModel]) -> typing.Callable[[typing.Callable], typing.Callable]:
        """注册事件处理器"""
        self.ap.logger.debug(f'注册事件处理器 {event.__name__}')

        def wrapper(func: typing.Callable) -> typing.Callable:
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

    async def load_plugins(self):
        """加载插件"""
        setattr(context, 'handler', self.handler)
        setattr(context, 'llm_func', self.llm_func)

        plugin_manifests = self.ap.discover.get_components_by_kind('Plugin')

        for plugin_manifest in plugin_manifests:
            try:
                config_schema = plugin_manifest.spec['config'] if 'config' in plugin_manifest.spec else []

                current_plugin_container = context.RuntimeContainer(
                    plugin_name=plugin_manifest.metadata.name,
                    plugin_label=plugin_manifest.metadata.label,
                    plugin_description=plugin_manifest.metadata.description,
                    plugin_version=plugin_manifest.metadata.version,
                    plugin_author=plugin_manifest.metadata.author,
                    plugin_repository=plugin_manifest.metadata.repository,
                    main_file=os.path.join(plugin_manifest.rel_dir, plugin_manifest.execution.python.path),
                    pkg_path=plugin_manifest.rel_dir,
                    config_schema=config_schema,
                    event_handlers={},
                    tools=[],
                )

                self._current_container = current_plugin_container

                # extract the plugin class
                # this step will load the plugin module,
                # so the event handlers and tools will be registered
                plugin_class = plugin_manifest.get_python_component_class()
                current_plugin_container.plugin_class = plugin_class

                # TODO load component extensions

                self.plugins.append(current_plugin_container)
            except Exception:
                self.ap.logger.error(f'加载插件 {plugin_manifest.metadata.name} 时发生错误')
                traceback.print_exc()
