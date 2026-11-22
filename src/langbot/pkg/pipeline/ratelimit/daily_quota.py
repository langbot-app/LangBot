from ...cloud.message_quota import daily_message_quota
from ...i18n import pipeline_notice
from .. import entities, stage
from ..pool import get_query_execution_context


@stage.stage_class('RequireDailyMessageQuota')
class DailyMessageQuota(stage.PipelineStage):
    async def process(self, query, stage_inst_name):
        if getattr(getattr(self.ap, 'deployment', None), 'mode', None) != 'cloud':
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
        accepted, quota = await daily_message_quota(
            self.ap, get_query_execution_context(query).workspace_uuid, reserve=True
        )
        if accepted:
            return entities.StageProcessResult(result_type=entities.ResultType.CONTINUE, new_query=query)
        message = pipeline_notice(
            query,
            'daily-message-quota-exceeded',
            'Daily message quota reached ({limit} per day). It resets at 00:00 UTC. Upgrade your plan for a higher quota.',
            limit=quota['limit'],
        )
        return entities.StageProcessResult(
            result_type=entities.ResultType.INTERRUPT,
            new_query=query,
            user_notice=message,
            error_notice=message,
            structured_error={'error_code': 'daily_message_quota_exceeded', 'message': message, 'quota': quota},
        )
