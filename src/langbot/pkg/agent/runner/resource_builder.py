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
from . import config_schema
from .host_models import AgentEventEnvelope, AgentBinding


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

    Entry points:
    - build_resources_from_binding(event, binding, descriptor): Event-first Protocol v1
    - build_resources(query, descriptor): Legacy Query-based

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

    async def build_resources_from_binding(
        self,
        event: AgentEventEnvelope,
        binding: AgentBinding,
        descriptor: AgentRunnerDescriptor,
    ) -> AgentResources:
        """Build AgentResources from event and binding.

        This is the main entry point for Protocol v1.

        Args:
            event: Event envelope
            binding: Agent binding with resource policy
            descriptor: Runner descriptor with permissions and capabilities

        Returns:
            AgentResources dict with filtered resource lists
        """
        # Layer 1: Runner manifest permissions
        manifest_perms = descriptor.permissions

        # Layer 2: Binding resource policy
        resource_policy = binding.resource_policy

        # Layer 3: Runner instance config
        runner_config = binding.runner_config

        # Build each resource category
        models = await self._build_models_from_binding(
            manifest_perms, resource_policy, descriptor, runner_config
        )
        tools = await self._build_tools_from_binding(
            manifest_perms, resource_policy, binding
        )
        knowledge_bases = await self._build_knowledge_bases_from_binding(
            manifest_perms, resource_policy, descriptor, runner_config
        )
        storage = self._build_storage_from_binding(manifest_perms, binding)

        return {
            'models': models,
            'tools': tools,
            'knowledge_bases': knowledge_bases,
            'files': [],  # Files are populated at runtime
            'storage': storage,
            'platform_capabilities': {},  # Reserved for EBA
        }

    async def _build_models_from_binding(
        self,
        manifest_perms: dict[str, list[str]],
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> list[ModelResource]:
        """Build models list from binding."""
        models: list[ModelResource] = []
        seen_model_ids: set[str] = set()

        # Check manifest permission
        model_perms = manifest_perms.get('models', [])
        if 'invoke' not in model_perms and 'stream' not in model_perms:
            return models

        # Get model UUIDs from resource policy
        allowed_uuids = resource_policy.allowed_model_uuids

        # Add model resources from binding config schema
        await self._append_config_declared_model_resources(
            models=models,
            seen_model_ids=seen_model_ids,
            descriptor=descriptor,
            runner_config=runner_config,
        )

        # Add explicitly allowed models
        if allowed_uuids:
            for model_uuid in allowed_uuids:
                await self._append_llm_model_resource(models, seen_model_ids, model_uuid)

        return models

    async def _build_tools_from_binding(
        self,
        manifest_perms: dict[str, list[str]],
        resource_policy: typing.Any,
        binding: AgentBinding,
    ) -> list[ToolResource]:
        """Build tools list from binding."""
        tools: list[ToolResource] = []

        # Check manifest permission
        tool_perms = manifest_perms.get('tools', [])
        if 'detail' not in tool_perms and 'call' not in tool_perms:
            return tools

        # Get tool names from resource policy
        allowed_names = resource_policy.allowed_tool_names

        if allowed_names:
            for tool_name in allowed_names:
                tools.append({
                    'tool_name': tool_name,
                    'tool_type': None,
                    'description': None,
                })

        return tools

    async def _build_knowledge_bases_from_binding(
        self,
        manifest_perms: dict[str, list[str]],
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> list[KnowledgeBaseResource]:
        """Build knowledge bases list from binding."""
        kb_resources: list[KnowledgeBaseResource] = []

        # Check manifest permission
        kb_perms = manifest_perms.get('knowledge_bases', [])
        if 'list' not in kb_perms and 'retrieve' not in kb_perms:
            return kb_resources

        # Get KB UUIDs from schema-defined config fields
        kb_uuids = config_schema.extract_knowledge_base_uuids(descriptor, runner_config)

        # Also check resource policy
        allowed_uuids = resource_policy.allowed_kb_uuids
        if allowed_uuids:
            kb_uuids = allowed_uuids

        for kb_uuid in kb_uuids:
            try:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
                if kb:
                    kb_resources.append({
                        'kb_id': kb_uuid,
                        'kb_name': kb.get_name(),
                        'kb_type': kb.knowledge_base_entity.kb_type if hasattr(kb.knowledge_base_entity, 'kb_type') else None,
                    })
            except Exception as e:
                self.ap.logger.warning(f'Failed to build knowledge base resource {kb_uuid}: {e}')

        return kb_resources

    def _build_storage_from_binding(
        self,
        manifest_perms: dict[str, list[str]],
        binding: AgentBinding,
    ) -> StorageResource:
        """Build storage permissions from binding."""
        storage_perms = manifest_perms.get('storage', [])
        resource_policy = binding.resource_policy

        return {
            'plugin_storage': 'plugin' in storage_perms and resource_policy.allow_plugin_storage,
            'workspace_storage': 'workspace' in storage_perms and resource_policy.allow_workspace_storage,
        }

    async def build_resources(
        self,
        query: typing.Any,  # pipeline_query.Query
        descriptor: AgentRunnerDescriptor,
    ) -> AgentResources:
        """Build AgentResources from query and runner descriptor.

        This is a compatibility wrapper for Query-based flow.

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
            self._build_knowledge_bases(manifest_perms, runner_config, descriptor, query),
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
        for model_type, model_uuid in config_schema.iter_config_model_refs(descriptor, runner_config):
            if model_type == 'llm':
                await self._append_llm_model_resource(models, seen_model_ids, model_uuid)
            elif model_type == 'rerank':
                await self._append_rerank_model_resource(models, seen_model_ids, model_uuid)

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
        descriptor: AgentRunnerDescriptor,
        query: typing.Any,
    ) -> list[KnowledgeBaseResource]:
        """Build knowledge bases list with plugin SDK field names."""
        kb_resources: list[KnowledgeBaseResource] = []

        # Check manifest permission
        kb_perms = manifest_perms.get('knowledge_bases', [])
        if 'list' not in kb_perms and 'retrieve' not in kb_perms:
            return kb_resources

        # Get knowledge base UUIDs from schema-defined config fields.
        kb_uuids = config_schema.extract_knowledge_base_uuids(descriptor, runner_config)

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
