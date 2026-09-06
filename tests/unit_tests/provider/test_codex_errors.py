from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from quart import Quart
from sqlalchemy.exc import SQLAlchemyError

from langbot.pkg.api.http.controller.groups.provider.models import LLMModelsRouterGroup
from langbot.pkg.api.http.authz import Permission
from langbot.pkg.provider.modelmgr.requesters.codex import CodexRequester
from tests.unit_tests.provider.test_codex import requester, MODEL, stream


CASES = [
    (400, 400, 'codex_invalid_request'),
    (401, 400, 'codex_reauthentication_required'),
    (403, 403, 'codex_access_denied'),
    (429, 429, 'codex_rate_limited'),
    (500, 502, 'codex_upstream_failure'),
]


@pytest.mark.asyncio
@pytest.mark.parametrize('upstream,status,code', CASES)
async def test_requester_safe_error(monkeypatch, upstream, status, code):
    obj = requester(monkeypatch, lambda request: httpx.Response(upstream, text='credential-secret'))
    with pytest.raises(Exception) as caught:
        await obj.invoke_llm(None, MODEL, [])
    error = caught.value
    assert getattr(error, 'status_code', None) == status
    assert error.error_code == code
    assert 'secret' not in str(error)
    if upstream == 429:
        assert 'rate limit' in str(error).lower()
        assert 'usage limit reached' not in str(error).lower()


@pytest.mark.asyncio
@pytest.mark.parametrize('events', [[{'type': 'response.failed', 'error': 'credential-secret'}], []])
async def test_stream_safe_error(monkeypatch, events):
    obj = requester(monkeypatch, lambda request: stream(events))
    with pytest.raises(Exception) as caught:
        await obj.invoke_llm(None, MODEL, [])
    assert getattr(caught.value, 'status_code', None) == 502
    assert caught.value.error_code == 'codex_upstream_failure'
    assert 'secret' not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'kind,code', [('usage_limit_reached', 'codex_usage_limit_reached'), ('unknown', 'codex_rate_limited')]
)
async def test_allowlisted_usage_error(monkeypatch, kind, code):
    obj = requester(
        monkeypatch,
        lambda request: httpx.Response(
            429, json={'error': {'type': kind, 'message': 'credential-secret', 'resets_at': 1789043289}}
        ),
    )
    with pytest.raises(Exception) as caught:
        await obj.invoke_llm(None, MODEL, [])
    assert caught.value.error_code == code
    assert 'secret' not in str(caught.value)


async def client_for(error):
    app = Quart(__name__)
    ap = SimpleNamespace(logger=Mock(), llm_model_service=SimpleNamespace(test_llm_model=AsyncMock(side_effect=error)))
    router = LLMModelsRouterGroup(ap, app)
    router._authenticate_api_key = AsyncMock(
        return_value=SimpleNamespace(
            workspace_uuid='w',
            workspace=SimpleNamespace(permissions=frozenset({Permission.PROVIDER_SECRET_MANAGE.value})),
        )
    )
    await router.initialize()
    return app.test_client(), ap


@pytest.mark.asyncio
@pytest.mark.parametrize('upstream,status,code', CASES)
async def test_real_model_test_route_safe_error(upstream, status, code):
    error = CodexRequester._http_error(upstream)
    client, ap = await client_for(error)
    response = await client.post('/api/v1/provider/models/llm/model/test', json={}, headers={'X-API-Key': 'synthetic'})
    body = await response.get_json()
    assert response.status_code == status
    assert body['code'] == code
    assert body['msg'] == str(error)
    ap.logger.error.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('error', [ValueError('private-value-secret'), SQLAlchemyError('private-sql-secret')])
async def test_real_model_test_route_unexpected_errors_hidden(error):
    client, _ = await client_for(error)
    response = await client.post('/api/v1/provider/models/llm/model/test', json={}, headers={'X-API-Key': 'synthetic'})
    assert response.status_code == 500
    assert 'secret' not in await response.get_data(as_text=True)
