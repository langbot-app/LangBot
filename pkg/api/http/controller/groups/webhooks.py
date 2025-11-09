import quart

from .. import group


@group.group_class('webhooks', '/api/v1/webhooks')
class WebhooksRouterGroup(group.RouterGroup):
    async def initialize(self) -> None:
        @self.route('', methods=['GET', 'POST'])
        async def _() -> str:
            if quart.request.method == 'GET':
                webhooks = await self.ap.webhook_service.get_webhooks()
                return self.success(data={'webhooks': webhooks})
            elif quart.request.method == 'POST':
                json_data = await quart.request.json
                name = json_data.get('name', '')
                url = json_data.get('url', '')
                description = json_data.get('description', '')
                enabled = json_data.get('enabled', True)

                if not name:
                    return self.http_status(400, -1, 'Name is required')
                if not url:
                    return self.http_status(400, -1, 'URL is required')

                webhook = await self.ap.webhook_service.create_webhook(name, url, description, enabled)
                return self.success(data={'webhook': webhook})

        @self.route('/<int:webhook_id>', methods=['GET', 'PUT', 'DELETE'])
        async def _(webhook_id: int) -> str:
            if quart.request.method == 'GET':
                webhook = await self.ap.webhook_service.get_webhook(webhook_id)
                if webhook is None:
                    return self.http_status(404, -1, 'Webhook not found')
                return self.success(data={'webhook': webhook})

            elif quart.request.method == 'PUT':
                json_data = await quart.request.json
                name = json_data.get('name')
                url = json_data.get('url')
                description = json_data.get('description')
                enabled = json_data.get('enabled')

                await self.ap.webhook_service.update_webhook(webhook_id, name, url, description, enabled)
                return self.success()

            elif quart.request.method == 'DELETE':
                await self.ap.webhook_service.delete_webhook(webhook_id)
                return self.success()
