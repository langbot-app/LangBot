from __future__ import annotations

import sqlalchemy

from ....core import app
from ....entity.persistence import webhook


class WebhookService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_webhooks(self) -> list[dict]:
        """Get all webhooks"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(webhook.Webhook))

        webhooks = result.all()
        return [self.ap.persistence_mgr.serialize_model(webhook.Webhook, wh) for wh in webhooks]

    async def create_webhook(self, name: str, url: str, description: str = '', enabled: bool = True) -> dict:
        """Create a new webhook"""
        webhook_data = {'name': name, 'url': url, 'description': description, 'enabled': enabled}

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(webhook.Webhook).values(**webhook_data))

        # Retrieve the created webhook
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.url == url).order_by(webhook.Webhook.id.desc())
        )
        created_webhook = result.first()

        return self.ap.persistence_mgr.serialize_model(webhook.Webhook, created_webhook)

    async def get_webhook(self, webhook_id: int) -> dict | None:
        """Get a specific webhook by ID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.id == webhook_id)
        )

        wh = result.first()

        if wh is None:
            return None

        return self.ap.persistence_mgr.serialize_model(webhook.Webhook, wh)

    async def update_webhook(
        self, webhook_id: int, name: str = None, url: str = None, description: str = None, enabled: bool = None
    ) -> None:
        """Update a webhook's metadata"""
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if url is not None:
            update_data['url'] = url
        if description is not None:
            update_data['description'] = description
        if enabled is not None:
            update_data['enabled'] = enabled

        if update_data:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(webhook.Webhook).where(webhook.Webhook.id == webhook_id).values(**update_data)
            )

    async def delete_webhook(self, webhook_id: int) -> None:
        """Delete a webhook"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(webhook.Webhook).where(webhook.Webhook.id == webhook_id)
        )

    async def get_enabled_webhooks(self) -> list[dict]:
        """Get all enabled webhooks"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.enabled == True)
        )

        webhooks = result.all()
        return [self.ap.persistence_mgr.serialize_model(webhook.Webhook, wh) for wh in webhooks]
