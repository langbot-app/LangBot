"""LangBot MCP server definition.

Wraps a curated subset of LangBot's HTTP service API as MCP tools. Tools call
the existing service layer directly (not the HTTP API over the network), so the
MCP surface stays aligned with the API by construction.

IMPORTANT: when you add, remove, or change an HTTP API endpoint that should be
agent-accessible, update the corresponding MCP tool here AND the skills under
``skills/`` (see AGENTS.md). The MCP tool surface and the API must stay aligned.

Scope (first version): core read operations plus the most common writes for
bots, pipelines, LLM/embedding models, knowledge bases, MCP servers, skills,
and read-only system info. This intentionally does NOT expose every one of the
~25 HTTP route groups — that keeps the agent surface small, safe, and
maintainable. Extend deliberately.
"""

from __future__ import annotations

import json
import typing

from mcp.server.fastmcp import FastMCP

from ..http.authz import Permission, require_permission
from .context import get_request_context

if typing.TYPE_CHECKING:
    from ...core import app as app_module


INSTRUCTIONS = """\
This MCP server manages a LangBot instance. LangBot is an LLM-native instant
messaging bot platform. Use these tools to inspect and manage bots, agents, pipelines,
models, knowledge bases, MCP servers, and skills.

Authentication uses a LangBot API key (web-UI-created `lbk_...` key or the
global API key from config.yaml), passed as the `X-API-Key` header or
`Authorization: Bearer <key>`.

Prefer the `list_*` / `get_*` tools to discover resources before mutating. All
identifiers are UUIDs unless noted. Mutating tools take JSON objects matching
the same shape as the LangBot HTTP API request bodies.
"""


