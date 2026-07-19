from __future__ import annotations

from langbot.pkg.utils import constants

from ...authz import Permission
from ...context import RequestContext
from .. import group
from .box_visibility import should_hide_box_runtime_status


@group.group_class('box', '/api/v1/box')
class BoxRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route(
            '/status',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.RESOURCE_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            status = await self.ap.box_service.get_status(request_context)
            status['hidden'] = should_hide_box_runtime_status(constants.edition, status.get('enabled'))
            return self.success(data=status)

        @self.route(
            '/sessions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            sessions = await self.ap.box_service.get_sessions(request_context)
            return self.success(data=sessions)

        @self.route(
            '/errors',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            errors = self.ap.box_service.get_recent_errors(request_context)
            return self.success(data=errors)
