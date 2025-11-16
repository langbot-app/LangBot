from __future__ import annotations

import uuid
import json
import sqlalchemy

from ....core import app
from ....entity.persistence import pipeline as persistence_pipeline


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

        pipeline_data['uuid'] = str(uuid.uuid4())
        pipeline_data['for_version'] = self.ap.ver_mgr.get_current_version()
        pipeline_data['stages'] = default_stage_order.copy()
        pipeline_data['is_default'] = default

        template_path = path_utils.get_resource_path('templates/default-pipeline-config.json')
        with open(template_path, 'r', encoding='utf-8') as f:
            pipeline_data['config'] = json.load(f)

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

    async def update_pipeline_extensions(
        self, pipeline_uuid: str, bound_plugins: list[dict], bound_mcp_servers: list[str] = None
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
