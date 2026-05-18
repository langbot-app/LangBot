from __future__ import annotations

import uuid
import traceback

import sqlalchemy

from ....core import app
from ....entity.persistence import model as persistence_model


class ModelProviderService:
    """Service for managing model providers"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    @staticmethod
    def _normalize_api_keys(api_keys: str | list[str] | tuple[str, ...] | None) -> list[str]:
        if api_keys is None:
            return []

        raw_keys = [api_keys] if isinstance(api_keys, str) else list(api_keys)
        normalized_keys = []
        seen_keys = set()

        for raw_key in raw_keys:
            normalized_key = raw_key.strip() if isinstance(raw_key, str) else ''
            if not normalized_key or normalized_key in seen_keys:
                continue
            normalized_keys.append(normalized_key)
            seen_keys.add(normalized_key)

        return normalized_keys

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
        provider_data['api_keys'] = self._normalize_api_keys(provider_data.get('api_keys'))
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_model.ModelProvider).values(**provider_data)
        )

        # load to runtime
        runtime_provider = await self.ap.model_mgr.load_provider(provider_data)
        self.ap.model_mgr.provider_dict[runtime_provider.provider_entity.uuid] = runtime_provider
        return provider_data['uuid']

    async def update_provider(self, provider_uuid: str, provider_data: dict) -> None:
        """Update an existing provider"""
        if 'uuid' in provider_data:
            del provider_data['uuid']
        if 'api_keys' in provider_data:
            provider_data['api_keys'] = self._normalize_api_keys(provider_data.get('api_keys'))
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.ModelProvider)
            .where(persistence_model.ModelProvider.uuid == provider_uuid)
            .values(**provider_data)
        )
        await self.ap.model_mgr.reload_provider(provider_uuid)

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

        rerank_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_model.RerankModel).where(
                persistence_model.RerankModel.provider_uuid == provider_uuid
            )
        )
        if rerank_result.first() is not None:
            raise ValueError('Cannot delete provider: Rerank models still reference it')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_model.ModelProvider).where(
                persistence_model.ModelProvider.uuid == provider_uuid
            )
        )

        await self.ap.model_mgr.remove_provider(provider_uuid)

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

        rerank_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count())
            .select_from(persistence_model.RerankModel)
            .where(persistence_model.RerankModel.provider_uuid == provider_uuid)
        )
        rerank_count = rerank_result.scalar() or 0

        return {'llm_count': llm_count, 'embedding_count': embedding_count, 'rerank_count': rerank_count}

    async def find_or_create_provider(self, requester: str, base_url: str, api_keys: list) -> str:
        """Find existing provider or create new one"""
        api_keys = self._normalize_api_keys(api_keys)

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
                'api_keys': api_keys,
            }
        )

    async def update_space_model_provider_api_keys(self, api_key: str) -> None:
        """Update Space model provider API keys"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_model.ModelProvider)
            .where(persistence_model.ModelProvider.uuid == '00000000-0000-0000-0000-000000000000')
            .values(api_keys=self._normalize_api_keys(api_key))
        )
        await self.ap.model_mgr.reload_provider('00000000-0000-0000-0000-000000000000')

    async def scan_provider_models(self, provider_uuid: str, model_type: str | None = None) -> dict:
        provider = await self.get_provider(provider_uuid)
        if provider is None:
            raise ValueError('provider not found')

        runtime_provider = await self.ap.model_mgr.load_provider(provider)

        try:
            scan_result = await runtime_provider.requester.scan_models(
                runtime_provider.token_mgr.get_token() if runtime_provider.token_mgr.tokens else None
            )
        except NotImplementedError:
            raise ValueError('current provider does not support model scanning')
        except Exception as exc:
            self.ap.logger.warning(
                f'Failed to scan models for provider {provider_uuid}: {exc}\n{traceback.format_exc()}'
            )
            raise ValueError(str(exc)) from exc

        if isinstance(scan_result, dict):
            scanned_models = scan_result.get('models', [])
            debug_info = scan_result.get('debug')
        else:
            scanned_models = scan_result
            debug_info = None

        llm_models = await self.ap.llm_model_service.get_llm_models_by_provider(provider_uuid)
        embedding_models = await self.ap.embedding_models_service.get_embedding_models_by_provider(provider_uuid)
        existing_llm_names = {model['name'] for model in llm_models}
        existing_embedding_names = {model['name'] for model in embedding_models}

        filtered_models = []
        for model in scanned_models:
            scanned_type = model.get('type', 'llm')
            if model_type and scanned_type != model_type:
                continue

            model_name = model.get('name') or model.get('id')
            if not model_name:
                continue

            filtered_models.append(
                {
                    'id': model.get('id', model_name),
                    'name': model_name,
                    'type': scanned_type,
                    'abilities': model.get('abilities', []),
                    'display_name': model.get('display_name'),
                    'description': model.get('description'),
                    'context_length': model.get('context_length'),
                    'owned_by': model.get('owned_by'),
                    'input_modalities': model.get('input_modalities', []),
                    'output_modalities': model.get('output_modalities', []),
                    'already_added': (
                        model_name in existing_embedding_names
                        if scanned_type == 'embedding'
                        else model_name in existing_llm_names
                    ),
                }
            )

        return {'models': filtered_models, 'debug': debug_info}
