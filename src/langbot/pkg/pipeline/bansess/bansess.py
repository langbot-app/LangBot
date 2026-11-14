from __future__ import annotations

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('BanSessionCheckStage')
class BanSessionCheckStage(stage.PipelineStage):
    """Access control processing stage

    Applies the access control list of the message policy in effect for the query.
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        policy = await self.ap.message_policy_mgr.for_query(query)
        verdict = policy.check_access(query.launcher_type.value, query.launcher_id, query.sender_id)

        return entities.StageProcessResult(
            result_type=entities.ResultType.CONTINUE if verdict.allowed else entities.ResultType.INTERRUPT,
            new_query=query,
            console_notice=verdict.console_notice,
        )
