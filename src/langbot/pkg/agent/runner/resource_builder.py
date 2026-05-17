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

    Resource field names match SDK v1 Protocol:
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
            self._build_models(manifest_perms, query),
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
        query: typing.Any,
    ) -> list[ModelResource]:
        """Build models list with SDK v1 field names."""
        models: list[ModelResource] = []

        # Check manifest permission
        model_perms = manifest_perms.get('models', [])
        if 'invoke' not in model_perms and 'stream' not in model_perms:
            return models

        # Get model from query (preproc already resolved this)
        model_uuid = getattr(query, 'use_llm_model_uuid', None)
        if not model_uuid:
            return models

        try:
            model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)
            if model and model.model_entity:
                models.append({
                    'model_id': model_uuid,
                    'model_type': getattr(model.model_entity, 'model_type', None),
                    'provider': getattr(model.provider_entity, 'name', None) if hasattr(model, 'provider_entity') else None,
                })
        except Exception as e:
            self.ap.logger.warning(f'Failed to build model resource {model_uuid}: {e}')

        # Add fallback models if present
        fallback_uuids = query.variables.get('_fallback_model_uuids', [])
        for fb_uuid in fallback_uuids:
            try:
                model = await self.ap.model_mgr.get_model_by_uuid(fb_uuid)
                if model and model.model_entity:
                    models.append({
                        'model_id': fb_uuid,
                        'model_type': model.model_entity.model_type,
                        'provider': model.provider_entity.name if hasattr(model, 'provider_entity') else None,
                    })
            except Exception as e:
                self.ap.logger.warning(f'Failed to build fallback model resource {fb_uuid}: {e}')

        return models

    async def _build_tools(
        self,
        manifest_perms: dict[str, list[str]],
        bound_plugins: list[str] | None,
        bound_mcp_servers: list[str] | None,
        query: typing.Any,
    ) -> list[ToolResource]:
        """Build tools list with SDK v1 field names."""
        tools: list[ToolResource] = []

        # Check manifest permission
        tool_perms = manifest_perms.get('tools', [])
        if 'list' not in tool_perms and 'call' not in tool_perms:
            return tools

        # Get tools from query (preproc already resolved this for local-agent)
        use_funcs = getattr(query, 'use_funcs', [])
        for tool in use_funcs:
            # Use SDK v1 field names: tool_name, tool_type, description
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
        """Build knowledge bases list with SDK v1 field names."""
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
                    # Use SDK v1 field names: kb_id, kb_name, kb_type
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
        """Build storage permissions with SDK v1 field names."""
        storage_perms = manifest_perms.get('storage', [])
        return {
            'plugin_storage': 'plugin' in storage_perms,
            'workspace_storage': 'workspace' in storage_perms,
        }
