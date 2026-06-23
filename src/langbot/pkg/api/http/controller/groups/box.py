from __future__ import annotations

from langbot.pkg.utils import constants

from .. import group
from .box_visibility import should_hide_box_runtime_status


@group.group_class('box', '/api/v1/box')
class BoxRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/status', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            status = await self.ap.box_service.get_status()
            status['hidden'] = should_hide_box_runtime_status(constants.edition, status.get('enabled'))
            return self.success(data=status)

        @self.route('/sessions', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            sessions = await self.ap.box_service.get_sessions()
            return self.success(data=sessions)

        @self.route('/errors', methods=['GET'], auth_type=group.AuthType.USER_TOKEN)
        async def _() -> str:
            errors = self.ap.box_service.get_recent_errors()
            return self.success(data=errors)
