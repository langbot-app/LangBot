from __future__ import annotations

from .. import group


@group.group_class('box', '/api/v1/box')
class BoxRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/status', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            status = await self.ap.box_service.get_status()
            return self.success(data=status)

        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            sessions = self.ap.box_service.runtime.get_sessions()
            return self.success(data=sessions)

        @self.route('/errors', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            errors = self.ap.box_service.get_recent_errors()
            return self.success(data=errors)
