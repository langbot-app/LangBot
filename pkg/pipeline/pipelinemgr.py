from __future__ import annotations

import typing

import sqlalchemy

from ..core import app, entities
from ..entity.persistence import pipeline as persistence_pipeline
from . import stagemgr, stage


class RuntimePipeline:
    """运行时流水线"""

    ap: app.Application

    pipeline_entity: persistence_pipeline.LegacyPipeline
    """流水线实体"""

    stage_containers: list[stagemgr.StageInstContainer]
    """阶段实例容器"""

    def __init__(self, ap: app.Application, pipeline_entity: persistence_pipeline.LegacyPipeline, stage_containers: list[stagemgr.StageInstContainer]):
        self.ap = ap
        self.pipeline_entity = pipeline_entity
        self.stage_containers = stage_containers

    async def run(self):
        pass


class PipelineManager:
    """流水线管理器"""

    # ====== 4.0 ======

    ap: app.Application

    pipelines: list[RuntimePipeline]

    stage_dict: dict[str, type[stage.PipelineStage]]

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.pipelines = []

    async def initialize(self):
        self.stage_dict = {name: cls for name, cls in stage.preregistered_stages.items()}

        await self.load_pipelines_from_db()

    async def load_pipelines_from_db(self):
        self.ap.logger.info('Loading pipelines from db...')

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline)
        )

        pipelines = result.all()

        # load pipelines
        for pipeline in pipelines:
            await self.load_pipeline(pipeline)

    async def load_pipeline(self, pipeline_entity: persistence_pipeline.LegacyPipeline | sqlalchemy.Row[persistence_pipeline.LegacyPipeline] | dict):
        
        if isinstance(pipeline_entity, sqlalchemy.Row):
            pipeline_entity = persistence_pipeline.LegacyPipeline(**pipeline_entity._mapping)
        elif isinstance(pipeline_entity, dict):
            pipeline_entity = persistence_pipeline.LegacyPipeline(**pipeline_entity)

        # initialize stage containers according to pipeline_entity.stages
        stage_containers = []
        for stage_name in pipeline_entity.stages:
            stage_containers.append(stagemgr.StageInstContainer(
                stage_name=stage_name,
                stage_class=self.stage_dict[stage_name]
            ))
        
        runtime_pipeline = RuntimePipeline(self.ap, pipeline_entity, stage_containers)
        self.pipelines.append(runtime_pipeline)

    async def get_pipeline_by_uuid(self, uuid: str) -> RuntimePipeline | None:
        for pipeline in self.pipelines:
            if pipeline.pipeline_entity.uuid == uuid:
                return pipeline
        return None

    async def remove_pipeline(self, uuid: str):
        for pipeline in self.pipelines:
            if pipeline.pipeline_entity.uuid == uuid:
                self.pipelines.remove(pipeline)
                return