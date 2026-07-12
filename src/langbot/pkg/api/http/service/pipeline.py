from __future__ import annotations

import uuid
import json
import sqlalchemy
import typing

from ....core import app
from ....entity.persistence import pipeline as persistence_pipeline


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

    def _get_default_values_from_schema(self, config_schema: list[dict[str, typing.Any]]) -> dict[str, typing.Any]:
        """Build runner config defaults from a DynamicForm schema."""
        defaults: dict[str, typing.Any] = {}
        for item in config_schema:
            name = item.get('name')
            if not name:
                continue
            if 'default' in item:
                defaults[name] = item['default']
        return defaults

    async def get_default_pipeline_config(self) -> dict[str, typing.Any]:
        """Get the default pipeline config, rendering runner defaults from installed plugins."""
        from ....utils import paths as path_utils

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        agent_runner_registry = getattr(self.ap, 'agent_runner_registry', None)
        if agent_runner_registry is None:
            return config

        try:
            runners = await agent_runner_registry.list_runners(bound_plugins=None)
        except Exception as e:
            logger = getattr(self.ap, 'logger', None)
            if logger:
                logger.warning(f'Failed to load plugin agent runners for default pipeline config: {e}')
            return config

        if not runners:
            return config

        selected_runner = runners[0]
        ai_config = config.setdefault('ai', {})
        runner_config = ai_config.setdefault('runner', {})
        runner_config['id'] = selected_runner.id
        runner_config.setdefault('expire-time', 0)

        ai_config['runner_config'] = {
            selected_runner.id: self._get_default_values_from_schema(selected_runner.config_schema),
        }

        return config

    async def get_pipeline_metadata(self) -> list[dict]:
        """Get pipeline metadata with dynamically loaded plugin runners from registry"""
        import copy

        # Deep copy AI metadata to avoid modifying the original
        ai_metadata = copy.deepcopy(self.ap.pipeline_config_meta_ai)

        # Find the runner stage
        runner_stage = None
        for stage in ai_metadata.get('stages', []):
            if stage.get('name') == 'runner':
                runner_stage = stage
                break

        if runner_stage:
            # Find the runner select config (now uses 'id' field)
            for config_item in runner_stage.get('config', []):
                if config_item.get('name') == 'id':
                    # Get plugin agent runners from registry
                    try:
                        (
                            runner_options,
                            runner_stages,
                        ) = await self.ap.agent_runner_registry.get_runner_metadata_for_pipeline()

                        # Replace options entirely with registry options
                        # Only installed/available runners should be shown
                        config_item['options'] = runner_options

                        # Use the registry order as the default order. If no runner is available, leave
                        # the default unset so the UI can recommend installing an AgentRunner plugin.
                        if runner_options and 'default' not in config_item:
                            config_item['default'] = runner_options[0]['name']

                        # Add corresponding stage configuration for each runner
                        for stage_config in runner_stages:
                            # Avoid duplicate stages
                            existing_stage_names = {s.get('name') for s in ai_metadata.get('stages', [])}
                            if stage_config['name'] not in existing_stage_names:
                                ai_metadata['stages'].append(stage_config)

                    except Exception as e:
                        self.ap.logger.warning(f'Failed to load plugin agent runners from registry: {e}')

        return [
            self.ap.pipeline_config_meta_trigger,
            self.ap.pipeline_config_meta_safety,
            ai_metadata,
            self.ap.pipeline_config_meta_output,
        ]

    async def get_pipelines(self, sort_by: str = 'created_at', sort_order: str = 'DESC') -> list[dict]:
        query = sqlalchemy.select(persistence_pipeline.LegacyPipeline)

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
        return [
            self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)
            for pipeline in pipelines
        ]

    async def get_pipeline(self, pipeline_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            )
        )

        pipeline = result.first()

        if pipeline is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

    async def create_pipeline(self, pipeline_data: dict, default: bool = False) -> str:
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_pipelines = limitation.get('max_pipelines', -1)
        if max_pipelines >= 0:
            existing_pipelines = await self.get_pipelines()
            if len(existing_pipelines) >= max_pipelines:
                raise ValueError(f'Maximum number of pipelines ({max_pipelines}) reached')

        pipeline_data['uuid'] = str(uuid.uuid4())
        pipeline_data['for_version'] = self.ap.ver_mgr.get_current_version()
        pipeline_data['stages'] = default_stage_order.copy()
        pipeline_data['is_default'] = default

        pipeline_data['config'] = await self.get_default_pipeline_config()

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

        pipeline = await self.get_pipeline(pipeline_data['uuid'])

        await self.ap.pipeline_mgr.load_pipeline(pipeline)

        return pipeline_data['uuid']

    async def update_pipeline(self, pipeline_uuid: str, pipeline_data: dict) -> None:
        pipeline_data = pipeline_data.copy()
        for protected_field in ('uuid', 'for_version', 'stages', 'is_default'):
            pipeline_data.pop(protected_field, None)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_pipeline.LegacyPipeline)
            .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
            .values(**pipeline_data)
        )

        pipeline = await self.get_pipeline(pipeline_uuid)

        await self.ap.pipeline_mgr.remove_pipeline(pipeline_uuid)
        await self.ap.pipeline_mgr.load_pipeline(pipeline)

        # update all conversation that use this pipeline
        for session in self.ap.sess_mgr.session_list:
            if session.using_conversation is not None and session.using_conversation.pipeline_uuid == pipeline_uuid:
                session.using_conversation = None

    async def delete_pipeline(self, pipeline_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            )
        )
        await self.ap.pipeline_mgr.remove_pipeline(pipeline_uuid)

    async def copy_pipeline(self, pipeline_uuid: str) -> str:
        """Copy a pipeline with all its configurations"""
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_pipelines = limitation.get('max_pipelines', -1)
        if max_pipelines >= 0:
            existing_pipelines = await self.get_pipelines()
            if len(existing_pipelines) >= max_pipelines:
                raise ValueError(f'Maximum number of pipelines ({max_pipelines}) reached')

        # Get the original pipeline
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            )
        )

        original_pipeline = result.first()
        if original_pipeline is None:
            raise ValueError(f'Pipeline {pipeline_uuid} not found')

        # Create new pipeline data
        new_uuid = str(uuid.uuid4())
        new_pipeline_data = {
            'uuid': new_uuid,
            'name': f'{original_pipeline.name} (Copy)',
            'description': original_pipeline.description,
            'for_version': self.ap.ver_mgr.get_current_version(),
            'stages': original_pipeline.stages.copy() if original_pipeline.stages else default_stage_order.copy(),
            'config': original_pipeline.config.copy() if original_pipeline.config else {},
            'is_default': False,
            'extensions_preferences': (
                original_pipeline.extensions_preferences.copy()
                if original_pipeline.extensions_preferences
                else {
                    'enable_all_plugins': True,
                    'enable_all_mcp_servers': True,
                    'plugins': [],
                    'mcp_servers': [],
                    'mcp_resources': [],
                    'mcp_resource_agent_read_enabled': True,
                }
            ),
        }

        # Insert the new pipeline
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(**new_pipeline_data)
        )

        # Load the new pipeline
        pipeline = await self.get_pipeline(new_uuid)
        await self.ap.pipeline_mgr.load_pipeline(pipeline)

        return new_uuid

    async def update_pipeline_extensions(
        self,
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
        # Get current pipeline
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            )
        )

        pipeline = result.first()
        if pipeline is None:
            raise ValueError(f'Pipeline {pipeline_uuid} not found')

        # Update extensions_preferences
        extensions_preferences = pipeline.extensions_preferences or {}
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
            sqlalchemy.update(persistence_pipeline.LegacyPipeline)
            .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
            .values(extensions_preferences=extensions_preferences)
        )

        # Reload pipeline to apply changes
        await self.ap.pipeline_mgr.remove_pipeline(pipeline_uuid)
        pipeline = await self.get_pipeline(pipeline_uuid)
        await self.ap.pipeline_mgr.load_pipeline(pipeline)
