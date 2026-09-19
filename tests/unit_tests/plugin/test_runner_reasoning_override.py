"""Secured Host actions accept explicit per-call options after authorization."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

from langbot.pkg.agent.runner.session_registry import AgentRunSessionRegistry
from langbot.pkg.plugin import handler as handler_module
from tests.unit_tests.agent.test_runner_model_reasoning import PRIMARY, FALLBACK, OTHER
from tests.unit_tests.plugin.test_handler_actions import make_handler, make_result
from tests.unit_tests.provider.test_reasoning_control import _requester, _runtime_model


ACTIONS = [
    PluginToRuntimeAction.INVOKE_LLM,
    PluginToRuntimeAction.INVOKE_LLM_STREAM,
    PluginToRuntimeAction.COUNT_TOKENS,
]


class RecordingProvider:
    """Network-free boundary; reasoning translation remains the real requester."""

    def __init__(self, request):
        self.requester = request
        self.provider_entity = SimpleNamespace(requester='openai')
        self.calls = []

    async def record(self, kwargs):
        await asyncio.sleep(0)
        built = self.requester._build_reasoning_args(kwargs['model'])
        self.calls.append((kwargs, built))

    async def invoke_llm(self, **kwargs):
        await self.record(kwargs)
        return provider_message.Message(role='assistant', content='ok')

    async def invoke_llm_stream(self, **kwargs):
        await self.record(kwargs)
        yield provider_message.MessageChunk(role='assistant', content='ok')

    async def count_tokens(self, **kwargs):
        await self.record(kwargs)
        return 37


@pytest.fixture
async def host(monkeypatch):
    registry = AgentRunSessionRegistry()
    monkeypatch.setattr(handler_module, 'get_session_registry', lambda: registry)
    request = _requester('openai')
    monkeypatch.setattr(request, '_supports_reasoning', lambda _: True)
    monkeypatch.setattr(request, '_safe_model_info', lambda _: {})
    provider = RecordingProvider(request)
    monkeypatch.setattr(request, 'count_tokens', provider.count_tokens)
    models = {}
    for model_id in (PRIMARY, FALLBACK):
        model = _runtime_model(request, 'medium', name='gpt-5')
        model.model_entity.uuid = model_id
        model.model_entity.workspace_uuid = 'workspace-a'
        model.provider = provider
        models[model_id] = model
    ap = SimpleNamespace(
        logger=Mock(),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(side_effect=lambda context, model_id: models[model_id])),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(return_value=make_result(SimpleNamespace(uuid=PRIMARY)))
        ),
    )
    runtime = make_handler(ap)

    async def register(run_id='run', workspace='workspace-a', plugin='test-author/test-plugin', operations=None):
        await registry.register(
            run_id=run_id,
            runner_id='plugin:test-author/test-plugin/arbitrary',
            query_id=None,
            plugin_identity=plugin,
            workspace_id=workspace,
            resources={
                'models': [
                    {'model_id': model_id, **({'operations': operations} if operations else {})}
                    for model_id in (PRIMARY, FALLBACK)
                ]
            },
        )
        return await registry.get(run_id)

    return SimpleNamespace(
        registry=registry, models=models, provider=provider, runtime=runtime, register=register, ap=ap
    )


async def call(host, action, model_id=PRIMARY, run_id='run', **extra):
    payload = {
        'llm_model_uuid': model_id,
        'messages': [{'role': 'user', 'content': 'hello'}],
        'extra_args': {'temperature': 0.7},
        **extra,
    }
    if run_id is not None:
        payload['run_id'] = run_id
    if action == PluginToRuntimeAction.INVOKE_LLM_STREAM:
        return [response async for response in host.runtime.actions[action.value](payload)]
    return [await host.runtime.actions[action.value](payload)]


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_primary_fallback_and_repeated_tool_round_use_explicit_options(host, action):
    await host.register()
    for model_id, level in [(PRIMARY, 'high'), (FALLBACK, 'low'), (FALLBACK, 'low')]:
        responses = await call(host, action, model_id, reasoning_level=level)
        assert all(response.code == 0 for response in responses)
        kwargs, built = host.provider.calls[-1]
        assert built == {'reasoning_effort': level}
        assert kwargs['model'] is not host.models[model_id]
        assert kwargs['model'].reasoning_config_override == {'level': level}
        assert kwargs['extra_args'] == {'temperature': 0.7}
        assert 'model_reasoning_overrides' not in kwargs
    assert all(model.reasoning_config_override is None for model in host.models.values())


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('level', [None, 'provider_default'])
async def test_absent_and_explicit_provider_default_are_distinct(host, action, level):
    await host.register()
    assert all(response.code == 0 for response in await call(host, action, reasoning_level=level))
    kwargs, built = host.provider.calls[-1]
    assert built == ({} if level else {'reasoning_effort': 'medium'})
    assert (kwargs['model'] is host.models[PRIMARY]) is (level is None)
    assert host.models[PRIMARY].model_entity.reasoning_config == {'level': 'medium'}


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_regular_plugin_without_run_keeps_model_defaults_and_ignores_forged_map(host, action):
    responses = await call(
        host,
        action,
        run_id=None,
        model_reasoning_overrides={PRIMARY: {'level': 'max'}},
        reasoning_config_override={'level': 'disabled'},
    )
    assert all(response.code == 0 for response in responses)
    kwargs, built = host.provider.calls[-1]
    assert kwargs['model'] is host.models[PRIMARY]
    assert built == {'reasoning_effort': 'medium'}


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_obsolete_hidden_policy_fields_do_not_override_explicit_api(host, action):
    await host.register()
    responses = await call(
        host,
        action,
        model_reasoning_overrides={PRIMARY: {'level': 'disabled'}},
        reasoning_config_override={'level': 'disabled'},
    )
    assert all(response.code == 0 for response in responses)
    assert host.provider.calls[-1][1] == {'reasoning_effort': 'medium'}


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('denial', ['workspace', 'plugin', 'unselected', 'operation', 'expired'])
async def test_authorization_denial_happens_before_model_access(host, action, denial):
    await host.register(
        workspace='workspace-b' if denial == 'workspace' else 'workspace-a',
        plugin='other/plugin' if denial == 'plugin' else 'test-author/test-plugin',
        operations=['rerank'] if denial == 'operation' else None,
    )
    responses = await call(
        host, action, OTHER if denial == 'unselected' else PRIMARY, run_id='expired' if denial == 'expired' else 'run'
    )
    assert all(response.code != 0 for response in responses)
    assert not host.provider.calls
    host.ap.model_mgr.get_model_by_uuid.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_concurrent_runs_share_model_without_cross_run_or_round_leakage(host, action):
    await host.register('high-run')
    await host.register('low-run')
    results = await asyncio.gather(
        *(
            call(host, action, run_id=run_id, reasoning_level=run_id.split('-')[0])
            for run_id in ['high-run', 'low-run'] * 3
        )
    )
    assert all(response.code == 0 for result in results for response in result)
    assert sorted(built['reasoning_effort'] for _, built in host.provider.calls) == ['high'] * 3 + ['low'] * 3
    assert len({id(kwargs['model']) for kwargs, _ in host.provider.calls}) == 6
    assert host.models[PRIMARY].reasoning_config_override is None


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_model_runtime_workspace_mismatch_denies(host, action):
    await host.register()
    host.models[PRIMARY].model_entity.workspace_uuid = 'workspace-b'
    responses = await call(host, action)
    assert all(response.code != 0 for response in responses)
    assert not host.provider.calls


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_host_reuses_core_ability_validation_before_provider_call(host, action):
    await host.register()
    host.models[PRIMARY].model_entity.abilities = []
    with pytest.raises(ValueError, match='reasoning ability'):
        await call(host, action, reasoning_level='high')
    assert not host.provider.calls


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_regular_plugins_can_explicitly_set_level_without_runner_session(host, action):
    responses = await call(host, action, run_id=None, reasoning_level='low')
    assert all(response.code == 0 for response in responses)
    assert host.provider.calls[-1][1] == {'reasoning_effort': 'low'}
