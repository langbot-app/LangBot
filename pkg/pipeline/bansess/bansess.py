from __future__ import annotations

from .. import stage, entities
from ...core import entities as core_entities


@stage.stage_class('BanSessionCheckStage')
class BanSessionCheckStage(stage.PipelineStage):
    """Access control processing stage

    Only check if the group or personal number in the query is in the access control list.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(self, query: core_entities.Query, stage_inst_name: str) -> entities.StageProcessResult:
        found = False

        mode = query.pipeline_config['trigger']['access-control']['mode']

        sess_list = query.pipeline_config['trigger']['access-control'][mode]

        if (query.launcher_type.value == 'group' and 'group_*' in sess_list) or (
            query.launcher_type.value == 'person' and 'person_*' in sess_list
        ):
            found = True
        else:
            for sess in sess_list:
                if sess == f'{query.launcher_type.value}_{query.launcher_id}':
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
            console_notice=f'Ignore message according to access control: {query.launcher_type.value}_{query.launcher_id}'
            if not ctn
            else '',
        )
