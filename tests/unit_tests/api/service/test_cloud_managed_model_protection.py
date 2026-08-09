"""Cloud Runtime write protection for the managed LangBot Models catalog."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.api.http.service import model as model_service_module
from langbot.pkg.api.http.service.model import (
    EmbeddingModelsService,
    LLMModelsService,
    RerankModelsService,
    _assert_cloud_managed_provider_mutable,
)
from langbot.pkg.cloud.model_catalog import LANGBOT_MODELS_PROVIDER_REQUESTER


WORKSPACE = 'workspace-a'
PROVIDER = 'managed-provider'
MODEL = 'managed-model'


@pytest.mark.asyncio
async def test_managed_provider_guard_is_cloud_only(monkeypatch) -> None:
    async def managed_provider(_ap, _context, provider_uuid):
        assert provider_uuid == PROVIDER
        return {'uuid': PROVIDER, 'requester': LANGBOT_MODELS_PROVIDER_REQUESTER}

    monkeypatch.setattr(model_service_module, '_require_workspace_provider', managed_provider)
    application = SimpleNamespace(persistence_mgr=SimpleNamespace(mode=SimpleNamespace(value='cloud_runtime')))

    with pytest.raises(ValueError, match='managed by Cloud'):
        await _assert_cloud_managed_provider_mutable(
            application,
            WORKSPACE,
            PROVIDER,
        )

    application.persistence_mgr.mode.value = 'normal'
    await _assert_cloud_managed_provider_mutable(
        application,
        WORKSPACE,
        PROVIDER,
    )


@pytest.mark.parametrize(
    ('service_type', 'create_method', 'model_data'),
    [
        (LLMModelsService, 'create_llm_model', {'provider_uuid': PROVIDER, 'name': 'chat', 'abilities': []}),
        (EmbeddingModelsService, 'create_embedding_model', {'provider_uuid': PROVIDER, 'name': 'embedding'}),
        (RerankModelsService, 'create_rerank_model', {'provider_uuid': PROVIDER, 'name': 'rerank'}),
    ],
)
@pytest.mark.asyncio
async def test_all_model_types_reject_creation_under_managed_provider(
    monkeypatch,
    service_type,
    create_method: str,
    model_data: dict,
) -> None:
    guard = AsyncMock(side_effect=ValueError('LangBot Models is managed by Cloud and cannot be modified'))
    monkeypatch.setattr(model_service_module, '_assert_cloud_managed_provider_mutable', guard)
    application = SimpleNamespace(
        persistence_mgr=SimpleNamespace(),
        provider_service=SimpleNamespace(
            get_provider=AsyncMock(return_value={'uuid': PROVIDER, 'requester': LANGBOT_MODELS_PROVIDER_REQUESTER})
        ),
        model_mgr=None,
    )
    service = service_type(application)

    with pytest.raises(ValueError, match='managed by Cloud'):
        await getattr(service, create_method)(WORKSPACE, model_data)

    guard.assert_awaited_once()


@pytest.mark.parametrize(
    ('service_type', 'get_method', 'write_method', 'payload'),
    [
        (LLMModelsService, 'get_llm_model', 'update_llm_model', {'name': 'changed'}),
        (LLMModelsService, 'get_llm_model', 'delete_llm_model', None),
        (EmbeddingModelsService, 'get_embedding_model', 'update_embedding_model', {'name': 'changed'}),
        (EmbeddingModelsService, 'get_embedding_model', 'delete_embedding_model', None),
        (RerankModelsService, 'get_rerank_model', 'update_rerank_model', {'name': 'changed'}),
        (RerankModelsService, 'get_rerank_model', 'delete_rerank_model', None),
    ],
)
@pytest.mark.asyncio
async def test_all_model_types_reject_update_and_delete_for_managed_provider(
    monkeypatch,
    service_type,
    get_method: str,
    write_method: str,
    payload: dict | None,
) -> None:
    guard = AsyncMock(side_effect=ValueError('LangBot Models is managed by Cloud and cannot be modified'))
    monkeypatch.setattr(model_service_module, '_assert_cloud_managed_provider_mutable', guard)
    application = SimpleNamespace(persistence_mgr=SimpleNamespace(mode=SimpleNamespace(value='cloud_runtime')))
    service = service_type(application)
    monkeypatch.setattr(
        service,
        get_method,
        AsyncMock(return_value={'uuid': MODEL, 'provider_uuid': PROVIDER, 'extra_args': {}}),
    )

    args = (WORKSPACE, MODEL) if payload is None else (WORKSPACE, MODEL, payload)
    with pytest.raises(ValueError, match='managed by Cloud'):
        await getattr(service, write_method)(*args)

    guard.assert_awaited_once()
