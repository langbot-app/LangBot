"""Quota and credential failures map to clear, localized errors (LANG-318)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import litellm
import pytest
from aiohttp import web

from langbot.pkg.i18n import language_scope
from langbot.pkg.provider.modelmgr.errors import RequesterError
from langbot.pkg.provider.modelmgr.request_policy import CallState, RequestPolicy, current_call
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from tests.unit_tests.provider.test_reasoning_control import _runtime_model

QUOTA_MESSAGE = 'Insufficient balance or quota for this model. Please top up and try again.'


def _new_api_error(message: str, code: str) -> dict:
    """Error body shape returned by the New API gateway behind LangBot Models."""
    return {'error': {'message': message, 'type': 'new_api_error', 'code': code}}


CASES = [
    ('user-quota', 403, _new_api_error('用户额度不足, 剩余额度: ＄0.000000', 'insufficient_user_quota'), 'k'),
    ('token-quota', 403, _new_api_error('token quota is not enough', 'pre_consume_token_quota_failed'), 'k'),
    ('payment-required', 402, _new_api_error('payment required', ''), 'k'),
]


async def _serve(status: int, body: dict):
    async def handle(request):
        await request.read()
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_post('/chat/completions', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    return runner, f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'


async def _stream_error(base_url: str, api_key: str) -> RequesterError:
    adapter = LiteLLMRequester(
        SimpleNamespace(logger=Mock()),
        {'custom_llm_provider': 'openai', 'base_url': base_url, 'requester_name': 'space-chat-completions'},
    )
    await adapter.initialize()
    model = _runtime_model(adapter, name='deepseek-chat')
    model.provider.token_mgr.get_token = lambda: api_key
    token = current_call.set(CallState(RequestPolicy()))
    try:
        with pytest.raises(RequesterError) as caught:
            [chunk async for chunk in adapter.invoke_llm_stream(None, model, [])]
        return caught.value
    finally:
        current_call.reset(token)
        await adapter.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize('leased_handler', [False, True])
@pytest.mark.parametrize('label,status,body,api_key', CASES, ids=[case[0] for case in CASES])
async def test_gateway_quota_errors_are_reported_as_quota(monkeypatch, label, status, body, api_key, leased_handler):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    if leased_handler:
        monkeypatch.setenv('EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER', 'true')
    runner, base_url = await _serve(status, body)
    try:
        error = await _stream_error(base_url, api_key)
    finally:
        await runner.cleanup()

    assert error.code == 'quota_exceeded'
    assert error.status_code == status
    assert not error.retryable
    assert QUOTA_MESSAGE in str(error)
    # Upstream diagnostics are classified, never shown verbatim.
    assert '剩余额度' not in str(error)


@pytest.mark.asyncio
async def test_leased_handler_keeps_http_status_of_ordinary_errors(monkeypatch):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    monkeypatch.setenv('EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER', 'true')
    runner, base_url = await _serve(401, _new_api_error('invalid token', ''))
    try:
        error = await _stream_error(base_url, 'k')
    finally:
        await runner.cleanup()
    assert error.code == 'authentication'
    assert error.status_code == 401


@pytest.mark.asyncio
async def test_missing_api_key_is_reported_before_the_request(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    error = await _stream_error('http://127.0.0.1:9', '')
    assert error.code == 'authentication'
    assert 'No API key is configured for this model provider' in str(error)


def test_quota_message_follows_workspace_language():
    adapter = LiteLLMRequester(Mock(), {})
    exc = litellm.APIError(status_code=403, message='OpenAIException - 用户额度不足', llm_provider='openai', model='m')
    with language_scope('zh_Hans'):
        with pytest.raises(RequesterError) as caught:
            adapter._handle_litellm_error(exc)
    assert caught.value.code == 'quota_exceeded'
    assert '余额或额度不足' in str(caught.value)
    # The default stays English.
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(exc)
    assert QUOTA_MESSAGE in str(caught.value)


def test_upstream_code_in_response_body_is_used_when_litellm_drops_it():
    adapter = LiteLLMRequester(Mock(), {})
    response = httpx.Response(
        403,
        content=json.dumps(_new_api_error('denied', 'insufficient_user_quota')).encode(),
        request=httpx.Request('POST', 'https://example.com'),
    )
    exc = litellm.PermissionDeniedError(message='denied', llm_provider='openai', model='m', response=response)
    exc.body = None
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(exc)
    assert caught.value.code == 'quota_exceeded'


def test_generic_errors_keep_their_mapping_and_expose_only_safe_codes():
    adapter = LiteLLMRequester(Mock(), {})
    exc = litellm.APIError(status_code=None, message='boom', llm_provider='openai', model='m')
    exc.status_code = None
    exc.body = {'error': {'code': 'upstream_overloaded', 'message': 'secret prompt'}}
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(exc)
    assert caught.value.code == 'upstream_error'
    assert str(caught.value).endswith('API error [upstream_overloaded]')
    assert 'secret prompt' not in str(caught.value)

    plain = litellm.RateLimitError('slow down', llm_provider='openai', model='m')
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(plain)
    assert caught.value.code == 'rate_limit'
    assert caught.value.retryable
