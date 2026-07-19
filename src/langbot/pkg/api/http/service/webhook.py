from __future__ import annotations

import sqlalchemy

from ....core import app
from ....entity.persistence import webhook
from .secrets import SECRET_MASK, mask_secret_value, restore_secret_placeholders
from .tenant import TenantContext, require_workspace_uuid, scope_statement


class WebhookService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def _serialize_webhook(self, entity, *, include_secret: bool) -> dict:
        serialized = self.ap.persistence_mgr.serialize_model(webhook.Webhook, entity)
        if not include_secret:
            serialized = serialized.copy()
            serialized['url'] = mask_secret_value(serialized.get('url'))
        return serialized

    async def get_webhooks(self, context: TenantContext, *, include_secret: bool = False) -> list[dict]:
        """Get all webhooks"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(webhook.Webhook), webhook.Webhook, context)
        )

        webhooks = result.all()
        return [self._serialize_webhook(wh, include_secret=include_secret) for wh in webhooks]

    async def create_webhook(
        self,
        context: TenantContext,
        name: str,
        url: str,
        description: str = '',
        enabled: bool = True,
    ) -> dict:
        """Create a new webhook"""
        workspace_uuid = require_workspace_uuid(context)
        url = restore_secret_placeholders(url, sensitive=True)
        webhook_data = {
            'workspace_uuid': workspace_uuid,
            'name': name,
            'url': url,
            'description': description,
            'enabled': enabled,
        }

        insert_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(webhook.Webhook).values(**webhook_data)
        )

        # Retrieve the created webhook
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.id == insert_result.inserted_primary_key[0]),
                webhook.Webhook,
                workspace_uuid,
            )
        )
        created_webhook = result.first()

        return self.ap.persistence_mgr.serialize_model(webhook.Webhook, created_webhook)

    async def get_webhook(
        self,
        context: TenantContext,
        webhook_id: int,
        *,
        include_secret: bool = False,
    ) -> dict | None:
        """Get a specific webhook by ID"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.id == webhook_id),
                webhook.Webhook,
                context,
            )
        )

        wh = result.first()

        if wh is None:
            return None

        return self._serialize_webhook(wh, include_secret=include_secret)

    async def update_webhook(
        self,
        context: TenantContext,
        webhook_id: int,
        name: str | None = None,
        url: str | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """Update a webhook's metadata"""
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if url is not None:
            if url == SECRET_MASK:
                current = await self.get_webhook(context, webhook_id, include_secret=True)
                if current is None:
                    return False
                url = restore_secret_placeholders(url, current.get('url'), sensitive=True)
            update_data['url'] = url
        if description is not None:
            update_data['description'] = description
        if enabled is not None:
            update_data['enabled'] = enabled

        if update_data:
            result = await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.update(webhook.Webhook).where(webhook.Webhook.id == webhook_id).values(**update_data),
                    webhook.Webhook,
                    context,
                )
            )
            return (result.rowcount or 0) > 0
        return await self.get_webhook(context, webhook_id) is not None

    async def delete_webhook(self, context: TenantContext, webhook_id: int) -> bool:
        """Delete a webhook"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(webhook.Webhook).where(webhook.Webhook.id == webhook_id),
                webhook.Webhook,
                context,
            )
        )
        return (result.rowcount or 0) > 0

    async def get_enabled_webhooks(self, context: TenantContext) -> list[dict]:
        """Get all enabled webhooks"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(webhook.Webhook).where(webhook.Webhook.enabled == True),
                webhook.Webhook,
                context,
            )
        )

        webhooks = result.all()
        return [self.ap.persistence_mgr.serialize_model(webhook.Webhook, wh) for wh in webhooks]
