from __future__ import annotations


from .. import stage, entities
from ...utils import importutil

import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query

from . import rules

importutil.import_modules_in_pkg(rules)


@stage.stage_class('GroupRespondRuleCheckStage')
class GroupRespondRuleCheckStage(stage.PipelineStage):
    """Group respond rule check

    Applies the group respond rules of the message policy in effect for the
    query. Only group messages are checked.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        if query.launcher_type.value != 'group':  # 只处理群消息
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        if query.variables and query.variables.get('_routed_by_rule') and query.variables.get('_dify_form_action'):
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        policy = await self.ap.message_policy_mgr.for_query(query)
        if await policy.match_group_rules(query):
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        return entities.StageProcessResult(result_type=entities.ResultType.INTERRUPT, new_query=query)
