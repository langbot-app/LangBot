from __future__ import annotations

import secrets
import sqlalchemy

from ....core import app
from ....entity.persistence import apikey


class ApiKeyService:
    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_api_keys(self) -> list[dict]:
        """Get all API keys"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(apikey.ApiKey))

        keys = result.all()
        return [self.ap.persistence_mgr.serialize_model(apikey.ApiKey, key) for key in keys]

    async def create_api_key(self, name: str, description: str = '') -> dict:
        """Create a new API key"""
        # Generate a secure random API key
        key = f'lbk_{secrets.token_urlsafe(32)}'

        key_data = {'name': name, 'key': key, 'description': description}

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(apikey.ApiKey).values(**key_data))

        # Retrieve the created key
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.key == key)
        )
        created_key = result.first()

        return self.ap.persistence_mgr.serialize_model(apikey.ApiKey, created_key)

    async def get_api_key(self, key_id: int) -> dict | None:
        """Get a specific API key by ID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.id == key_id)
        )

        key = result.first()

        if key is None:
            return None

        return self.ap.persistence_mgr.serialize_model(apikey.ApiKey, key)

    async def verify_api_key(self, key: str) -> bool:
        """Verify if an API key is valid"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.key == key)
        )

        key_obj = result.first()
        return key_obj is not None

    async def delete_api_key(self, key_id: int) -> None:
        """Delete an API key"""
        await self.ap.persistence_mgr.execute_async(sqlalchemy.delete(apikey.ApiKey).where(apikey.ApiKey.id == key_id))

    async def update_api_key(self, key_id: int, name: str = None, description: str = None) -> None:
        """Update an API key's metadata (name, description)"""
        update_data = {}
        if name is not None:
            update_data['name'] = name
        if description is not None:
            update_data['description'] = description

        if update_data:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(apikey.ApiKey).where(apikey.ApiKey.id == key_id).values(**update_data)
            )
