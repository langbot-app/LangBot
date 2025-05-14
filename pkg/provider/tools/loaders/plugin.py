from __future__ import annotations

import typing
import traceback

from .. import loader, entities as tools_entities
from ....core import entities as core_entities
from ....plugin import context as plugin_context


@loader.loader_class('plugin-tool-loader')
class PluginToolLoader(loader.ToolLoader):
    """插件工具加载器。

    本加载器中不存储工具信息，仅负责从插件系统中获取工具信息。
    """

    async def get_tools(self, enabled: bool = True) -> list[tools_entities.LLMFunction]:
        # 从插件系统获取工具（内容函数）
        all_functions: list[tools_entities.LLMFunction] = []

        for plugin in self.ap.plugin_mgr.plugins(
            enabled=enabled, status=plugin_context.RuntimeContainerStatus.INITIALIZED
        ):
            all_functions.extend(plugin.tools)

        return all_functions

    async def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        for plugin in self.ap.plugin_mgr.plugins(
            enabled=True, status=plugin_context.RuntimeContainerStatus.INITIALIZED
        ):
            for function in plugin.tools:
                if function.name == name:
                    return True
        return False

    async def _get_function_and_plugin(
        self, name: str
    ) -> typing.Tuple[tools_entities.LLMFunction, plugin_context.BasePlugin]:
        """获取函数和插件实例"""
        for plugin in self.ap.plugin_mgr.plugins(
            enabled=True, status=plugin_context.RuntimeContainerStatus.INITIALIZED
        ):
            for function in plugin.tools:
                if function.name == name:
                    return function, plugin.plugin_inst
        return None, None

    async def invoke_tool(self, query: core_entities.Query, name: str, parameters: dict) -> typing.Any:
        try:
            function, plugin = await self._get_function_and_plugin(name)
            if function is None:
                return None

            parameters = parameters.copy()

            parameters = {'query': query, **parameters}

            return await function.func(plugin, **parameters)
        except Exception as e:
            self.ap.logger.error(f'执行函数 {name} 时发生错误: {e}')
            traceback.print_exc()
            return f'error occurred when executing function {name}: {e}'
        finally:
            plugin = None

            for p in self.ap.plugin_mgr.plugins():
                if function in p.tools:
                    plugin = p
                    break

            # TODO statistics

    async def shutdown(self):
        """关闭工具"""
        pass
