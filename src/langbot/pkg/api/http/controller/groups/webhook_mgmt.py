from __future__ import annotations

import quart

from ...authz import Permission, has_permission
from ...context import RequestContext
from .. import group


@group.group_class('webhook_mgmt', '/api/v1/webhooks')
class WebhookManagementRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def _(request_context: RequestContext) -> str:
            webhooks = await self.ap.webhook_service.get_webhooks(
                request_context,
                include_secret=has_permission(request_context, Permission.RESOURCE_MANAGE),
            )
            return self.success(data={'webhooks': webhooks})

        @self.route('', methods=['POST'], permission=Permission.RESOURCE_MANAGE)
        async def _(request_context: RequestContext) -> str:
            json_data = await quart.request.get_json(silent=True) or {}
            name = json_data.get('name', '')
            url = json_data.get('url', '')
            description = json_data.get('description', '')
            enabled = json_data.get('enabled', True)

            if not name:
                return self.http_status(400, -1, 'Name is required')
            if not url:
                return self.http_status(400, -1, 'URL is required')

            try:
                webhook = await self.ap.webhook_service.create_webhook(
                    request_context,
                    name,
                    url,
                    description,
                    enabled,
                )
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'webhook': webhook})

        @self.route('/<int:webhook_id>', methods=['GET'], permission=Permission.RESOURCE_VIEW)
        async def _(webhook_id: int, request_context: RequestContext) -> str:
            webhook = await self.ap.webhook_service.get_webhook(
                request_context,
                webhook_id,
                include_secret=has_permission(request_context, Permission.RESOURCE_MANAGE),
            )
            if webhook is None:
                return self.http_status(404, -1, 'Webhook not found')
            return self.success(data={'webhook': webhook})

        @self.route(
            '/<int:webhook_id>',
            methods=['PUT', 'DELETE'],
            permission=Permission.RESOURCE_MANAGE,
        )
        async def _(webhook_id: int, request_context: RequestContext) -> str:
            if quart.request.method == 'PUT':
                json_data = await quart.request.get_json(silent=True) or {}
                updated = await self.ap.webhook_service.update_webhook(
                    request_context,
                    webhook_id,
                    json_data.get('name'),
                    json_data.get('url'),
                    json_data.get('description'),
                    json_data.get('enabled'),
                )
                if not updated:
                    return self.http_status(404, -1, 'Webhook not found')
                return self.success()

            deleted = await self.ap.webhook_service.delete_webhook(request_context, webhook_id)
            if not deleted:
                return self.http_status(404, -1, 'Webhook not found')
            return self.success()
