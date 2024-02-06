from __future__ import annotations
import re

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class('BanSessionCheckStage')
class BanSessionCheckStage(stage.PipelineStage):

    async def initialize(self):
        pass

    async def process(
        self,
        query: core_entities.Query,
        stage_inst_name: str
    ) -> entities.StageProcessResult:
        
        found = False

        mode = self.ap.pipeline_cfg.data['access-control']['mode']

        sess_list = self.ap.pipeline_cfg.data['access-control'][mode]

        if (query.launcher_type == 'group' and 'group_*' in sess_list) \
            or (query.launcher_type == 'person' and 'person_*' in sess_list):
            found = True
        else:
            for sess in sess_list:
                if sess == f"{query.launcher_type}_{query.launcher_id}":
                    found = True
                    break

        result = False

        if mode == 'blacklist':
            result = found

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE if not result else entities.ResultType.INTERRUPT,
            new_query=query,
            debug_notice=f'根据访问控制忽略消息: {query.launcher_type}_{query.launcher_id}' if result else ''
        )
