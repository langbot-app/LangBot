from __future__ import annotations


from .. import stage, entities
from ...utils import importutil
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from . import strategies

importutil.import_modules_in_pkg(strategies)


@stage.stage_class('LongTextProcessStage')
class LongTextProcessStage(stage.PipelineStage):
    """Long message processing stage

    Applies the long-text handling of the message policy in effect for the query.

    Rewrite:
        - resp_message_chain
    """

    async def initialize(self, pipeline_config: dict):
        pass

    async def process(self, query: pipeline_query.Query, stage_inst_name: str) -> entities.StageProcessResult:
        if not query.resp_message_chain:
            self.ap.logger.debug('Response message chain is empty, skip long message processing.')
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)

        policy = await self.ap.message_policy_mgr.for_query(query)
        query.resp_message_chain[-1] = await policy.process_long_text(query, query.resp_message_chain[-1])

        return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
