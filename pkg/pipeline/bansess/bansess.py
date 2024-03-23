from __future__ import annotations
import re

from .. import stage, entities, stagemgr
from ...core import entities as core_entities
from ...config import manager as cfg_mgr


@stage.stage_class('BanSessionCheckStage')
class BanSessionCheckStage(stage.PipelineStage):
    """访问控制处理阶段"""

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

        if (query.launcher_type.value == 'group' and 'group_*' in sess_list) \
            or (query.launcher_type.value == 'person' and 'person_*' in sess_list):
            found = True
        else:
            for sess in sess_list:
                if sess == f"{query.launcher_type.value}_{query.launcher_id}":
                    found = True
                    break
            
        ctn = False

        if mode == 'whitelist':
            ctn = found
        else:
            ctn = not found

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE if ctn else entities.ResultType.INTERRUPT,
            new_query=query,
            console_notice=f'根据访问控制忽略消息: {query.launcher_type.value}_{query.launcher_id}' if not ctn else ''
        )
