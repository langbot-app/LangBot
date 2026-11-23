"""Workspace failure alert settings, incidents and delivery history."""

from __future__ import annotations

import quart

from ...authz import Permission
from ...context import RequestContext
from .. import group
from .....alerts import rules as alert_rules


@group.group_class('alerts', '/api/v1/alerts')
class AlertsRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('/settings', methods=['GET'], permission=Permission.AUDIT_VIEW)
        async def _(request_context: RequestContext) -> str:
            service = self.ap.alert_service
            workspace_uuid = request_context.workspace_uuid
            settings = await service._settings(workspace_uuid, refresh=True)
            state = await service.channel_state(workspace_uuid, settings)
            webhooks = await self.ap.webhook_service.get_webhooks(request_context, include_secret=False)
            muted = set(settings['muted_account_uuids'])
            return self.success(
                data={
                    'enabled_instance_wide': service.enabled(),
                    'settings': settings,
                    'rule_catalog': alert_rules.rule_catalog(),
                    'channels': {
                        'instance': state['instance'],
                        'space': state['space'],
                        'effective_email_channel': state['effective_email_channel'],
                    },
                    'recipients': [
                        {
                            'account_uuid': item['account_uuid'],
                            'email': item['email'],
                            'role': item['role'],
                            'space_linked': item['space_linked'],
                            'muted': item['account_uuid'] in muted,
                        }
                        for item in state['recipients']
                    ],
                    'webhooks': [
                        {'id': item['id'], 'name': item['name'], 'enabled': bool(item['enabled'])} for item in webhooks
                    ],
                }
            )

        @self.route('/summary', methods=['GET'], permission=Permission.AUDIT_VIEW)
        async def _(request_context: RequestContext) -> str:
            return self.success(data=await self.ap.alert_service.summary(request_context.workspace_uuid))

        @self.route('/settings', methods=['PUT'], permission=Permission.WORKSPACE_UPDATE)
        async def _(request_context: RequestContext) -> str:
            payload = await quart.request.get_json(silent=True) or {}
            try:
                settings = await self.ap.alert_service.update_settings(request_context.workspace_uuid, payload)
            except ValueError as exc:
                return self.http_status(400, -1, str(exc))
            return self.success(data={'settings': settings})

        @self.route('/incidents', methods=['GET'], permission=Permission.AUDIT_VIEW)
        async def _(request_context: RequestContext) -> str:
            state = quart.request.args.get('state') or None
            try:
                limit = int(quart.request.args.get('limit', 50))
            except ValueError:
                limit = 50
            incidents = await self.ap.alert_service.list_incidents(
                request_context.workspace_uuid, state=state, limit=limit
            )
            return self.success(data={'incidents': incidents})

        @self.route('/deliveries', methods=['GET'], permission=Permission.AUDIT_VIEW)
        async def _(request_context: RequestContext) -> str:
            try:
                limit = int(quart.request.args.get('limit', 50))
            except ValueError:
                limit = 50
            deliveries = await self.ap.alert_service.list_deliveries(request_context.workspace_uuid, limit=limit)
            return self.success(data={'deliveries': deliveries})

        @self.route('/test', methods=['POST'], permission=Permission.WORKSPACE_UPDATE)
        async def _(request_context: RequestContext) -> str:
            try:
                deliveries = await self.ap.alert_service.send_test(request_context.workspace_uuid)
            except PermissionError as exc:
                return self.http_status(429, -1, str(exc))
            return self.success(data={'deliveries': deliveries})
