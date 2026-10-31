from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import quart

from langbot.pkg.api.http.controller.groups.knowledge.base import KnowledgeBaseRouterGroup
from langbot.pkg.api.http.controller.groups.pipelines.pipelines import PipelinesRouterGroup
from langbot.pkg.api.http.controller.groups.provider.models import LLMModelsRouterGroup
from langbot.pkg.api.http.controller.groups.provider.providers import ModelProvidersRouterGroup
from langbot.pkg.api.http.controller.groups.resources.mcp import MCPRouterGroup
from langbot.pkg.api.http.controller.groups.webhook_mgmt import WebhookManagementRouterGroup
from langbot.pkg.api.http.service.secrets import mask_secret_value, redact_secrets


pytestmark = pytest.mark.asyncio
WORKSPACE_UUID = '11111111-1111-4111-8111-111111111111'

RAW_PIPELINE = {
    'uuid': 'pipeline-test',
    'config': {'ai': {'n8n': {'webhook-url': 'https://hook.invalid/bearer-secret'}}},
}
RAW_MODEL = {
    'uuid': 'model-test',
    'provider_uuid': 'provider-test',
    'extra_args': {'headers': {'Authorization': 'Bearer model-secret'}},
}
RAW_PROVIDER = {
    'uuid': 'provider-test',
    'base_url': 'https://provider-user:provider-password@provider.invalid/v1?token=url-secret&region=sg',
    'api_keys': ['provider-secret'],
}
RAW_MCP_SERVER = {
    'uuid': 'mcp-test',
    'name': 'MCP Test',
    'extra_args': {'url': 'https://mcp-user:mcp-password@mcp.invalid/connect?api_key=url-secret&transport=http'},
}
RAW_KNOWLEDGE_BASE = {
    'uuid': 'kb-test',
    'creation_settings': {'dify_apikey': 'knowledge-secret'},
}
RAW_WEBHOOK = {'id': 1, 'url': 'https://hook.invalid/path?token=webhook-secret'}


def _access(role: str):
    return SimpleNamespace(
        workspace=SimpleNamespace(uuid=WORKSPACE_UUID),
        membership=SimpleNamespace(uuid='membership-test', role=role, projection_revision=1),
        execution=SimpleNamespace(instance_uuid='instance-test', placement_generation=1),
    )


async def _create_client(role: str):
    application = SimpleNamespace()
    account = SimpleNamespace(uuid='account-test', user='test@example.com')
    application.user_service = SimpleNamespace(get_authenticated_account=AsyncMock(return_value=account))
    application.apikey_service = SimpleNamespace(authenticate_api_key=AsyncMock(return_value=None))
    application.workspace_collaboration_service = SimpleNamespace(
        resolve_account_workspace=AsyncMock(return_value=_access(role))
    )

    async def get_pipelines(_context, *_args, include_secret=False):
        value = copy.deepcopy(RAW_PIPELINE)
        return [value] if include_secret else [redact_secrets(value)]

    async def get_pipeline(_context, _uuid, *, include_secret=False):
        value = copy.deepcopy(RAW_PIPELINE)
        return value if include_secret else redact_secrets(value)

    application.pipeline_service = SimpleNamespace(
        get_pipelines=AsyncMock(side_effect=get_pipelines),
        get_pipeline=AsyncMock(side_effect=get_pipeline),
    )
    application.plugin_connector = SimpleNamespace(list_plugins=AsyncMock(return_value=[]))
    application.mcp_service = SimpleNamespace(
        get_mcp_servers=AsyncMock(return_value=[redact_secrets(copy.deepcopy(RAW_MCP_SERVER))])
    )
    application.skill_service = SimpleNamespace(list_skills=AsyncMock(return_value=[]))

    async def get_models_by_provider(_context, _provider_uuid, *, include_secret=False):
        value = copy.deepcopy(RAW_MODEL)
        return [value] if include_secret else [redact_secrets(value)]

    application.llm_model_service = SimpleNamespace(
        get_llm_models_by_provider=AsyncMock(side_effect=get_models_by_provider)
    )

    async def get_providers(_context, *, include_secret=False):
        value = copy.deepcopy(RAW_PROVIDER)
        return [value] if include_secret else [redact_secrets(value)]

    application.provider_service = SimpleNamespace(
        get_providers=AsyncMock(side_effect=get_providers),
        get_provider_model_counts=AsyncMock(return_value={'llm_count': 0, 'embedding_count': 0, 'rerank_count': 0}),
    )

    async def get_knowledge_bases(_context, *, include_secret=False):
        value = copy.deepcopy(RAW_KNOWLEDGE_BASE)
        return [value] if include_secret else [redact_secrets(value)]

    application.knowledge_service = SimpleNamespace(get_knowledge_bases=AsyncMock(side_effect=get_knowledge_bases))

    async def get_webhooks(_context, *, include_secret=False):
        value = copy.deepcopy(RAW_WEBHOOK)
        if not include_secret:
            value['url'] = mask_secret_value(value['url'])
        return [value]

    application.webhook_service = SimpleNamespace(get_webhooks=AsyncMock(side_effect=get_webhooks))

    quart_app = quart.Quart(__name__)
    for router_type in (
        PipelinesRouterGroup,
        LLMModelsRouterGroup,
        ModelProvidersRouterGroup,
        MCPRouterGroup,
        KnowledgeBaseRouterGroup,
        WebhookManagementRouterGroup,
    ):
        await router_type(application, quart_app).initialize()
    return application, quart_app.test_client()


