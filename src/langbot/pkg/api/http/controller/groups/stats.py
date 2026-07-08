from .. import group


@group.group_class('stats', '/api/v1/stats')
class StatsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/basic', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            conv_count = 0
            for session in self.ap.sess_mgr.session_list:
                conv_count += len(session.conversations if session.conversations is not None else [])

            return self.success(
                data={
                    'active_session_count': len(self.ap.sess_mgr.session_list),
                    'conversation_count': conv_count,
                    'query_count': self.ap.query_pool.query_id_counter,
                }
            )
