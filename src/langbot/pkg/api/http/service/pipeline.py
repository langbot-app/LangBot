from __future__ import annotations

import uuid
import json
import sqlalchemy
import typing

from ....core import app
from ....agent.runner.config_resolver import RunnerConfigResolver
from ....entity.persistence import pipeline as persistence_pipeline
from ....pipeline.extension_preferences import (
    normalize_extension_preferences,
    validate_extension_preferences,
)
from ....workspace.errors import WorkspaceNotFoundError
from .secrets import contains_secret_placeholder, redact_secrets, restore_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid, scope_statement


default_stage_order = [
    'GroupRespondRuleCheckStage',  # 群响应规则检查
    'BanSessionCheckStage',  # 封禁会话检查
    'PreContentFilterStage',  # 内容过滤前置阶段
    'PreProcessor',  # 预处理器
    'RequireRateLimitOccupancy',  # 请求速率限制占用
    'MessageProcessor',  # 处理器
    'ReleaseRateLimitOccupancy',  # 释放速率限制占用
    'PostContentFilterStage',  # 内容过滤后置阶段
    'ResponseWrapper',  # 响应包装器
    'LongTextProcessStage',  # 长文本处理
    'SendResponseBackStage',  # 发送响应
]


class PipelineService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @staticmethod
    def _get_default_values_from_schema(
        config_schema: list[dict[str, typing.Any]],
    ) -> dict[str, typing.Any]:
        return {
            item['name']: item['default']
            for item in config_schema
            if item.get('name') and 'default' in item
        }

    async def get_default_pipeline_config(self, context: TenantContext) -> dict[str, typing.Any]:
        from ....utils import paths as path_utils

        template_path = path_utils.get_resource_path(
            'templates/default-pipeline-config.json'
        )
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        registry = getattr(self.ap, 'agent_runner_registry', None)
        if registry is None:
            return config
        try:
            runners = await registry.list_runners(context, bound_plugins=None)
        except Exception as exc:
            self.ap.logger.warning(
                f'Failed to load AgentRunner defaults for pipeline config: {exc}'
            )
            return config
        if not runners:
            return config

        selected = runners[0]
        ai_config = config.setdefault('ai', {})
        runner_config = ai_config.setdefault('runner', {})
        runner_config['id'] = selected.id
        runner_config.setdefault('expire-time', 0)
        ai_config['runner_config'] = {
            selected.id: self._get_default_values_from_schema(
                selected.config_schema
            )
        }
        return config

    async def get_pipeline_metadata(self, context: TenantContext) -> list[dict]:
        require_workspace_uuid(context)
        import copy

        ai_metadata = copy.deepcopy(self.ap.pipeline_config_meta_ai)
        runner_stage = next(
            (
                stage
                for stage in ai_metadata.get('stages', [])
                if stage.get('name') == 'runner'
            ),
            None,
        )
        if runner_stage:
            for config_item in runner_stage.get('config', []):
                if config_item.get('name') != 'id':
                    continue
                try:
                    runner_options, runner_stages = (
                        await self.ap.agent_runner_registry.get_runner_metadata_for_pipeline(context)
                    )
                    config_item['options'] = runner_options
                    if runner_options and 'default' not in config_item:
                        config_item['default'] = runner_options[0]['name']
                    existing = {
                        stage.get('name')
                        for stage in ai_metadata.get('stages', [])
                    }
                    ai_metadata.setdefault('stages', []).extend(
                        stage
                        for stage in runner_stages
                        if stage.get('name') not in existing
                    )
                except Exception as exc:
                    self.ap.logger.warning(
                        f'Failed to load AgentRunner pipeline metadata: {exc}'
                    )
        return [
            self.ap.pipeline_config_meta_trigger,
            self.ap.pipeline_config_meta_safety,
            ai_metadata,
            self.ap.pipeline_config_meta_output,
        ]

    async def get_pipelines(
        self,
        context: TenantContext,
        sort_by: str = 'created_at',
        sort_order: str = 'DESC',
        *,
        include_secret: bool = False,
    ) -> list[dict]:
        query = scope_statement(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline),
            persistence_pipeline.LegacyPipeline,
            context,
        )

        if sort_by == 'created_at':
            if sort_order == 'DESC':
                query = query.order_by(persistence_pipeline.LegacyPipeline.created_at.desc())
            else:
                query = query.order_by(persistence_pipeline.LegacyPipeline.created_at.asc())
        elif sort_by == 'updated_at':
            if sort_order == 'DESC':
                query = query.order_by(persistence_pipeline.LegacyPipeline.updated_at.desc())
            else:
                query = query.order_by(persistence_pipeline.LegacyPipeline.updated_at.asc())

        result = await self.ap.persistence_mgr.execute_async(query)
        pipelines = result.all()
        serialized = [
            self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)
            for pipeline in pipelines
        ]
        return serialized if include_secret else [redact_secrets(pipeline) for pipeline in serialized]

    async def get_pipeline(
        self,
        context: TenantContext,
        pipeline_uuid: str,
        *,
        include_secret: bool = False,
    ) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                ),
                persistence_pipeline.LegacyPipeline,
                context,
            )
        )

        pipeline = result.first()

        if pipeline is None:
            return None

        serialized = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)
        return serialized if include_secret else redact_secrets(serialized)

    async def create_pipeline(self, context: TenantContext, pipeline_data: dict, default: bool = False) -> str:
        workspace_uuid = require_workspace_uuid(context)
        if 'extensions_preferences' in pipeline_data:
            self._validate_extension_preferences(
                pipeline_data['extensions_preferences']
            )
        if 'config' in pipeline_data:
            RunnerConfigResolver.validate_pipeline_config(pipeline_data['config'])
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_pipelines = limitation.get('max_pipelines', -1)
        if max_pipelines >= 0:
            existing_pipelines = await self.get_pipelines(context)
            if len(existing_pipelines) >= max_pipelines:
                raise ValueError(f'Maximum number of pipelines ({max_pipelines}) reached')

        pipeline_data = pipeline_data.copy()
        pipeline_data['uuid'] = str(uuid.uuid4())
        pipeline_data['workspace_uuid'] = workspace_uuid
        pipeline_data['for_version'] = self.ap.ver_mgr.get_current_version()
        pipeline_data['stages'] = default_stage_order.copy()
        pipeline_data['is_default'] = default

        pipeline_data['config'] = await self.get_default_pipeline_config(context)
        RunnerConfigResolver.validate_pipeline_config(pipeline_data['config'])

        # Ensure extensions_preferences is set with enable_all_plugins and enable_all_mcp_servers=True by default
        if 'extensions_preferences' not in pipeline_data:
            pipeline_data['extensions_preferences'] = {
                'enable_all_plugins': True,
                'enable_all_mcp_servers': True,
                'plugins': [],
                'mcp_servers': [],
                'mcp_resources': [],
                'mcp_resource_agent_read_enabled': True,
            }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(**pipeline_data)
        )

        pipeline = await self.get_pipeline(context, pipeline_data['uuid'], include_secret=True)

        await self.ap.pipeline_mgr.load_pipeline(context, pipeline)

        return pipeline_data['uuid']

    async def update_pipeline(self, context: TenantContext, pipeline_uuid: str, pipeline_data: dict) -> None:
        workspace_uuid = require_workspace_uuid(context)
        pipeline_data = pipeline_data.copy()
        for protected_field in ('uuid', 'workspace_uuid', 'for_version', 'stages', 'is_default'):
            pipeline_data.pop(protected_field, None)

        if 'config' in pipeline_data:
            current_config = None
            if contains_secret_placeholder(pipeline_data['config']):
                current_pipeline = await self.get_pipeline(context, pipeline_uuid, include_secret=True)
                if current_pipeline is None:
                    raise WorkspaceNotFoundError('Pipeline not found')
                current_config = current_pipeline.get('config', {})
            pipeline_data['config'] = restore_secret_placeholders(
                pipeline_data['config'],
                current_config if current_config is not None else {},
            )
            RunnerConfigResolver.validate_pipeline_config(pipeline_data['config'])
        if 'extensions_preferences' in pipeline_data:
            self._validate_extension_preferences(
                pipeline_data['extensions_preferences']
            )

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
                .values(**pipeline_data),
                persistence_pipeline.LegacyPipeline,
                workspace_uuid,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Pipeline not found')

        pipeline = await self.get_pipeline(context, pipeline_uuid, include_secret=True)
        if pipeline is None:
            raise WorkspaceNotFoundError('Pipeline not found')

        await self.ap.pipeline_mgr.remove_pipeline(context, pipeline_uuid)
        await self.ap.pipeline_mgr.load_pipeline(context, pipeline)

        # update all conversation that use this pipeline
        for session in self.ap.sess_mgr.session_list:
            if (
                session.using_conversation is not None
                and session.using_conversation.pipeline_uuid == pipeline_uuid
                and getattr(session, 'workspace_uuid', workspace_uuid) == workspace_uuid
            ):
                session.using_conversation = None

    async def delete_pipeline(self, context: TenantContext, pipeline_uuid: str) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                ),
                persistence_pipeline.LegacyPipeline,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Pipeline not found')
        await self.ap.pipeline_mgr.remove_pipeline(context, pipeline_uuid)

    async def copy_pipeline(self, context: TenantContext, pipeline_uuid: str) -> str:
        """Copy a pipeline with all its configurations"""
        workspace_uuid = require_workspace_uuid(context)
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_pipelines = limitation.get('max_pipelines', -1)
        if max_pipelines >= 0:
            existing_pipelines = await self.get_pipelines(context)
            if len(existing_pipelines) >= max_pipelines:
                raise ValueError(f'Maximum number of pipelines ({max_pipelines}) reached')

        # Get the original pipeline
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                ),
                persistence_pipeline.LegacyPipeline,
                workspace_uuid,
            )
        )

        original_pipeline = result.first()
        if original_pipeline is None:
            raise WorkspaceNotFoundError(f'Pipeline {pipeline_uuid} not found')

        # Create new pipeline data
        new_uuid = str(uuid.uuid4())
        new_pipeline_data = {
            'uuid': new_uuid,
            'workspace_uuid': workspace_uuid,
            'name': f'{original_pipeline.name} (Copy)',
            'description': original_pipeline.description,
            'for_version': self.ap.ver_mgr.get_current_version(),
            'stages': original_pipeline.stages.copy() if original_pipeline.stages else default_stage_order.copy(),
            'config': original_pipeline.config.copy() if original_pipeline.config else {},
            'is_default': False,
            'extensions_preferences': normalize_extension_preferences(
                original_pipeline.extensions_preferences
            ),
        }

        # Insert the new pipeline
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(**new_pipeline_data)
        )

        # Load the new pipeline
        pipeline = await self.get_pipeline(context, new_uuid, include_secret=True)
        await self.ap.pipeline_mgr.load_pipeline(context, pipeline)

        return new_uuid

    async def update_pipeline_extensions(
        self,
        context: TenantContext,
        pipeline_uuid: str,
        bound_plugins: list[dict],
        bound_mcp_servers: list[str] = None,
        enable_all_plugins: bool = True,
        enable_all_mcp_servers: bool = True,
        bound_skills: list[str] = None,
        enable_all_skills: bool = True,
        bound_mcp_resources: list[dict] = None,
        mcp_resource_agent_read_enabled: bool | None = None,
    ) -> None:
        """Update the bound plugins and MCP servers for a pipeline"""
        workspace_uuid = require_workspace_uuid(context)
        extension_updates: dict[str, typing.Any] = {
            'enable_all_plugins': enable_all_plugins,
            'enable_all_mcp_servers': enable_all_mcp_servers,
            'enable_all_skills': enable_all_skills,
            'plugins': bound_plugins,
        }
        if bound_mcp_servers is not None:
            extension_updates['mcp_servers'] = bound_mcp_servers
        if bound_skills is not None:
            extension_updates['skills'] = bound_skills
        if bound_mcp_resources is not None:
            extension_updates['mcp_resources'] = bound_mcp_resources
        if mcp_resource_agent_read_enabled is not None:
            extension_updates['mcp_resource_agent_read_enabled'] = (
                mcp_resource_agent_read_enabled
            )
        self._validate_extension_preferences(
            extension_updates,
            context='Pipeline extension',
            field_aliases={
                'plugins': 'bound_plugins',
                'mcp_servers': 'bound_mcp_servers',
                'skills': 'bound_skills',
                'mcp_resources': 'bound_mcp_resources',
            },
        )
        # Get current pipeline
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                ),
                persistence_pipeline.LegacyPipeline,
                workspace_uuid,
            )
        )

        pipeline = result.first()
        if pipeline is None:
            raise WorkspaceNotFoundError(f'Pipeline {pipeline_uuid} not found')

        # Update extensions_preferences
        extensions_preferences = normalize_extension_preferences(
            pipeline.extensions_preferences
        )
        extensions_preferences['enable_all_plugins'] = enable_all_plugins
        extensions_preferences['enable_all_mcp_servers'] = enable_all_mcp_servers
        extensions_preferences['enable_all_skills'] = enable_all_skills
        extensions_preferences['plugins'] = bound_plugins
        if mcp_resource_agent_read_enabled is not None:
            extensions_preferences['mcp_resource_agent_read_enabled'] = mcp_resource_agent_read_enabled
        if bound_mcp_servers is not None:
            extensions_preferences['mcp_servers'] = bound_mcp_servers
        if bound_skills is not None:
            extensions_preferences['skills'] = bound_skills
        if bound_mcp_resources is not None:
            extensions_preferences['mcp_resources'] = bound_mcp_resources

        await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
                .values(extensions_preferences=extensions_preferences),
                persistence_pipeline.LegacyPipeline,
                workspace_uuid,
            )
        )

        # Reload pipeline to apply changes
        await self.ap.pipeline_mgr.remove_pipeline(context, pipeline_uuid)
        pipeline = await self.get_pipeline(context, pipeline_uuid, include_secret=True)
        await self.ap.pipeline_mgr.load_pipeline(context, pipeline)

    @staticmethod
    def _validate_extension_preferences(
        value: typing.Any,
        *,
        context: str = 'Pipeline extensions_preferences',
        field_aliases: typing.Mapping[str, str] | None = None,
    ) -> dict[str, typing.Any]:
        validated = validate_extension_preferences(
            value,
            context=context,
            field_aliases=field_aliases,
        )
        RunnerConfigResolver.validate_mcp_resource_attachments(
            validated.get('mcp_resources'),
            context=context,
            field_name='mcp_resources',
        )
        return validated
