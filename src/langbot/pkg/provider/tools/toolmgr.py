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


TOOL_SOURCE_REFS_QUERY_KEY = '_host_tool_source_refs'


class ToolSourceRef(typing.TypedDict):
    """Stable Host-side identity for one tool implementation."""

    source: str
    source_id: str | None


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

    async def get_resolved_tool_catalog(
        self,
        bound_plugins: list[str] | None = None,
        bound_mcp_servers: list[str] | None = None,
        include_skill_authoring: bool = True,
        include_mcp_resource_tools: bool = False,
    ) -> list[dict[str, typing.Any]]:
        """Return scoped tools with one unambiguous implementation per name.

        LLM tool calls only carry a function name. If two implementations with
        the same name remain inside the current Host scope, choosing one by
        loader or registration order would authorize one resource and execute
        another. Such names are therefore omitted until the scope is narrowed.
        """
        catalog = await self.get_tool_catalog(
            bound_plugins,
            bound_mcp_servers,
            include_skill_authoring=include_skill_authoring,
            include_mcp_resource_tools=include_mcp_resource_tools,
        )
        tools_by_name: dict[str, list[dict[str, typing.Any]]] = {}
        for item in catalog:
            name = item.get('name')
            if isinstance(name, str) and name:
                tools_by_name.setdefault(name, []).append(item)

        resolved: list[dict[str, typing.Any]] = []
        for name, candidates in tools_by_name.items():
            implementations = {
                (str(item.get('source') or ''), self._normalize_source_id(item.get('source_id'))) for item in candidates
            }
            if len(implementations) != 1:
                self.ap.logger.warning(
                    f'Tool {name} is hidden because multiple implementations are visible: '
                    f'{sorted(implementations, key=lambda item: (item[0], item[1] or ""))}'
                )
                continue
            resolved.append(candidates[0])
        return resolved

    @staticmethod
    def _normalize_source_id(source_id: typing.Any) -> str | None:
        return source_id if isinstance(source_id, str) and source_id else None

    @classmethod
    def source_ref_from_catalog_item(cls, item: dict[str, typing.Any]) -> ToolSourceRef | None:
        source = item.get('source')
        if not isinstance(source, str) or not source:
            return None
        return {
            'source': source,
            'source_id': cls._normalize_source_id(item.get('source_id')),
        }

    @classmethod
    def source_refs_from_catalog(
        cls,
        catalog: typing.Iterable[dict[str, typing.Any]],
    ) -> dict[str, ToolSourceRef]:
        refs: dict[str, ToolSourceRef] = {}
        for item in catalog:
            name = item.get('name')
            ref = cls.source_ref_from_catalog_item(item)
            if isinstance(name, str) and name and ref is not None:
                refs[name] = ref
        return refs

    @staticmethod
    def tools_from_catalog(
        catalog: typing.Iterable[dict[str, typing.Any]],
    ) -> list[resource_tool.LLMTool]:
        """Materialize LLM schemas from an already authorized Host catalog."""
        return [
            resource_tool.LLMTool(
                name=item['name'],
                human_desc=item.get('human_desc') or item.get('description') or item['name'],
                description=item.get('description') or '',
                parameters=item.get('parameters') or {},
                func=lambda parameters: {},
            )
            for item in catalog
        ]

    @classmethod
    def bind_query_tool_sources(
        cls,
        query: pipeline_query.Query,
        catalog: typing.Iterable[dict[str, typing.Any]],
    ) -> None:
        query.variables = query.variables or {}
        query.variables[TOOL_SOURCE_REFS_QUERY_KEY] = cls.source_refs_from_catalog(catalog)

    @staticmethod
    def get_query_tool_source(
        query: pipeline_query.Query,
        name: str,
    ) -> ToolSourceRef | None:
        variables = getattr(query, 'variables', None)
        if not isinstance(variables, dict):
            return None
        refs = variables.get(TOOL_SOURCE_REFS_QUERY_KEY)
        if not isinstance(refs, dict):
            return None
        ref = refs.get(name)
        if not isinstance(ref, dict):
            return None
        source = ref.get('source')
        if not isinstance(source, str) or not source:
            return None
        source_id = ref.get('source_id')
        return {
            'source': source,
            'source_id': source_id if isinstance(source_id, str) and source_id else None,
        }

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

    async def get_tool_schema(
        self,
        name: str,
        source_ref: ToolSourceRef | None = None,
    ) -> tuple[str | None, dict | None]:
        """Return (description, parameters JSON schema) for a tool by name.

        Used by the host to prefill ToolResource so a runner can build LLM tool
        definitions without a separate get_tool_detail round-trip. All loaders
        return resource_tool.LLMTool, so no per-shape branching is needed.
        Returns (None, None) when the tool is not found.
        """
        tool = await self.get_tool_by_source(name, source_ref) if source_ref else await self.get_tool_by_name(name)
        if tool is None:
            return None, None
        return tool.description, (tool.parameters or None)

    async def get_tool_detail(
        self,
        name: str,
        source_ref: ToolSourceRef | None = None,
    ) -> dict | None:
        """Return the host-level tool detail shape for a tool by name.

        All loaders return resource_tool.LLMTool, so the shape is uniform:
        {name, description, human_desc, parameters}. Returns None when the tool
        is not found.
        """
        tool = await self.get_tool_by_source(name, source_ref) if source_ref else await self.get_tool_by_name(name)
        if tool is None:
            return None
        return {
            'name': tool.name,
            'description': tool.description,
            'human_desc': tool.human_desc,
            'parameters': tool.parameters or {},
        }

    async def get_tool_by_source(
        self,
        name: str,
        source_ref: ToolSourceRef,
    ) -> tool_loader.ToolLookupResult | None:
        """Resolve a tool only from the implementation frozen at authorization."""
        source = source_ref['source']
        source_id = source_ref.get('source_id')
        if source in {'builtin', 'native'}:
            return await self.native_tool_loader.get_tool(name)
        if source == 'skill':
            return await self.skill_tool_loader.get_tool(name)
        if source == 'plugin':
            if not source_id:
                return None
            return await self.plugin_tool_loader.get_tool(name, source_id=source_id)
        if source == 'mcp':
            return await self.mcp_tool_loader.get_tool(name, source_id=source_id)
        return None

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

    async def execute_func_call(
        self,
        name: str,
        parameters: dict,
        query: pipeline_query.Query,
        source_ref: ToolSourceRef | None = None,
    ) -> typing.Any:
        from langbot.pkg.telemetry import features as telemetry_features

        source_ref = source_ref or self.get_query_tool_source(query, name)
        if source_ref is not None:
            source = source_ref['source']
            source_id = source_ref.get('source_id')
            uses_source_id = False
            if source in {'builtin', 'native'}:
                loader = self.native_tool_loader
                telemetry_source = 'native'
                exists = await loader.has_tool(name)
            elif source == 'skill':
                loader = self.skill_tool_loader
                telemetry_source = 'skill'
                exists = await loader.has_tool(name)
            elif source == 'plugin' and source_id:
                loader = self.plugin_tool_loader
                telemetry_source = 'plugin'
                uses_source_id = True
                exists = await loader.has_tool(name, source_id=source_id)
            elif source == 'mcp':
                loader = self.mcp_tool_loader
                telemetry_source = 'mcp'
                uses_source_id = True
                exists = await loader.has_tool(name, source_id=source_id)
            else:
                raise ToolNotFoundError(name)

            if not exists:
                raise ToolNotFoundError(name)

            async def invoke_selected_tool() -> typing.Any:
                if uses_source_id:
                    return await loader.invoke_tool(name, parameters, query, source_id=source_id)
                return await loader.invoke_tool(name, parameters, query)

            telemetry_features.increment(query, 'tool_calls', telemetry_source)
            return await self._invoke_tool_with_monitoring(
                source=telemetry_source,
                name=name,
                parameters=parameters,
                query=query,
                invoke=invoke_selected_tool,
            )

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
