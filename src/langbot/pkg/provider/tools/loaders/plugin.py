from __future__ import annotations

import typing
import traceback

from langbot_plugin.api.entities.events import pipeline_query

from .. import loader
import langbot_plugin.api.entities.builtin.resource.tool as resource_tool


# @loader.loader_class('plugin-tool-loader')
class PluginToolLoader(loader.ToolLoader):
    """插件工具加载器。

    本加载器中不存储工具信息，仅负责从插件系统中获取工具信息。
    """

    async def get_tools(self, bound_plugins: list[str] | None = None) -> list[resource_tool.LLMTool]:
        # 从插件系统获取工具（内容函数）
        all_functions: list[resource_tool.LLMTool] = []

        for tool in await self.ap.plugin_connector.list_tools(bound_plugins):
            tool_obj = resource_tool.LLMTool(
                name=tool.metadata.name,
                human_desc=tool.metadata.description.en_US,
                description=tool.spec['llm_prompt'],
                parameters=tool.spec['parameters'],
                func=lambda parameters: {},
            )
            all_functions.append(tool_obj)

        return all_functions

    async def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        for tool in await self.ap.plugin_connector.list_tools():
            if tool.metadata.name == name:
                return True
        return False

    async def invoke_tool(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        try:
            return await self.ap.plugin_connector.call_tool(
                name, parameters, session=query.session, query_id=query.query_id
            )
        except Exception as e:
            self.ap.logger.error(f'执行函数 {name} 时发生错误: {e}')
            traceback.print_exc()
            return f'error occurred when executing function {name}: {e}'

    async def shutdown(self):
        """关闭工具"""
        pass
