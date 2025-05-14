from __future__ import annotations


import quart

from .. import group


@group.group_class('logs', '/api/v1/logs')
class LogsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            start_page_number = int(quart.request.args.get('start_page_number', 0))
            start_offset = int(quart.request.args.get('start_offset', 0))

            logs_str, end_page_number, end_offset = self.ap.log_cache.get_log_by_pointer(
                start_page_number=start_page_number, start_offset=start_offset
            )

            return self.success(
                data={
                    'logs': logs_str,
                    'end_page_number': end_page_number,
                    'end_offset': end_offset,
                }
            )
