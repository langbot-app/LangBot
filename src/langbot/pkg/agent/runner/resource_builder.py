"""Agent resource builder for constructing authorized resources."""
from __future__ import annotations

import asyncio
import typing

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .context_builder import (
    AgentResources,
    ModelResource,
    ToolResource,
    KnowledgeBaseResource,
    StorageResource,
)


class AgentResourceBuilder:
    """Builder for constructing AgentResources with permission filtering.

    Responsibilities:
    - Apply 3-layer permission filtering:
        1. Runner manifest declared permissions
        2. Pipeline extensions_preference (bound plugins/MCP servers)
        3. Runner instance config selected resources
    - Build models list from authorized models
    - Build tools list from bound plugins/MCP servers
    - Build knowledge_bases list from config
    - Build storage and files permissions summary

    Note: This only builds the resource declaration. The actual proxy actions
    in handler.py must still validate against ctx.resources at runtime.

    Resource field names match the plugin SDK payload:
    - ModelResource: model_id, model_type, provider
    - ToolResource: tool_name, tool_type, description
    - KnowledgeBaseResource: kb_id, kb_name, kb_type
    - StorageResource: plugin_storage, workspace_storage
    """

    ap: app.Application

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def build_resources(
        self,
        query: typing.Any,  # pipeline_query.Query
        descriptor: AgentRunnerDescriptor,
    ) -> AgentResources:
        """Build AgentResources from query and runner descriptor.

        Args:
            query: Pipeline query with pipeline_config and variables
            descriptor: Runner descriptor with permissions and capabilities

        Returns:
            AgentResources dict with filtered resource lists
        """
        # Get bound plugins and MCP servers from query
        bound_plugins = query.variables.get('_pipeline_bound_plugins')
        bound_mcp_servers = query.variables.get('_pipeline_bound_mcp_servers')

        # Layer 1: Runner manifest permissions
        manifest_perms = descriptor.permissions

        # Layer 2: Pipeline extensions_preference (already in bound_plugins/MCP servers)
        # Layer 3: Runner instance config (from pipeline_config) - resolved via ConfigMigration
        from .config_migration import ConfigMigration
        runner_config = ConfigMigration.resolve_runner_config(query.pipeline_config, descriptor.id)

        # Build each resource category in parallel
        models, tools, knowledge_bases = await asyncio.gather(
            self._build_models(manifest_perms, runner_config, descriptor, query),
            self._build_tools(manifest_perms, bound_plugins, bound_mcp_servers, query),
            self._build_knowledge_bases(manifest_perms, runner_config, query),
        )
        storage = self._build_storage(manifest_perms)

        return {
            'models': models,
            'tools': tools,
            'knowledge_bases': knowledge_bases,
            'files': [],  # Files are populated at runtime
            'storage': storage,
            'platform_capabilities': {},  # Reserved for EBA
        }

    async def _build_models(
        self,
        manifest_perms: dict[str, list[str]],
        runner_config: dict[str, typing.Any],
        descriptor: AgentRunnerDescriptor,
        query: typing.Any,
    ) -> list[ModelResource]:
        """Build models list with plugin SDK field names."""
        models: list[ModelResource] = []
        seen_model_ids: set[str] = set()

        # Check manifest permission
        model_perms = manifest_perms.get('models', [])
        if 'invoke' not in model_perms and 'stream' not in model_perms:
            return models

        # Get model from query (preproc already resolved this)
        model_uuid = getattr(query, 'use_llm_model_uuid', None)
        if model_uuid:
            await self._append_llm_model_resource(models, seen_model_ids, model_uuid)

        # Add fallback models if present
        fallback_uuids = query.variables.get('_fallback_model_uuids', [])
        for fb_uuid in fallback_uuids:
            await self._append_llm_model_resource(models, seen_model_ids, fb_uuid)

        # Add model resources referenced by the runner binding config schema.
        # This makes authorization generic for AgentRunner plugins instead of
        # hard-coding only local-agent's primary/fallback model path.
        await self._append_config_declared_model_resources(
            models=models,
            seen_model_ids=seen_model_ids,
            descriptor=descriptor,
            runner_config=runner_config,
        )

        return models

    async def _append_config_declared_model_resources(
        self,
        models: list[ModelResource],
        seen_model_ids: set[str],
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> None:
        """Authorize model-like values selected through DynamicForm fields."""
        for item in descriptor.config_schema or []:
            if not isinstance(item, dict):
                continue

            field_name = item.get('name')
            field_type = item.get('type')
            if not field_name or field_name not in runner_config:
                continue

            value = runner_config.get(field_name)
            if field_type == 'model-fallback-selector':
                if isinstance(value, str):
                    await self._append_llm_model_resource(models, seen_model_ids, value)
                elif isinstance(value, dict):
                    primary = value.get('primary')
                    if isinstance(primary, str):
                        await self._append_llm_model_resource(models, seen_model_ids, primary)
                    fallbacks = value.get('fallbacks', [])
                    if isinstance(fallbacks, list):
                        for fallback_uuid in fallbacks:
                            if isinstance(fallback_uuid, str):
                                await self._append_llm_model_resource(models, seen_model_ids, fallback_uuid)
            elif field_type == 'llm-model-selector':
                if isinstance(value, str):
                    await self._append_llm_model_resource(models, seen_model_ids, value)
            elif field_type == 'rerank-model-selector':
                if isinstance(value, str):
                    await self._append_rerank_model_resource(models, seen_model_ids, value)

    async def _append_llm_model_resource(
        self,
        models: list[ModelResource],
        seen_model_ids: set[str],
        model_uuid: str | None,
    ) -> None:
        """Append an LLM model resource if it exists and has not been added."""
        if not model_uuid or model_uuid == '__none__' or model_uuid in seen_model_ids:
            return

        try:
            model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)
            if model and model.model_entity:
                models.append({
                    'model_id': model_uuid,
                    'model_type': getattr(model.model_entity, 'model_type', None),
                    'provider': getattr(model.provider_entity, 'name', None) if hasattr(model, 'provider_entity') else None,
                })
                seen_model_ids.add(model_uuid)
        except Exception as e:
            self.ap.logger.warning(f'Failed to build LLM model resource {model_uuid}: {e}')

    async def _append_rerank_model_resource(
        self,
        models: list[ModelResource],
        seen_model_ids: set[str],
        model_uuid: str | None,
    ) -> None:
        """Append a rerank model resource if it exists and has not been added."""
        if not model_uuid or model_uuid == '__none__' or model_uuid in seen_model_ids:
            return

        try:
            model = await self.ap.model_mgr.get_rerank_model_by_uuid(model_uuid)
            if model and model.model_entity:
                models.append({
                    'model_id': model_uuid,
                    'model_type': getattr(model.model_entity, 'model_type', 'rerank') or 'rerank',
                    'provider': getattr(model.provider_entity, 'name', None) if hasattr(model, 'provider_entity') else None,
                })
                seen_model_ids.add(model_uuid)
        except Exception as e:
            self.ap.logger.warning(f'Failed to build rerank model resource {model_uuid}: {e}')

    async def _build_tools(
        self,
        manifest_perms: dict[str, list[str]],
        bound_plugins: list[str] | None,
        bound_mcp_servers: list[str] | None,
        query: typing.Any,
    ) -> list[ToolResource]:
        """Build tools list with plugin SDK field names."""
        tools: list[ToolResource] = []

        # Check manifest permission
        tool_perms = manifest_perms.get('tools', [])
        if 'list' not in tool_perms and 'call' not in tool_perms:
            return tools

        # Get tools from query (preproc already resolved this for local-agent)
        use_funcs = getattr(query, 'use_funcs', [])
        for tool in use_funcs:
            # Use plugin SDK field names: tool_name, tool_type, description
            tools.append({
                'tool_name': tool.name,
                'tool_type': None,  # Tool type not available in current LLMTool
                'description': tool.description,
            })

        return tools

    async def _build_knowledge_bases(
        self,
        manifest_perms: dict[str, list[str]],
        runner_config: dict[str, typing.Any],
        query: typing.Any,
    ) -> list[KnowledgeBaseResource]:
        """Build knowledge bases list with plugin SDK field names."""
        kb_resources: list[KnowledgeBaseResource] = []

        # Check manifest permission
        kb_perms = manifest_perms.get('knowledge_bases', [])
        if 'list' not in kb_perms and 'retrieve' not in kb_perms:
            return kb_resources

        # Get knowledge base UUIDs from config
        kb_uuids = runner_config.get('knowledge-bases', [])
        if not kb_uuids:
            # Old single KB config
            old_kb_uuid = runner_config.get('knowledge-base', '')
            if old_kb_uuid and old_kb_uuid != '__none__':
                kb_uuids = [old_kb_uuid]

        # Also check query variables (may be modified by plugin PromptPreProcessing)
        kb_uuids_from_vars = query.variables.get('_knowledge_base_uuids', [])
        if kb_uuids_from_vars:
            kb_uuids = kb_uuids_from_vars

        for kb_uuid in kb_uuids:
            try:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
                if kb:
                    # Use plugin SDK field names: kb_id, kb_name, kb_type
                    kb_resources.append({
                        'kb_id': kb_uuid,
                        'kb_name': kb.get_name(),
                        'kb_type': kb.knowledge_base_entity.kb_type if hasattr(kb.knowledge_base_entity, 'kb_type') else None,
                    })
            except Exception as e:
                self.ap.logger.warning(f'Failed to build knowledge base resource {kb_uuid}: {e}')

        return kb_resources

    def _build_storage(
        self,
        manifest_perms: dict[str, list[str]],
    ) -> StorageResource:
        """Build storage permissions with plugin SDK field names."""
        storage_perms = manifest_perms.get('storage', [])
        return {
            'plugin_storage': 'plugin' in storage_perms,
            'workspace_storage': 'workspace' in storage_perms,
        }