def _dump(value: typing.Any) -> str:
    """Serialize a tool result to a compact JSON string for the agent."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _authorized(permission: Permission):
    context = get_request_context()
    require_permission(context, permission)
    return context


class LangBotMCPServer:
    """Builds and owns the FastMCP instance for LangBot."""

    def __init__(self, ap: app_module.Application) -> None:
        self.ap = ap
        # Stateless HTTP so the server does not need sticky sessions behind a
        # load balancer; json_response keeps responses simple (no SSE stream
        # required for unary tool calls).
        self.mcp = FastMCP(
            name='LangBot',
            instructions=INSTRUCTIONS,
            stateless_http=True,
            json_response=True,
        )
        self._register_tools()

    # ------------------------------------------------------------------ #
    # Tool registration
    # ------------------------------------------------------------------ #
    def _register_tools(self) -> None:
        ap = self.ap
        mcp = self

        # ----- System (read-only) -------------------------------------- #
        @mcp.tool(description='Get basic LangBot system/runtime information (version, edition).')
        async def get_system_info() -> str:
            _authorized(Permission.WORKSPACE_VIEW)
            version = None
            try:
                version = ap.ver_mgr.get_current_version()
            except Exception:
                pass
            data = {
                'version': version,
                'edition': ap.instance_config.data.get('system', {}).get('edition'),
                'instance_id': ap.instance_config.data.get('system', {}).get('instance_id'),
            }
            return _dump(data)

        @mcp.tool(description='List knowledge engines and their capabilities.')
        async def list_knowledge_engines() -> str:
            return _dump(await ap.knowledge_service.list_knowledge_engines(_authorized(Permission.RESOURCE_VIEW)))

        @mcp.tool(description='Get creation or retrieval schema for an author/name knowledge engine.')
        async def get_knowledge_engine_schema(plugin_id: str, kind: typing.Literal['creation', 'retrieval']) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            if kind == 'creation':
                return _dump(await ap.knowledge_service.get_engine_creation_schema(context, plugin_id))
            return _dump(await ap.knowledge_service.get_engine_retrieval_schema(context, plugin_id))

        @mcp.tool(description='List document parsers, optionally filtered by MIME type.')
        async def list_knowledge_parsers(mime_type: str | None = None) -> str:
            return _dump(await ap.knowledge_service.list_parsers(_authorized(Permission.RESOURCE_VIEW), mime_type))

        @mcp.tool(description='Read Pipeline extension bindings, enable-all switches and available extensions.')
        async def get_pipeline_extensions(pipeline_uuid: str) -> str:
            return _dump(
                await ap.pipeline_service.get_pipeline_extensions(_authorized(Permission.RESOURCE_VIEW), pipeline_uuid)
            )

        @mcp.tool(description='Replace all Pipeline extension bindings. All binding lists and switches are required.')
        async def update_pipeline_extensions(
            pipeline_uuid: str,
            bound_plugins: list[dict],
            bound_mcp_servers: list[str],
            bound_skills: list[str],
            bound_mcp_resources: list[dict],
            enable_all_plugins: bool,
            enable_all_mcp_servers: bool,
            enable_all_skills: bool,
            mcp_resource_agent_read_enabled: bool,
        ) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            require_permission(context, Permission.RESOURCE_VIEW)
            await ap.pipeline_service.update_pipeline_extensions(
                context,
                pipeline_uuid,
                bound_plugins,
                bound_mcp_servers,
                enable_all_plugins,
                enable_all_mcp_servers,
                bound_skills,
                enable_all_skills,
                bound_mcp_resources,
                mcp_resource_agent_read_enabled,
            )
            return _dump(await ap.pipeline_service.get_pipeline_extensions(context, pipeline_uuid))

        @mcp.tool(
            description='Run one Pipeline turn in a fresh session. Calls configured models/tools. Never retry an unknown outcome automatically.'
        )
        async def run_pipeline(pipeline_uuid: str, message: str) -> str:
            from ..http.service.pipeline_run import run_pipeline as execute

            return _dump(await execute(ap, _authorized(Permission.RUNTIME_OPERATE), pipeline_uuid, message))

        @mcp.tool(
            description='Read Workspace sandbox status, sessions or recent errors. Does not create execution sessions.'
        )
        async def get_sandbox_diagnostics(kind: typing.Literal['status', 'sessions', 'errors'] = 'status') -> str:
            context = _authorized(Permission.RESOURCE_VIEW if kind == 'status' else Permission.AUDIT_VIEW)
            if kind == 'status':
                return _dump(await ap.box_service.get_status(context))
            if kind == 'sessions':
                return _dump(await ap.box_service.get_sessions(context))
            if ap.box_service.managed_admission_required:
                await ap.box_service.require_workspace_sandbox(context)
            return _dump(ap.box_service.get_recent_errors(context))

        @mcp.tool(
            description='Read bounded Workspace runtime records. Filters follow the monitoring service: bot_ids, pipeline_ids, session_ids, start_time, end_time, knowledge_base_id, user_query, is_active as supported by the record kind.'
        )
        async def get_monitoring_records(
            kind: typing.Literal['messages', 'llm_calls', 'tool_calls', 'embedding_calls', 'sessions', 'errors'],
            limit: int = 100,
            offset: int = 0,
            filters: dict | None = None,
        ) -> str:
            import datetime

            context = _authorized(Permission.RESOURCE_VIEW)
            allowed = {'start_time', 'end_time'}
            if kind != 'embedding_calls':
                allowed |= {'bot_ids', 'pipeline_ids'}
            if kind in {'messages', 'tool_calls'}:
                allowed.add('session_ids')
            if kind == 'embedding_calls':
                allowed.add('knowledge_base_id')
            if kind == 'sessions':
                allowed |= {'user_query', 'is_active'}
            kwargs = dict(filters or {})
            if set(kwargs) - allowed:
                raise ValueError('Unsupported monitoring filter')
            for field in ('start_time', 'end_time'):
                if kwargs.get(field):
                    value = datetime.datetime.fromisoformat(kwargs[field].replace('Z', '+00:00'))
                    if value.tzinfo is not None:
                        value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    kwargs[field] = value
            limit, offset = ap.monitoring_service.normalize_page_window(limit, offset)
            rows, total = await getattr(ap.monitoring_service, 'get_' + kind)(
                context, limit=limit, offset=offset, **kwargs
            )
            return _dump({kind: rows, 'total': total, 'limit': limit, 'offset': offset})

        @mcp.tool(description='Read message details or session analysis within the authenticated Workspace.')
        async def get_monitoring_details(kind: typing.Literal['message', 'session'], identifier: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            if kind == 'message':
                return _dump(await ap.monitoring_service.get_message_details(context, identifier))
            return _dump(await ap.monitoring_service.get_session_analysis(context, identifier))

        # ----- Bots ---------------------------------------------------- #
        @mcp.tool(description='List all messaging-platform bots. Secrets are redacted.')
        async def list_bots() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.bot_service.get_bots(context, include_secret=False))

        @mcp.tool(description='Get a single bot by its UUID. Secrets are redacted.')
        async def get_bot(bot_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.bot_service.get_bot(context, bot_uuid, include_secret=False))

        @mcp.tool(
            description=(
                'Create a bot. `bot_data` is a JSON object matching the LangBot '
                'POST /api/v1/platform/bots body (e.g. name, adapter, config). '
                'Use event_bindings for exclusive Agent/Pipeline routes; plugin_processors is an array '
                'of {processor_uuid, enabled} subscriptions that automatically match Runner-declared events. '
                'Subscriptions run independently of each other and of event_bindings. Returns the new bot UUID.'
            )
        )
        async def create_bot(bot_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            return _dump({'uuid': await ap.bot_service.create_bot(context, bot_data)})

        @mcp.tool(
            description=(
                'Update a bot by UUID. `bot_data` matches the PUT bot body. '
                'plugin_processors replaces the bot subscriptions with [{processor_uuid, enabled}]. '
                'Do not put event_processor targets in event_bindings; those are exclusive Agent/Pipeline routes.'
            )
        )
        async def update_bot(bot_uuid: str, bot_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.bot_service.update_bot(context, bot_uuid, bot_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete a bot by UUID.')
        async def delete_bot(bot_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.bot_service.delete_bot(context, bot_uuid)
            return _dump({'ok': True})

        @mcp.tool(description='List recent runtime route status for a bot event route table.')
        async def list_bot_event_route_statuses(bot_uuid: str) -> str:
            return _dump(await ap.bot_service.list_event_route_statuses(bot_uuid))

        # ----- Pipelines ----------------------------------------------- #
        @mcp.tool(description='List all pipelines.')
        async def list_pipelines() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.pipeline_service.get_pipelines(context))

        @mcp.tool(description='Get a single pipeline by UUID.')
        async def get_pipeline(pipeline_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.pipeline_service.get_pipeline(context, pipeline_uuid))

        @mcp.tool(
            description=(
                'Create a pipeline. `pipeline_data` matches the LangBot POST '
                '/api/v1/pipelines body. Returns the new pipeline UUID.'
            )
        )
        async def create_pipeline(pipeline_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            create_as_default = pipeline_data.get('is_default') is True
            return _dump(
                {
                    'uuid': await ap.pipeline_service.create_pipeline(
                        context,
                        pipeline_data,
                        default=create_as_default,
                    )
                }
            )

        @mcp.tool(description='Update a pipeline by UUID. `pipeline_data` matches the PUT body.')
        async def update_pipeline(pipeline_uuid: str, pipeline_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.pipeline_service.update_pipeline(context, pipeline_uuid, pipeline_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete a pipeline by UUID.')
        async def delete_pipeline(pipeline_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.pipeline_service.delete_pipeline(context, pipeline_uuid)
            return _dump({'ok': True})

        # ----- Processors ---------------------------------------------- #
        @mcp.tool(description='List product-level processors, including Agents, Pipelines and Event processors.')
        async def list_processors() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.agent_service.get_agents(context))

        @mcp.tool(description='Get an Agent, Pipeline or Event processor by UUID.')
        async def get_processor(processor_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.agent_service.get_agent(context, processor_uuid))

        @mcp.tool(
            description=(
                'Create an Agent, Pipeline or Event processor. Set `processor_data.kind` to '
                '`agent`, `pipeline` or `event_processor`. Event processors may be created without a component; '
                'then use update_processor with an installed component_ref from get_processor_metadata and optional '
                'parameters. Unconfigured instances support no events. Returns UUID and kind.'
            )
        )
        async def create_processor(processor_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            return _dump(await ap.agent_service.create_agent(context, processor_data))

        @mcp.tool(description='Update an Agent, Pipeline or Event processor by UUID.')
        async def update_processor(processor_uuid: str, processor_data: dict) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.agent_service.update_agent(context, processor_uuid, processor_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete an Agent, Pipeline or Event processor by UUID.')
        async def delete_processor(processor_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_MANAGE)
            await ap.agent_service.delete_agent(context, processor_uuid)
            return _dump({'ok': True})

        @mcp.tool(
            description='Get processor kinds and installed event-capable Runner components with configuration schemas.'
        )
        async def get_processor_metadata() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.agent_service.get_agent_metadata(context))

        @mcp.tool(
            description='List one Agent or plugin processor run history; use before_id to page older runs. '
            'created_at_ms, started_at_ms and finished_at_ms are Host lifecycle times in epoch milliseconds.'
        )
        async def list_processor_runs(processor_uuid: str, before_id: int | None = None) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.agent_service.get_processor_runs(context, processor_uuid, before_id=before_id))

        @mcp.tool(
            description='Read logs and action results for an Agent or plugin processor run; page using after_sequence.'
        )
        async def get_processor_run_events(
            processor_uuid: str,
            run_id: str,
            after_sequence: int | None = None,
        ) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(
                await ap.agent_service.get_processor_run_events(
                    context,
                    processor_uuid,
                    run_id,
                    after_sequence=after_sequence,
                )
            )

        # ----- Models -------------------------------------------------- #
        @mcp.tool(
            description=(
                'Run a synthetic event against an Agent or Event processor without platform delivery. '
                'Returns final text and execution_events containing reported messages/thinking and tool calls. '
                'Platform tools use mock adapters; other tools execute normally. '
                'For Event processors, data contains the complete typed event fields. '
                'Requires runtime.operate; payload accepts event_type, text, data, conversation_id, actor, subject and '
                'mock (errors/results keyed by platform tool name; unsupported_apis lists unavailable platform APIs).'
            )
        )
        async def debug_agent(processor_uuid: str, payload: dict) -> str:
            context = _authorized(Permission.RUNTIME_OPERATE)
            return _dump(await ap.agent_service.debug_agent(context, processor_uuid, payload))

        @mcp.tool(description='List all configured LLM models. Secrets are redacted.')
        async def list_llm_models() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.llm_model_service.get_llm_models(context, include_secret=False))

        @mcp.tool(description='Get a single LLM model by UUID.')
        async def get_llm_model(model_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.llm_model_service.get_llm_model(context, model_uuid, include_secret=False))

        @mcp.tool(description='List all configured embedding models.')
        async def list_embedding_models() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.embedding_models_service.get_embedding_models(context, include_secret=False))

        @mcp.tool(description='List all model providers (OpenAI-compatible, Anthropic, etc.).')
        async def list_model_providers() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.provider_service.get_providers(context, include_secret=False))

        # ----- Knowledge bases ----------------------------------------- #
        @mcp.tool(description='List all knowledge bases (RAG).')
        async def list_knowledge_bases() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.knowledge_service.get_knowledge_bases(context))

        @mcp.tool(description='Get a single knowledge base by UUID.')
        async def get_knowledge_base(kb_uuid: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.knowledge_service.get_knowledge_base(context, kb_uuid))

        @mcp.tool(
            description=('Retrieve (semantic search) from a knowledge base. Returns the matched chunks for `query`.')
        )
        async def retrieve_knowledge_base(kb_uuid: str, query: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.knowledge_service.retrieve_knowledge_base(context, kb_uuid, query))

        # ----- MCP servers (LangBot as MCP client) --------------------- #
        @mcp.tool(
            description=(
                'List external MCP servers registered in LangBot (the servers LangBot itself connects to as a client).'
            )
        )
        async def list_mcp_servers() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.mcp_service.get_mcp_servers(context))

        # ----- Skills -------------------------------------------------- #
        @mcp.tool(description='List installed skills.')
        async def list_skills() -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.skill_service.list_skills(context))

        @mcp.tool(description='Get a single skill by name.')
        async def get_skill(skill_name: str) -> str:
            context = _authorized(Permission.RESOURCE_VIEW)
            return _dump(await ap.skill_service.get_skill(context, skill_name))

    def tool(self, **options):
        """Register a tool boundary before its authorization and service call."""

        def register(fn):
            observed = fn
            return self.mcp.tool(**options)(observed)

        return register

    # ------------------------------------------------------------------ #
    # ASGI app
    # ------------------------------------------------------------------ #
    def streamable_http_app(self):  # type: ignore[no-untyped-def]
        """Return the Starlette ASGI app serving MCP over streamable HTTP at /mcp."""
        return self.mcp.streamable_http_app()

    @property
    def session_manager(self):  # type: ignore[no-untyped-def]
        """Expose the session manager so its lifespan can be run by the host."""
        return self.mcp.session_manager
