"""Temporary Codex models use saved, tenant-scoped providers and synthetic SQLite credentials."""

import time
from types import SimpleNamespace

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.model import CodexCredential, ModelProvider
from langbot.pkg.provider.modelmgr.codex_auth import BASE_URL
from langbot.pkg.provider.modelmgr.modelmgr import ModelManager
from langbot.pkg.provider.modelmgr.requesters.codex import CodexRequester
from langbot.pkg.workspace.errors import WorkspaceNotFoundError
from tests.unit_tests.provider.conftest import (
    TEST_EXECUTION_CONTEXT,
    TEST_WORKSPACE_UUID,
    FakeProviderAPIRequester,
)


@pytest_asyncio.fixture
async def manager(tmp_path, mock_app_for_modelmgr):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "temporary-codex.db"}')
    async with engine.begin() as conn:
        await conn.run_sync(ModelProvider.__table__.create)
        await conn.run_sync(CodexCredential.__table__.create)
        for uuid, workspace, kind in (
            ('saved', TEST_WORKSPACE_UUID, 'openai-codex'),
            ('foreign', 'another-workspace', 'openai-codex'),
            ('api', TEST_WORKSPACE_UUID, 'fake-requester'),
        ):
            await conn.execute(
                sa.insert(ModelProvider).values(
                    uuid=uuid,
                    workspace_uuid=workspace,
                    name='Saved provider',
                    requester=kind,
                    base_url=BASE_URL,
                    api_keys=[],
                )
            )
        await conn.execute(
            sa.insert(CodexCredential).values(
                provider_uuid='saved',
                workspace_uuid=TEST_WORKSPACE_UUID,
                payload={
                    'tokens': {
                        'access_token': 'synthetic-access',
                        'refresh_token': 'synthetic-refresh',
                        'account_id': 'synthetic-account',
                        'expires_at': time.time() + 3600,
                    }
                },
            )
        )

    async def execute(statement):
        async with engine.begin() as conn:
            return await conn.execute(statement)

    mock_app_for_modelmgr.persistence_mgr = SimpleNamespace(execute_async=execute)
    mgr = ModelManager(mock_app_for_modelmgr)
    mgr.requester_dict = {'openai-codex': CodexRequester, 'fake-requester': FakeProviderAPIRequester}
    try:
        yield mgr
    finally:
        await engine.dispose()


def info(provider_uuid='saved', **inline):
    result = {'name': 'codex-test', 'provider': {'requester': 'openai-codex', **inline}}
    if provider_uuid is not None:
        result['provider_uuid'] = provider_uuid
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'inline',
    [
        {},
        {'uuid': 'saved'},
        {
            'requester': 'fake-requester',
            'api_keys': ['untrusted'],
            'base_url': 'https://untrusted.invalid',
            'workspace_uuid': 'another-workspace',
        },
    ],
)
async def test_codex_temporary_model_resolves_saved_provider_and_real_credentials(manager, inline):
    model = await manager.init_temporary_runtime_llm_model(TEST_EXECUTION_CONTEXT, info(**inline))
    provider = model.provider
    assert provider.provider_entity.uuid == 'saved'
    assert provider.provider_entity.requester == 'openai-codex'
    assert provider.provider_entity.api_keys == []
    assert provider.provider_entity.base_url == BASE_URL
    assert isinstance(provider.requester, CodexRequester)
    tokens = await provider.requester.auth.access(provider.requester.workspace, provider.requester.provider)
    assert tokens['access_token'] == 'synthetic-access'
    assert model.model_entity.provider_uuid == 'saved'


@pytest.mark.asyncio
async def test_codex_temporary_model_accepts_inline_saved_identity(manager):
    model = await manager.init_temporary_runtime_llm_model(TEST_EXECUTION_CONTEXT, info(None, uuid='saved'))
    assert model.provider.provider_entity.name == 'Saved provider'


@pytest.mark.asyncio
@pytest.mark.parametrize('identity', ['missing', 'foreign', None])
async def test_codex_temporary_model_rejects_unavailable_identity(manager, identity):
    with pytest.raises(WorkspaceNotFoundError):
        await manager.init_temporary_runtime_llm_model(
            TEST_EXECUTION_CONTEXT, info(identity, workspace_uuid='another-workspace')
        )


@pytest.mark.asyncio
async def test_codex_temporary_model_rejects_non_codex_saved_provider(manager):
    with pytest.raises(ValueError):
        await manager.init_temporary_runtime_llm_model(TEST_EXECUTION_CONTEXT, info('api'))


@pytest.mark.asyncio
async def test_codex_temporary_model_rejects_conflicting_identities(manager):
    with pytest.raises(ValueError):
        await manager.init_temporary_runtime_llm_model(TEST_EXECUTION_CONTEXT, info('saved', uuid='foreign'))


@pytest.mark.asyncio
async def test_api_key_temporary_model_preserves_inline_configuration(manager):
    model = await manager.init_temporary_runtime_llm_model(
        TEST_EXECUTION_CONTEXT,
        {
            'name': 'api-model',
            'provider': {
                'requester': 'fake-requester',
                'api_keys': ['synthetic-key'],
                'base_url': 'https://api.example.invalid',
            },
        },
    )
    assert model.provider.provider_entity.api_keys == ['synthetic-key']
    assert model.provider.provider_entity.base_url == 'https://api.example.invalid'
