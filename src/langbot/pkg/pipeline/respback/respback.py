from __future__ import annotations

from .. import stage, entities
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query


@stage.stage_class('SendResponseBackStage')
class SendResponseBackStage(stage.PipelineStage):
    """Send the reply back, with the delay, @sender and quote settings of the message policy."""

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        """处理"""
        policy = await self.ap.message_policy_mgr.for_query(query)
        await policy.send_reply(query)

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
