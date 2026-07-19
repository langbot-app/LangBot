from __future__ import annotations

from langbot.pkg.utils import constants
from langbot_plugin.box.errors import BoxAdmissionError

from langbot.pkg.cloud.entitlements import EntitlementUnavailableError
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
            try:
                status = await self.ap.box_service.get_status(request_context)
            except (BoxAdmissionError, EntitlementUnavailableError) as exc:
                return self.http_status(403, 'managed_sandbox_unavailable', str(exc))
            status['hidden'] = should_hide_box_runtime_status(constants.edition, status.get('enabled'))
            return self.success(data=status)

        @self.route(
            '/sessions',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                sessions = await self.ap.box_service.get_sessions(request_context)
            except (BoxAdmissionError, EntitlementUnavailableError) as exc:
                return self.http_status(403, 'managed_sandbox_unavailable', str(exc))
            return self.success(data=sessions)

        @self.route(
            '/errors',
            methods=['GET'],
            auth_type=group.AuthType.USER_TOKEN,
            permission=Permission.AUDIT_VIEW,
        )
        async def _(request_context: RequestContext) -> str:
            try:
                if getattr(self.ap.box_service, 'managed_admission_required', False):
                    await self.ap.box_service.require_workspace_sandbox(request_context)
            except (BoxAdmissionError, EntitlementUnavailableError) as exc:
                return self.http_status(403, 'managed_sandbox_unavailable', str(exc))
            errors = self.ap.box_service.get_recent_errors(request_context)
            return self.success(data=errors)
