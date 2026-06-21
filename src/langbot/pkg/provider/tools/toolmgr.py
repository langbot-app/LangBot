from __future__ import annotations

import typing
import time
from typing import TYPE_CHECKING

import langbot_plugin.api.entities.builtin.resource.tool as resource_tool
from langbot_plugin.api.entities.events import pipeline_query

from . import loader as tool_loader
from .errors import ToolNotFoundError

if TYPE_CHECKING:
    from ...core import app
    from langbot.pkg.provider.tools.loaders import (
        mcp as mcp_loader,
        native as native_loader,
        plugin as plugin_loader,
        skill_authoring as skill_authoring_loader,
    )


class ToolManager:
    """LLM工具管理器"""

    ap: app.Application

    native_tool_loader: native_loader.NativeToolLoader
    plugin_tool_loader: plugin_loader.PluginToolLoader
    mcp_tool_loader: mcp_loader.MCPLoader
    skill_tool_loader: skill_authoring_loader.SkillToolLoader

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        from langbot.pkg.utils import importutil
        from langbot.pkg.provider.tools import loaders
        from langbot.pkg.provider.tools.loaders import (
            mcp as mcp_loader,
            native as native_loader,
            plugin as plugin_loader,
            skill_authoring as skill_authoring_loader,
        )

        importutil.import_modules_in_pkg(loaders)

        self.native_tool_loader = native_loader.NativeToolLoader(self.ap)
        await self.native_tool_loader.initialize()

        self.plugin_tool_loader = plugin_loader.PluginToolLoader(self.ap)
        await self.plugin_tool_loader.initialize()
        self.mcp_tool_loader = mcp_loader.MCPLoader(self.ap)
        await self.mcp_tool_loader.initialize()
        self.skill_tool_loader = skill_authoring_loader.SkillToolLoader(self.ap)
        await self.skill_tool_loader.initialize()

    async def get_all_tools(
        self,
        bound_plugins: list[str] | None = None,
        bound_mcp_servers: list[str] | None = None,
        include_mcp_resource_tools: bool = True,
    ) -> list[resource_tool.LLMTool]:
        all_functions: list[resource_tool.LLMTool] = []

        all_functions.extend(await self.native_tool_loader.get_tools())
        # Skill tools (activate / register_skill) are exposed like native tools:
        # the SkillToolLoader gates itself on sandbox + skill_mgr availability, so
        # skill is just a group of authorized tools rather than a separate
        # capability-gated surface.
        all_functions.extend(await self.skill_tool_loader.get_tools())
        all_functions.extend(await self.plugin_tool_loader.get_tools(bound_plugins))
        all_functions.extend(
            await self.mcp_tool_loader.get_tools(
                bound_mcp_servers,
                include_resource_tools=include_mcp_resource_tools,
            )
        )

        return all_functions

    async def get_tool_catalog(
        self,
        bound_plugins: list[str] | None = None,
        bound_mcp_servers: list[str] | None = None,
        include_skill_authoring: bool = False,
        include_mcp_resource_tools: bool = False,
    ) -> list[dict[str, typing.Any]]:
        catalog: list[dict[str, typing.Any]] = []

        def append_tools(source: str, source_name: str, tools: list[resource_tool.LLMTool]) -> None:
            for tool in tools:
                catalog.append(
                    {
                        'name': tool.name,
                        'description': tool.description,
                        'human_desc': tool.human_desc,
                        'parameters': tool.parameters,
                        'source': source,
                        'source_name': source_name,
                    }
                )

        append_tools('builtin', 'LangBot', await self.native_tool_loader.get_tools())
        if include_skill_authoring:
            append_tools('skill', 'LangBot', await self.skill_tool_loader.get_tools())
        catalog.extend(await self.plugin_tool_loader.get_tool_catalog(bound_plugins))

        if self.mcp_tool_loader:
            for item in await self.mcp_tool_loader.get_tool_catalog(
                bound_mcp_servers,
                include_resource_tools=include_mcp_resource_tools,
            ):
                catalog.append(item)

        return catalog

    async def get_tool_by_name(self, name: str) -> tool_loader.ToolLookupResult | None:
        """Get tool by name from any active loader."""
        for active_loader in (
            self.native_tool_loader,
            self.plugin_tool_loader,
            self.mcp_tool_loader,
            self.skill_tool_loader,
        ):
            tool = await active_loader.get_tool(name)
            if tool:
                return tool

        return None

    async def get_tool_schema(self, name: str) -> tuple[str | None, dict | None]:
        """Return (description, parameters JSON schema) for a tool by name.

        Used by the host to prefill ToolResource so a runner can build LLM tool
        definitions without a separate get_tool_detail round-trip. Handles both
        LLMTool (native/mcp/skill) and plugin ComponentManifest shapes. Returns
        (None, None) when the tool is not found.
        """
        tool = await self.get_tool_by_name(name)
        if tool is None:
            return None, None
        if hasattr(tool, 'spec') and hasattr(tool, 'metadata'):
            spec = getattr(tool, 'spec', None) or {}
            return spec.get('llm_prompt'), (spec.get('parameters') or None)
        description = getattr(tool, 'description', None) or getattr(tool, 'human_desc', None)
        return description, (getattr(tool, 'parameters', None) or None)

    async def generate_tools_for_openai(self, use_funcs: list[resource_tool.LLMTool]) -> list:
        tools = []

        for function in use_funcs:
            function_schema = {
                'type': 'function',
                'function': {
                    'name': function.name,
                    'description': function.description,
                    'parameters': function.parameters,
                },
            }
            tools.append(function_schema)

        return tools

    def _get_query_session_id(self, query: pipeline_query.Query) -> str | None:
        launcher_type = getattr(query, 'launcher_type', None)
        launcher_id = getattr(query, 'launcher_id', None)
        if launcher_type is None or launcher_id is None:
            return None

        launcher_type_value = launcher_type.value if hasattr(launcher_type, 'value') else launcher_type
        return f'{launcher_type_value}_{launcher_id}'

    async def _record_tool_call(
        self,
        *,
        name: str,
        source: str,
        parameters: dict,
        query: pipeline_query.Query,
        duration_ms: int,
        status: str,
        result: typing.Any = None,
        error_message: str | None = None,
    ) -> None:
        monitoring_service = getattr(self.ap, 'monitoring_service', None)
        if not monitoring_service:
            return

        variables = getattr(query, 'variables', {}) or {}
        message_id = variables.get('_monitoring_message_id') if isinstance(variables, dict) else None
        bot_name = variables.get('_monitoring_bot_name') if isinstance(variables, dict) else None
        pipeline_name = variables.get('_monitoring_pipeline_name') if isinstance(variables, dict) else None

        try:
            await monitoring_service.record_tool_call(
                tool_name=name,
                tool_source=source,
                duration=duration_ms,
                status=status,
                bot_id=getattr(query, 'bot_uuid', None),
                bot_name=bot_name,
                pipeline_name=pipeline_name,
                session_id=self._get_query_session_id(query),
                message_id=message_id,
                arguments=parameters,
                result=result,
                error_message=error_message,
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to record tool call: {e}')

    async def _invoke_tool_with_monitoring(
        self,
        *,
        source: str,
        name: str,
        parameters: dict,
        query: pipeline_query.Query,
        invoke: typing.Callable[[], typing.Awaitable[typing.Any]],
    ) -> typing.Any:
        start_time = time.perf_counter()
        try:
            result = await invoke()
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            await self._record_tool_call(
                name=name,
                source=source,
                parameters=parameters,
                query=query,
                duration_ms=duration_ms,
                status='error',
                error_message=str(e),
            )
            raise

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        await self._record_tool_call(
            name=name,
            source=source,
            parameters=parameters,
            query=query,
            duration_ms=duration_ms,
            status='success',
            result=result,
        )
        return result

    async def execute_func_call(self, name: str, parameters: dict, query: pipeline_query.Query) -> typing.Any:
        from langbot.pkg.telemetry import features as telemetry_features

        if await self.native_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'native')
            return await self._invoke_tool_with_monitoring(
                source='native',
                name=name,
                parameters=parameters,
                query=query,
                invoke=lambda: self.native_tool_loader.invoke_tool(name, parameters, query),
            )
        if await self.plugin_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'plugin')
            return await self._invoke_tool_with_monitoring(
                source='plugin',
                name=name,
                parameters=parameters,
                query=query,
                invoke=lambda: self.plugin_tool_loader.invoke_tool(name, parameters, query),
            )
        if await self.mcp_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'mcp')
            return await self._invoke_tool_with_monitoring(
                source='mcp',
                name=name,
                parameters=parameters,
                query=query,
                invoke=lambda: self.mcp_tool_loader.invoke_tool(name, parameters, query),
            )
        if await self.skill_tool_loader.has_tool(name):
            telemetry_features.increment(query, 'tool_calls', 'skill')
            return await self._invoke_tool_with_monitoring(
                source='skill',
                name=name,
                parameters=parameters,
                query=query,
                invoke=lambda: self.skill_tool_loader.invoke_tool(name, parameters, query),
            )
        raise ToolNotFoundError(name)

    async def shutdown(self):
        await self.native_tool_loader.shutdown()
        await self.plugin_tool_loader.shutdown()
        await self.mcp_tool_loader.shutdown()
        await self.skill_tool_loader.shutdown()
