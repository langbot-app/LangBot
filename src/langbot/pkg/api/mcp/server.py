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
        mcp = self.mcp

        # ----- System (read-only) -------------------------------------- #
        @mcp.tool(description='Get basic LangBot system/runtime information (version, edition).')
        async def get_system_info() -> str:
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

        # ----- Bots ---------------------------------------------------- #
        @mcp.tool(description='List all messaging-platform bots. Secrets are redacted.')
        async def list_bots() -> str:
            return _dump(await ap.bot_service.get_bots(include_secret=False))

        @mcp.tool(description='Get a single bot by its UUID. Secrets are redacted.')
        async def get_bot(bot_uuid: str) -> str:
            return _dump(await ap.bot_service.get_bot(bot_uuid, include_secret=False))

        @mcp.tool(
            description=(
                'Create a bot. `bot_data` is a JSON object matching the LangBot '
                'POST /api/v1/platform/bots body (e.g. name, adapter, config). '
                'Returns the new bot UUID.'
            )
        )
        async def create_bot(bot_data: dict) -> str:
            return _dump({'uuid': await ap.bot_service.create_bot(bot_data)})

        @mcp.tool(description='Update a bot by UUID. `bot_data` matches the PUT bot body.')
        async def update_bot(bot_uuid: str, bot_data: dict) -> str:
            await ap.bot_service.update_bot(bot_uuid, bot_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete a bot by UUID.')
        async def delete_bot(bot_uuid: str) -> str:
            await ap.bot_service.delete_bot(bot_uuid)
            return _dump({'ok': True})

        # ----- Pipelines ----------------------------------------------- #
        @mcp.tool(description='List all pipelines.')
        async def list_pipelines() -> str:
            return _dump(await ap.pipeline_service.get_pipelines())

        @mcp.tool(description='Get a single pipeline by UUID.')
        async def get_pipeline(pipeline_uuid: str) -> str:
            return _dump(await ap.pipeline_service.get_pipeline(pipeline_uuid))

        @mcp.tool(
            description=(
                'Create a pipeline. `pipeline_data` matches the LangBot POST '
                '/api/v1/pipelines body. Returns the new pipeline UUID.'
            )
        )
        async def create_pipeline(pipeline_data: dict) -> str:
            return _dump({'uuid': await ap.pipeline_service.create_pipeline(pipeline_data)})

        @mcp.tool(description='Update a pipeline by UUID. `pipeline_data` matches the PUT body.')
        async def update_pipeline(pipeline_uuid: str, pipeline_data: dict) -> str:
            await ap.pipeline_service.update_pipeline(pipeline_uuid, pipeline_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete a pipeline by UUID.')
        async def delete_pipeline(pipeline_uuid: str) -> str:
            await ap.pipeline_service.delete_pipeline(pipeline_uuid)
            return _dump({'ok': True})

        # ----- Agents -------------------------------------------------- #
        @mcp.tool(description='List product-level processors, including Agents and Pipelines.')
        async def list_agents() -> str:
            return _dump(await ap.agent_service.get_agents())

        @mcp.tool(description='Get a product-level Agent or Pipeline by UUID.')
        async def get_agent(agent_uuid: str) -> str:
            return _dump(await ap.agent_service.get_agent(agent_uuid))

        @mcp.tool(
            description=(
                'Create an Agent processor or Pipeline. `agent_data` matches '
                'POST /api/v1/agents; set kind to `agent` or `pipeline`. Returns the new UUID and kind.'
            )
        )
        async def create_agent(agent_data: dict) -> str:
            return _dump(await ap.agent_service.create_agent(agent_data))

        @mcp.tool(description='Update an Agent processor or Pipeline by UUID.')
        async def update_agent(agent_uuid: str, agent_data: dict) -> str:
            await ap.agent_service.update_agent(agent_uuid, agent_data)
            return _dump({'ok': True})

        @mcp.tool(description='Delete an Agent processor or Pipeline by UUID.')
        async def delete_agent(agent_uuid: str) -> str:
            await ap.agent_service.delete_agent(agent_uuid)
            return _dump({'ok': True})

        # ----- Models -------------------------------------------------- #
        @mcp.tool(description='List all configured LLM models. Secrets are redacted.')
        async def list_llm_models() -> str:
            return _dump(await ap.llm_model_service.get_llm_models(include_secret=False))

        @mcp.tool(description='Get a single LLM model by UUID.')
        async def get_llm_model(model_uuid: str) -> str:
            return _dump(await ap.llm_model_service.get_llm_model(model_uuid))

        @mcp.tool(description='List all configured embedding models.')
        async def list_embedding_models() -> str:
            return _dump(await ap.embedding_models_service.get_embedding_models())

        @mcp.tool(description='List all model providers (OpenAI-compatible, Anthropic, etc.).')
        async def list_model_providers() -> str:
            return _dump(await ap.provider_service.get_providers())

        # ----- Knowledge bases ----------------------------------------- #
        @mcp.tool(description='List all knowledge bases (RAG).')
        async def list_knowledge_bases() -> str:
            return _dump(await ap.knowledge_service.get_knowledge_bases())

        @mcp.tool(description='Get a single knowledge base by UUID.')
        async def get_knowledge_base(kb_uuid: str) -> str:
            return _dump(await ap.knowledge_service.get_knowledge_base(kb_uuid))

        @mcp.tool(
            description=('Retrieve (semantic search) from a knowledge base. Returns the matched chunks for `query`.')
        )
        async def retrieve_knowledge_base(kb_uuid: str, query: str) -> str:
            return _dump(await ap.knowledge_service.retrieve_knowledge_base(kb_uuid, query))

        # ----- MCP servers (LangBot as MCP client) --------------------- #
        @mcp.tool(
            description=(
                'List external MCP servers registered in LangBot (the servers LangBot itself connects to as a client).'
            )
        )
        async def list_mcp_servers() -> str:
            return _dump(await ap.mcp_service.get_mcp_servers())

        # ----- Skills -------------------------------------------------- #
        @mcp.tool(description='List installed skills.')
        async def list_skills() -> str:
            return _dump(await ap.skill_service.list_skills())

        @mcp.tool(description='Get a single skill by name.')
        async def get_skill(skill_name: str) -> str:
            return _dump(await ap.skill_service.get_skill(skill_name))

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