def _headers() -> dict[str, str]:
    return {'Authorization': 'Bearer test-token', 'X-Workspace-Id': WORKSPACE_UUID}


@pytest.mark.parametrize('role', ['viewer', 'operator'])
async def test_viewer_and_operator_resource_reads_are_redacted(role: str):
    application, client = await _create_client(role)

    pipeline = (await (await client.get('/api/v1/pipelines', headers=_headers())).get_json())['data']['pipelines'][0]
    model = (
        await (
            await client.get(
                '/api/v1/provider/models/llm?provider_uuid=provider-test',
                headers=_headers(),
            )
        ).get_json()
    )['data']['models'][0]
    provider = (await (await client.get('/api/v1/provider/providers', headers=_headers())).get_json())['data'][
        'providers'
    ][0]
    mcp_server = (await (await client.get('/api/v1/mcp/servers', headers=_headers())).get_json())['data']['servers'][0]
    knowledge_base = (await (await client.get('/api/v1/knowledge/bases', headers=_headers())).get_json())['data'][
        'bases'
    ][0]
    webhook = (await (await client.get('/api/v1/webhooks', headers=_headers())).get_json())['data']['webhooks'][0]

    assert pipeline['config']['ai']['n8n']['webhook-url'] == '***'
    assert model['extra_args']['headers']['Authorization'] == '***'
    assert provider['api_keys'] == ['***']
    assert provider['base_url'] == 'https://***@provider.invalid/v1?token=***&region=sg'
    assert mcp_server['extra_args']['url'] == 'https://***@mcp.invalid/connect?api_key=***&transport=http'
    assert knowledge_base['creation_settings']['dify_apikey'] == '***'
    assert webhook['url'] == '***'
    assert application.pipeline_service.get_pipelines.await_args.kwargs['include_secret'] is False
    assert application.llm_model_service.get_llm_models_by_provider.await_args.kwargs['include_secret'] is False
    assert application.provider_service.get_providers.await_args.kwargs['include_secret'] is False
    assert application.knowledge_service.get_knowledge_bases.await_args.kwargs['include_secret'] is False
    assert application.webhook_service.get_webhooks.await_args.kwargs['include_secret'] is False


async def test_resource_manager_receives_credentials_needed_for_management():
    application, client = await _create_client('developer')

    pipeline = (await (await client.get('/api/v1/pipelines', headers=_headers())).get_json())['data']['pipelines'][0]
    model = (
        await (
            await client.get(
                '/api/v1/provider/models/llm?provider_uuid=provider-test',
                headers=_headers(),
            )
        ).get_json()
    )['data']['models'][0]
    provider = (await (await client.get('/api/v1/provider/providers', headers=_headers())).get_json())['data'][
        'providers'
    ][0]
    knowledge_base = (await (await client.get('/api/v1/knowledge/bases', headers=_headers())).get_json())['data'][
        'bases'
    ][0]
    webhook = (await (await client.get('/api/v1/webhooks', headers=_headers())).get_json())['data']['webhooks'][0]

    assert pipeline == RAW_PIPELINE
    assert model == RAW_MODEL
    assert provider['api_keys'] == ['provider-secret']
    assert knowledge_base == RAW_KNOWLEDGE_BASE
    assert webhook == RAW_WEBHOOK
    assert application.pipeline_service.get_pipelines.await_args.kwargs['include_secret'] is True
    assert application.llm_model_service.get_llm_models_by_provider.await_args.kwargs['include_secret'] is True
    assert application.provider_service.get_providers.await_args.kwargs['include_secret'] is True
    assert application.knowledge_service.get_knowledge_bases.await_args.kwargs['include_secret'] is True
    assert application.webhook_service.get_webhooks.await_args.kwargs['include_secret'] is True
