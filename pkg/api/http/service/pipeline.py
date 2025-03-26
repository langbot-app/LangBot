from __future__ import annotations

import uuid
import datetime
import sqlalchemy

from ....core import app
from ....pipeline import stagemgr
from ....entity.persistence import pipeline as persistence_pipeline


class PipelineService:
    ap: app.Application
    
    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
    
    async def get_pipeline_metadata(self) -> dict:
        return [
            self.ap.pipeline_config_meta_trigger.data,
            self.ap.pipeline_config_meta_safety.data,
            self.ap.pipeline_config_meta_ai.data,
            self.ap.pipeline_config_meta_output.data
        ]

    async def get_pipelines(self) -> list[dict]:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline)
        )
        
        pipelines = result.all()
        return [
            self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)
            for pipeline in pipelines
        ]
    
    async def get_pipeline(self, pipeline_uuid: str) -> dict | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
        )
        
        pipeline = result.first()

        if pipeline is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

    async def create_pipeline(self, pipeline_data: dict) -> None:
        pipeline_data['uuid'] = str(uuid.uuid4())
        pipeline_data['for_version'] = self.ap.ver_mgr.get_current_version()
        pipeline_data['stages'] = stagemgr.stage_order.copy()

        # TODO: 检查pipeline config是否完整

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_pipeline.LegacyPipeline).values(**pipeline_data)
        )
        # TODO: 更新到pipeline manager

    async def update_pipeline(self, pipeline_uuid: str, pipeline_data: dict) -> None:
        del pipeline_data['uuid']
        del pipeline_data['for_version']
        del pipeline_data['stages']
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_pipeline.LegacyPipeline).where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid).values(**pipeline_data)
        )
        # TODO: 更新到pipeline manager

    async def delete_pipeline(self, pipeline_uuid: str) -> None:
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_pipeline.LegacyPipeline).where(persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid)
        )
        # TODO: 更新到pipeline manager
