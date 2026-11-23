from .. import group
from ...authz import Permission
from ...context import ExecutionContext, RequestContext


def collect_basic_stats(ap, request_context: RequestContext) -> dict[str, int]:
    """Collect runtime counters only from the selected Workspace placement."""

    execution_context = ExecutionContext.from_request(request_context)
    sessions = [
        session
        for session in ap.sess_mgr.session_list
        if (
            getattr(session, 'instance_uuid', None) == execution_context.instance_uuid
            and getattr(session, 'workspace_uuid', None) == execution_context.workspace_uuid
            and getattr(session, 'placement_generation', None) == execution_context.placement_generation
        )
    ]
    conversation_count = sum(
        len(session.conversations if session.conversations is not None else []) for session in sessions
    )
    return {
        'active_session_count': len(sessions),
        'conversation_count': conversation_count,
        'query_count': ap.query_pool.get_query_count(execution_context),
    }


@group.group_class('stats', '/api/v1/stats')
class StatsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/basic',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            return self.success(data=collect_basic_stats(self.ap, request_context))
