from __future__ import annotations

import uuid
import json
import copy
import sqlalchemy
import typing

from ....core import app
from ....entity.persistence import pipeline as persistence_pipeline
from ....provider.conversation.dify_store import DifyConversationStore


def _normalize_launcher_type(launcher_type: typing.Any) -> str:
    if hasattr(launcher_type, 'value'):
        return str(launcher_type.value)
    return str(launcher_type)

def _parse_bool_config(value: typing.Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes', 'on'}:
            return True
        if normalized in {'false', '0', 'no', 'off'}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return default
    return bool(value)


def _deep_merge_dict(base: typing.Any, override: typing.Any) -> typing.Any:
    """Recursively merge user-provided config into the template defaults."""
    if not isinstance(base, dict):
        return copy.deepcopy(override)

    merged = copy.deepcopy(base)
    if not isinstance(override, dict):
        return merged

    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)

    return merged



def _get_dify_conversation_store(ap: app.Application) -> DifyConversationStore | None:
    raw_cfg = getattr(getattr(ap, 'instance_config', None), 'data', {}) or {}
    cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
    raw_store_cfg = cfg.get('dify_conversation_store', {}) or {}
    store_cfg = raw_store_cfg if isinstance(raw_store_cfg, dict) else {}

    try:
        if 'idle_timeout_seconds' in store_cfg:
            ttl_seconds = int(store_cfg.get('idle_timeout_seconds'))
        else:
            ttl_seconds = int(store_cfg.get('ttl_seconds', 43200))
    except (TypeError, ValueError):
        ttl_seconds = 43200

    try:
        lock_ttl_seconds = int(store_cfg.get('lock_ttl_seconds', 10))
    except (TypeError, ValueError):
        lock_ttl_seconds = 10

    redis_mgr = getattr(ap, 'redis_mgr', None)
    if redis_mgr is None:
        return None

    return DifyConversationStore(
        redis_mgr=redis_mgr,
        ttl_seconds=max(1, ttl_seconds),
        lock_ttl_seconds=max(1, lock_ttl_seconds),
        enabled=_parse_bool_config(store_cfg.get('enabled', True), True),
    )


def _get_session_scope(session: typing.Any) -> tuple[str, str] | None:
    launcher_type = getattr(session, 'launcher_type', None)
    launcher_id = getattr(session, 'launcher_id', None)
    if launcher_type is None or launcher_id is None:
        return None

    return _normalize_launcher_type(launcher_type), str(launcher_id)


default_stage_order = [
    'GroupRespondRuleCheckStage',  # 群响应规则检查
    'BanSessionCheckStage',  # 封禁会话检查
    'PreContentFilterStage',  # 内容过滤前置阶段
    'PreProcessor',  # 预处理器
    'ConversationMessageTruncator',  # 会话消息截断器
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

    async def get_pipeline_metadata(self) -> list[dict]:
        return [
            self.ap.pipeline_config_meta_trigger,
            self.ap.pipeline_config_meta_safety,
            self.ap.pipeline_config_meta_ai,
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
        from ....utils import paths as path_utils

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

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            default_config = json.load(f)

        submitted_config = pipeline_data.get('config', {})
        if not isinstance(submitted_config, dict):
            submitted_config = {}

        # Preserve user-submitted values while still filling omitted fields from the default template.
        pipeline_data['config'] = _deep_merge_dict(default_config, submitted_config)

        # Ensure extensions_preferences is set with enable_all_plugins and enable_all_mcp_servers=True by default
        if 'extensions_preferences' not in pipeline_data:
            pipeline_data['extensions_preferences'] = {
                'enable_all_plugins': True,
                'enable_all_mcp_servers': True,
                'plugins': [],
                'mcp_servers': [],
            }

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(**pipeline_data)
        )

        pipeline = await self.get_pipeline(pipeline_data['uuid'])

        await self.ap.pipeline_mgr.load_pipeline(pipeline)

        return pipeline_data['uuid']

    async def update_pipeline(self, pipeline_uuid: str, pipeline_data: dict) -> None:
        if 'uuid' in pipeline_data:
            del pipeline_data['uuid']
        if 'for_version' in pipeline_data:
            del pipeline_data['for_version']
        if 'stages' in pipeline_data:
            del pipeline_data['stages']
        if 'is_default' in pipeline_data:
            del pipeline_data['is_default']

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_pipeline.LegacyPipeline)
            .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
            .values(**pipeline_data)
        )

        pipeline = await self.get_pipeline(pipeline_uuid)

        if 'name' in pipeline_data:
            from ....entity.persistence import bot as persistence_bot

            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.use_pipeline_uuid == pipeline_uuid)
            )

            bots = result.all()

            for bot in bots:
                bot_data = {'use_pipeline_name': pipeline_data['name']}
                await self.ap.bot_service.update_bot(bot.uuid, bot_data)

        await self.ap.pipeline_mgr.remove_pipeline(pipeline_uuid)
        await self.ap.pipeline_mgr.load_pipeline(pipeline)

        # update all conversation that use this pipeline
        store = _get_dify_conversation_store(self.ap)
        for session in self.ap.sess_mgr.session_list:
            using_conversation = getattr(session, 'using_conversation', None)
            if using_conversation is None or using_conversation.pipeline_uuid != pipeline_uuid:
                continue

            if store is not None:
                scope = _get_session_scope(session)
                bot_uuid = getattr(using_conversation, 'bot_uuid', None)
                if scope is not None and bot_uuid:
                    launcher_type, launcher_id = scope
                    scope_bot_uuid = str(bot_uuid)
                    scope_pipeline_uuid = str(pipeline_uuid)
                    try:
                        await store.delete_conversation_id(
                            scope_bot_uuid,
                            scope_pipeline_uuid,
                            launcher_type,
                            launcher_id,
                        )
                    except Exception as exc:
                        self.ap.logger.warning(
                            'dify conversation reset delete failed '
                            f'bot_uuid={scope_bot_uuid} pipeline_uuid={scope_pipeline_uuid} '
                            f'launcher_type={launcher_type} launcher_id={launcher_id}: {exc}'
                        )

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
        extensions_preferences['plugins'] = bound_plugins
        if bound_mcp_servers is not None:
            extensions_preferences['mcp_servers'] = bound_mcp_servers

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_pipeline.LegacyPipeline)
            .where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
            .values(extensions_preferences=extensions_preferences)
        )

        # Reload pipeline to apply changes
        await self.ap.pipeline_mgr.remove_pipeline(pipeline_uuid)
        pipeline = await self.get_pipeline(pipeline_uuid)
        await self.ap.pipeline_mgr.load_pipeline(pipeline)
