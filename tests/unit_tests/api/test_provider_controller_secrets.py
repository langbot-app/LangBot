from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.provider.models import (
    EmbeddingModelsRouterGroup,
    LLMModelsRouterGroup,
    RerankModelsRouterGroup,
)
from langbot.pkg.api.http.controller.groups.provider.providers import ModelProvidersRouterGroup
from langbot.pkg.api.http.controller.groups.provider.query import resolve_include_secret
from langbot.pkg.api.http.service.secrets import redact_secrets


pytestmark = pytest.mark.asyncio

RAW_PROVIDER = {
    'uuid': 'provider-test',
    'name': 'Test Provider',
    'api_keys': ['provider-secret'],
}
RAW_MODEL = {
    'uuid': 'model-test',
    'name': 'Test Model',
    'extra_args': {'headers': {'Authorization': 'Bearer model-secret'}},
}


def _access(role: str):
    return SimpleNamespace(
        execution=SimpleNamespace(instance_uuid='instance-test', placement_generation=1),
        workspace=SimpleNamespace(uuid='workspace-test'),
        membership=SimpleNamespace(uuid='membership-test', role=role, projection_revision=1),
    )


def _project(value: dict, include_secret: bool) -> dict:
    value = copy.deepcopy(value)
    return value if include_secret else redact_secrets(value)


async def _create_client(role: str):
    application = SimpleNamespace()
    account = SimpleNamespace(uuid='account-test', user='test@example.com')
    application.user_service = SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account))
    application.apikey_service = SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None))
    application.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(return_value=_access(role))
    )

    async def get_providers(_context, *, include_secret=False):
        return [_project(RAW_PROVIDER, include_secret)]

    async def get_provider(_context, _uuid, *, include_secret=False):
        return _project(RAW_PROVIDER, include_secret)

    application.provider_service = SimpleNamespace(
        get_providers=AsyncMock(side_effect=get_providers),
        get_provider=AsyncMock(side_effect=get_provider),
        get_provider_model_counts=AsyncMock(
            return_value={'llm_count': 1, 'embedding_count': 1, 'rerank_count': 1}
        ),
    )

    def model_service(list_name: str, get_name: str):
        async def get_models(_context, *, include_secret=False):
            return [_project(RAW_MODEL, include_secret)]

        async def get_model(_context, _uuid, *, include_secret=False):
            return _project(RAW_MODEL, include_secret)

        return SimpleNamespace(
            **{
                list_name: AsyncMock(side_effect=get_models),
                get_name: AsyncMock(side_effect=get_model),
            }
        )

    application.llm_model_service = model_service('get_llm_models', 'get_llm_model')
    application.embedding_models_service = model_service('get_embedding_models', 'get_embedding_model')
    application.rerank_models_service = model_service('get_rerank_models', 'get_rerank_model')

    quart_app = quart.Quart(__name__)
    for router_type in (
        ModelProvidersRouterGroup,
        LLMModelsRouterGroup,
        EmbeddingModelsRouterGroup,
        RerankModelsRouterGroup,
    ):
        await router_type(application, quart_app).initialize()
    return application, quart_app.test_client()


def _headers() -> dict[str, str]:
    return {'Authorization': 'Bearer test-token'}


@pytest.mark.parametrize(
    ('raw_value', 'permitted', 'expected', 'error'),
    [
        (None, True, True, None),
        (None, False, False, None),
        ('false', True, False, None),
        ('true', True, True, None),
        ('true', False, False, None),
        ('invalid', True, False, 'include_secret must be either true or false'),
    ],
)
def test_resolve_include_secret(raw_value, permitted, expected, error):
    assert resolve_include_secret(raw_value, permitted=permitted) == (expected, error)


@pytest.mark.parametrize(
    'endpoint',
    [
        '/api/v1/provider/providers',
        '/api/v1/provider/models/llm',
        '/api/v1/provider/models/embedding',
        '/api/v1/provider/models/rerank',
    ],
)
async def test_default_preserves_secrets_and_explicit_false_redacts_high_permission_reads(endpoint):
    application, client = await _create_client('developer')

    default_response = await client.get(endpoint, headers=_headers())
    false_response = await client.get(f'{endpoint}?include_secret=false', headers=_headers())

    assert default_response.status_code == 200
    assert false_response.status_code == 200
    default_data = await default_response.get_json()
    false_data = await false_response.get_json()
    default_value = default_data['data'].get('providers', default_data['data'].get('models'))[0]
    false_value = false_data['data'].get('providers', false_data['data'].get('models'))[0]
    assert '***' not in str(default_value)
    assert '***' in str(false_value)


@pytest.mark.parametrize(
    'endpoint',
    [
        '/api/v1/provider/providers',
        '/api/v1/provider/models/llm',
        '/api/v1/provider/models/embedding',
        '/api/v1/provider/models/rerank',
    ],
)
async def test_explicit_true_does_not_grant_low_permission_reads(endpoint):
    _application, client = await _create_client('viewer')

    response = await client.get(f'{endpoint}?include_secret=true', headers=_headers())

    assert response.status_code == 200
    data = await response.get_json()
    value = data['data'].get('providers', data['data'].get('models'))[0]
    assert '***' in str(value)


@pytest.mark.parametrize(
    'endpoint',
    [
        '/api/v1/provider/providers',
        '/api/v1/provider/providers/provider-test',
        '/api/v1/provider/models/llm',
        '/api/v1/provider/models/llm/model-test',
        '/api/v1/provider/models/embedding',
        '/api/v1/provider/models/embedding/model-test',
        '/api/v1/provider/models/rerank',
        '/api/v1/provider/models/rerank/model-test',
    ],
)
async def test_invalid_include_secret_returns_bad_request(endpoint):
    _application, client = await _create_client('developer')

    response = await client.get(f'{endpoint}?include_secret=maybe', headers=_headers())

    assert response.status_code == 400
    assert (await response.get_json())['msg'] == 'include_secret must be either true or false'
