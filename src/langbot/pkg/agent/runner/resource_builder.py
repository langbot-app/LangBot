"""Agent resource builder for constructing authorized resources."""

from __future__ import annotations

import typing

from ...core import app
from .descriptor import AgentRunnerDescriptor
from .context_builder import (
    AgentResources,
    ModelResource,
    ToolResource,
    KnowledgeBaseResource,
    SkillResource,
    StorageResource,
)
from . import config_schema
from .host_models import AgentEventEnvelope, AgentBinding
from .resource_policy import ResourcePolicyProjector
from ...provider.tools.loaders.mcp import MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE
from ...provider.tools.toolmgr import ToolSourceRef


class AgentResourceBuilder:
    """Builder for constructing run-scoped AgentResources with permission filtering.

    Responsibilities:
    - Apply manifest permissions intersected with binding resource policy
    - Build models list from authorized models
    - Build tools list from bound plugins/MCP servers
    - Build knowledge_bases list from config
    - Build storage access summary

    Note: This only builds the resource declaration. The actual proxy actions
    in handler.py must still validate against ctx.resources at runtime.

    Resource field names match the plugin SDK payload:
    - ModelResource: model_id, model_type, provider
    - ToolResource: tool_name, tool_type, description
    - KnowledgeBaseResource: kb_id, kb_name, kb_type
    - SkillResource: skill_name, display_name, description
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
            descriptor: Runner descriptor with capabilities, permissions, and config schema

        Returns:
            AgentResources dict with filtered resource lists
        """
        resource_policy = binding.resource_policy
        runner_config = binding.runner_config
        manifest_perms = descriptor.permissions

        # Build each resource category
        models = await self._build_models_from_binding(manifest_perms, resource_policy, descriptor, runner_config)
        tools = await self._build_tools_from_binding(manifest_perms, resource_policy, descriptor, runner_config)
        knowledge_bases = await self._build_knowledge_bases_from_binding(
            manifest_perms, resource_policy, descriptor, runner_config
        )
        skills = self._build_skills_from_binding(resource_policy, descriptor)
        storage = self._build_storage_from_binding(manifest_perms, binding)

        return {
            'models': models,
            'tools': tools,
            'knowledge_bases': knowledge_bases,
            'skills': skills,
            'storage': storage,
            'platform_capabilities': {},  # Reserved for EBA
        }

    async def _build_models_from_binding(
        self,
        manifest_perms: typing.Any,
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> list[ModelResource]:
        """Build models list from binding."""
        models: list[ModelResource] = []
        seen_model_ids: set[str] = set()

        model_perms = set(manifest_perms.models)
        include_llm = bool({'invoke', 'stream', 'count_tokens'} & model_perms)
        include_rerank = 'rerank' in model_perms
        llm_operations = [operation for operation in ('invoke', 'stream', 'count_tokens') if operation in model_perms]
        if not include_llm and not include_rerank:
            return models

        # Get additional model UUID grants from resource policy.
        allowed_uuids = resource_policy.allowed_model_uuids

        # Add model resources from Agent/runner config schema
        await self._append_config_declared_model_resources(
            models=models,
            seen_model_ids=seen_model_ids,
            descriptor=descriptor,
            runner_config=runner_config,
            include_llm=include_llm,
            include_rerank=include_rerank,
            llm_operations=llm_operations,
        )

        # Add explicitly allowed models
        if allowed_uuids and include_llm:
            for model_uuid in allowed_uuids:
                await self._append_llm_model_resource(models, seen_model_ids, model_uuid, llm_operations)

        return models

    async def _build_tools_from_binding(
        self,
        manifest_perms: typing.Any,
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> list[ToolResource]:
        """Build tools list from binding."""
        tools: list[ToolResource] = []
        tool_perms = set(manifest_perms.tools)
        if not ({'detail', 'call'} & tool_perms):
            return tools

        if not config_schema.uses_host_tools(descriptor):
            return tools

        allowed_names = resource_policy.allowed_tool_names
        allowed_sources = resource_policy.allowed_tool_sources
        if resource_policy.allow_all_tools or allowed_sources is None:
            get_catalog = getattr(getattr(self.ap, 'tool_mgr', None), 'get_resolved_tool_catalog', None)
            if get_catalog is None:
                return tools
            try:
                catalog = await get_catalog(
                    include_skill_authoring=True,
                    include_mcp_resource_tools=True,
                )
            except Exception as e:
                self.ap.logger.warning(f'Failed to resolve visible Host tools: {e}')
                return tools

            if not resource_policy.allow_all_tools:
                selected_names = set(allowed_names or [])
                catalog = [item for item in catalog if item.get('name') in selected_names]
            allowed_names = ResourcePolicyProjector.extract_tool_names(catalog)
            allowed_sources = {
                item['name']: ref for item in catalog if (ref := self._catalog_source_ref(item)) is not None
            }

        if runner_config.get('mcp-resource-agent-read-enabled', True) is not True:
            denied_resource_tools = {MCP_TOOL_LIST_RESOURCES, MCP_TOOL_READ_RESOURCE}
            allowed_names = [
                name
                for name in (allowed_names or [])
                if not (
                    name in denied_resource_tools
                    and allowed_sources
                    and (source_ref := allowed_sources.get(name)) is not None
                    and source_ref['source'] == 'mcp'
                    and source_ref.get('source_id') is None
                )
            ]

        tool_operations = [operation for operation in ('detail', 'call') if operation in tool_perms]

        # Prefill full tool schema (best-effort) so runners can build LLM tool
        # definitions without a per-tool get_tool_detail round-trip. Degrades to
        # None when no tool manager is available.
        get_tool_schema = getattr(getattr(self.ap, 'tool_mgr', None), 'get_tool_schema', None)
        if allowed_names:
            for tool_name in allowed_names:
                source_ref = allowed_sources.get(tool_name) if allowed_sources else None
                if source_ref is None:
                    self.ap.logger.warning(f'Tool {tool_name} is not authorized because its Host source is unresolved')
                    continue
                if get_tool_schema is not None:
                    description, parameters = await get_tool_schema(tool_name, source_ref=source_ref)
                else:
                    description, parameters = None, None
                tools.append(
                    {
                        'tool_name': tool_name,
                        'tool_type': source_ref['source'],
                        'description': description,
                        'operations': tool_operations,
                        'parameters': parameters,
                        'source': source_ref['source'],
                        'source_id': source_ref.get('source_id'),
                    }
                )

        return tools

    @staticmethod
    def _catalog_source_ref(item: dict[str, typing.Any]) -> ToolSourceRef | None:
        source = item.get('source')
        if not isinstance(source, str) or not source:
            return None
        source_id = item.get('source_id')
        return {
            'source': source,
            'source_id': source_id if isinstance(source_id, str) and source_id else None,
        }

    async def _build_knowledge_bases_from_binding(
        self,
        manifest_perms: typing.Any,
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
    ) -> list[KnowledgeBaseResource]:
        """Build knowledge bases list from binding."""
        kb_resources: list[KnowledgeBaseResource] = []
        kb_perms = set(manifest_perms.knowledge_bases)
        if not ({'list', 'retrieve'} & kb_perms):
            return kb_resources
        kb_operations = [operation for operation in ('list', 'retrieve') if operation in kb_perms]

        if not config_schema.uses_host_knowledge_bases(descriptor):
            return kb_resources

        # Get KB UUID grants from schema-defined config fields.
        kb_uuids = config_schema.extract_knowledge_base_uuids(descriptor, runner_config)

        # Also include resource policy grants.
        allowed_uuids = resource_policy.allowed_kb_uuids
        if allowed_uuids:
            kb_uuids = list(dict.fromkeys([*kb_uuids, *allowed_uuids]))

        for kb_uuid in kb_uuids:
            try:
                kb = await self.ap.rag_mgr.get_knowledge_base_by_uuid(kb_uuid)
                if kb:
                    kb_resources.append(
                        {
                            'kb_id': kb_uuid,
                            'kb_name': kb.get_name(),
                            'kb_type': kb.knowledge_base_entity.kb_type
                            if hasattr(kb.knowledge_base_entity, 'kb_type')
                            else None,
                            'operations': kb_operations,
                        }
                    )
            except Exception as e:
                self.ap.logger.warning(f'Failed to build knowledge base resource {kb_uuid}: {e}')

        return kb_resources

    def _build_skills_from_binding(
        self,
        resource_policy: typing.Any,
        descriptor: AgentRunnerDescriptor,
    ) -> list[SkillResource]:
        """Build pipeline-visible skill resource facts.

        Skills are exposed as authorized tools (activate / register_skill / native
        exec), so skill facts are surfaced to every run that has a skill manager,
        not gated by the ``skill_authoring`` capability. The capability is now a
        semantic declaration only.
        """
        skill_mgr = getattr(self.ap, 'skill_mgr', None)
        if skill_mgr is None:
            return []

        loaded_skills = getattr(skill_mgr, 'skills', {}) or {}
        allowed_names = resource_policy.allowed_skill_names
        if allowed_names is None:
            names = sorted(loaded_skills.keys())
        else:
            names = sorted(name for name in allowed_names if name in loaded_skills)

        skills: list[SkillResource] = []
        for skill_name in names:
            skill_data = loaded_skills.get(skill_name) or {}
            skills.append(
                {
                    'skill_name': skill_name,
                    'display_name': skill_data.get('display_name') or skill_data.get('name') or skill_name,
                    'description': skill_data.get('description') or None,
                }
            )
        return skills

    def _build_storage_from_binding(
        self,
        manifest_perms: typing.Any,
        binding: AgentBinding,
    ) -> StorageResource:
        """Build storage access summary from manifest and binding policy."""
        resource_policy = binding.resource_policy
        storage_perms = set(manifest_perms.storage)

        return {
            'plugin_storage': 'plugin' in storage_perms and resource_policy.allow_plugin_storage,
            'workspace_storage': 'workspace' in storage_perms and resource_policy.allow_workspace_storage,
        }

    async def _append_config_declared_model_resources(
        self,
        models: list[ModelResource],
        seen_model_ids: set[str],
        descriptor: AgentRunnerDescriptor,
        runner_config: dict[str, typing.Any],
        include_llm: bool,
        include_rerank: bool,
        llm_operations: list[str],
    ) -> None:
        """Authorize model-like values selected through DynamicForm fields."""
        for model_type, model_uuid in config_schema.iter_config_model_refs(descriptor, runner_config):
            if model_type == 'llm' and include_llm:
                await self._append_llm_model_resource(models, seen_model_ids, model_uuid, llm_operations)
            elif model_type == 'rerank' and include_rerank:
                await self._append_rerank_model_resource(models, seen_model_ids, model_uuid)

    async def _append_llm_model_resource(
        self,
        models: list[ModelResource],
        seen_model_ids: set[str],
        model_uuid: str | None,
        operations: list[str],
    ) -> None:
        """Append an LLM model resource if it exists and has not been added."""
        if not model_uuid or model_uuid == '__none__' or model_uuid in seen_model_ids:
            return

        try:
            model = await self.ap.model_mgr.get_model_by_uuid(model_uuid)
            if model and model.model_entity:
                models.append(
                    {
                        'model_id': model_uuid,
                        'model_type': getattr(model.model_entity, 'model_type', None),
                        'provider': getattr(model.provider_entity, 'name', None)
                        if hasattr(model, 'provider_entity')
                        else None,
                        'operations': operations,
                    }
                )
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
                models.append(
                    {
                        'model_id': model_uuid,
                        'model_type': getattr(model.model_entity, 'model_type', 'rerank') or 'rerank',
                        'provider': getattr(model.provider_entity, 'name', None)
                        if hasattr(model, 'provider_entity')
                        else None,
                        'operations': ['rerank'],
                    }
                )
                seen_model_ids.add(model_uuid)
        except Exception as e:
            self.ap.logger.warning(f'Failed to build rerank model resource {model_uuid}: {e}')
