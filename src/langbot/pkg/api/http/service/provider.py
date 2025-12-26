from __future__ import annotations

import uuid

import sqlalchemy

from ....core import app
from ....entity.persistence import model as persistence_model


class ModelProviderService:
    """Service for managing model providers"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_providers(self) -> list[dict]:
        """Get all providers"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_model.ModelProvider))
        providers = result.all()
        providers_list = []
        for p in providers:
            provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, p)
            # Parse api_keys if it's a JSON string
            if isinstance(provider_dict.get('api_keys'), str):
                import json

                try:
                    provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
                except Exception:
                    provider_dict['api_keys'] = []
            providers_list.append(provider_dict)
        return providers_list

    async def get_provider(self, provider_uuid: str) -> dict | None:
        """Get a single provider by UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )
        provider = result.first()
        if provider is None:
            return None
        provider_dict = self.ap.persistence_mgr.serialize_model(persistence_model.ModelProvider, provider)
        # Parse api_keys if it's a JSON string
        if isinstance(provider_dict.get('api_keys'), str):
            import json

            try:
                provider_dict['api_keys'] = json.loads(provider_dict['api_keys'])
            except Exception:
                provider_dict['api_keys'] = []
        return provider_dict

    async def create_provider(self, provider_data: dict) -> str:
        """Create a new provider"""
        provider_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.ModelProvider).values(**provider_data)
        )
        return provider_data['uuid']

    async def update_provider(self, provider_uuid: str, provider_data: dict) -> None:
        """Update an existing provider"""
        if 'uuid' in provider_data:
            del provider_data['uuid']
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.ModelProvider)
            .where(persistence_model.ModelProvider.uuid == provider_uuid)
            .values(**provider_data)
        )
        # Reload all models using this provider
        await self.ap.model_mgr.load_models_from_db()

    async def delete_provider(self, provider_uuid: str) -> None:
        """Delete a provider (only if no models reference it)"""
        # Check if any models use this provider
        llm_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.LLMModel).where(
                persistence_model.LLMModel.provider_uuid == provider_uuid
            )
        )
        if llm_result.first() is not None:
            raise ValueError('Cannot delete provider: LLM models still reference it')

        embedding_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.EmbeddingModel).where(
                persistence_model.EmbeddingModel.provider_uuid == provider_uuid
            )
        )
        if embedding_result.first() is not None:
            raise ValueError('Cannot delete provider: Embedding models still reference it')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )

    async def get_provider_model_counts(self, provider_uuid: str) -> dict:
        """Get count of models using this provider"""
        llm_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(persistence_model.LLMModel)
            .where(persistence_model.LLMModel.provider_uuid == provider_uuid)
        )
        llm_count = llm_result.scalar() or 0

        embedding_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(persistence_model.EmbeddingModel)
            .where(persistence_model.EmbeddingModel.provider_uuid == provider_uuid)
        )
        embedding_count = embedding_result.scalar() or 0

        return {'llm_count': llm_count, 'embedding_count': embedding_count}

    async def find_or_create_provider(self, requester: str, base_url: str, api_keys: list) -> str:
        """Find existing provider or create new one"""
        # Try to find existing provider with same config
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.requester == requester,
                persistence_model.ModelProvider.base_url == base_url,
            )
        )
        for provider in result.all():
            if sorted(provider.api_keys or []) == sorted(api_keys or []):
                return provider.uuid

        # Create new provider
        provider_name = requester
        if base_url:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(base_url)
                provider_name = parsed.netloc or requester
            except Exception:
                pass

        return await self.create_provider(
            {
                'name': provider_name,
                'requester': requester,
                'base_url': base_url,
                'api_keys': api_keys or [],
            }
        )
