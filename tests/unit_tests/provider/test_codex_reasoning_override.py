"""Request-local reasoning must reach the native Codex Responses builder."""

from copy import copy, deepcopy
from types import SimpleNamespace

import pytest
import langbot_plugin.api.entities.builtin.provider.message as pm

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence import model as persistence_model
from langbot.pkg.provider.modelmgr.requester import RuntimeLLMModel
from tests.unit_tests.provider.test_codex import TOKENS, requester, stream


@pytest.fixture
def codex(monkeypatch):
    def unexpected_request(request):
        pytest.fail('Builder tests must not send HTTP requests')

    return requester(monkeypatch, unexpected_request)


def runtime_model(codex, name='primary', level='high'):
    context = ExecutionContext(instance_uuid='instance', workspace_uuid='w', placement_generation=1)
    provider = SimpleNamespace(
        execution_context=context,
        provider_entity=persistence_model.ModelProvider(
            workspace_uuid='w', uuid='p', name='codex', requester='codex', api_keys=[]
        ),
        requester=codex,
    )
    entity = persistence_model.LLMModel(
        workspace_uuid='w',
        uuid=name,
        name=name,
        provider_uuid='p',
        abilities=['reasoning', 'func_call'],
        reasoning_config={'level': level},
        extra_args={},
    )
    return RuntimeLLMModel(context, entity, provider)


def entity_values(model):
    return {
        column.name: deepcopy(getattr(model.model_entity, column.name))
        for column in model.model_entity.__table__.columns
    }


def build(codex, model):
    return codex._body(None, model, [pm.Message(role='user', content='Hi')], None, None, TOKENS)


@pytest.mark.parametrize('level', ['provider_default', 'low', 'medium', 'high', 'xhigh'])
def test_canonical_codex_override_levels(codex, level):
    model = runtime_model(codex, level='medium')
    before = deepcopy(entity_values(model))
    model.reasoning_config_override = {'level': level}
    assert codex.get_reasoning_capabilities(model)['levels'] == ['provider_default', 'low', 'medium', 'high', 'xhigh']
    body = build(codex, model)
    if level == 'provider_default':
        assert 'reasoning' not in body
    else:
        assert body['reasoning'] == {'effort': level, 'summary': 'auto'}
    assert model.reasoning_config_override == {'level': level}
    assert entity_values(model) == before
    assert 'reasoning_config_override' not in body


def test_primary_fallback_and_shared_entity_clones_are_isolated(codex):
    primary = runtime_model(codex)
    fallback = runtime_model(codex, name='fallback', level='medium')
    primary_run, fallback_run, another_run = copy(primary), copy(fallback), copy(primary)
    primary_run.reasoning_config_override = {'level': 'low'}
    fallback_run.reasoning_config_override = {'level': 'xhigh'}
    another_run.reasoning_config_override = {'level': 'medium'}
    originals = [primary, fallback]
    before = [deepcopy(entity_values(model)) for model in originals]
    for scoped, expected in [(primary_run, 'low'), (fallback_run, 'xhigh'), (another_run, 'medium')]:
        assert build(codex, scoped)['reasoning']['effort'] == expected
    assert primary_run.model_entity is another_run.model_entity is primary.model_entity
    assert primary_run.provider is another_run.provider is primary.provider
    assert build(codex, primary)['reasoning']['effort'] == 'high'
    assert build(codex, fallback)['reasoning']['effort'] == 'medium'
    assert [entity_values(model) for model in originals] == before
    assert all(model.reasoning_config_override is None for model in originals)


def test_explicit_provider_default_overrides_persisted_high(codex):
    model = runtime_model(codex)
    model.reasoning_config_override = {'level': 'provider_default'}
    assert 'reasoning' not in build(codex, model)
    assert model.model_entity.reasoning_config == {'level': 'high'}


@pytest.mark.parametrize('missing_attribute', [False, True])
@pytest.mark.parametrize('level', ['provider_default', 'high'])
def test_absent_override_preserves_persisted_config(codex, missing_attribute, level):
    model = runtime_model(codex, level=level)
    if missing_attribute:
        del model.reasoning_config_override
    body = build(codex, model)
    assert body.get('reasoning') == (None if level == 'provider_default' else {'effort': level, 'summary': 'auto'})


@pytest.mark.parametrize(
    'config',
    [
        {'level': 'turbo'},
        {'level': 'disabled'},
        {'level': 'enabled'},
        {'level': 'minimal'},
        {'level': 'max'},
        {'unknown': True},
        'high',
    ],
)
def test_override_uses_same_validation_errors_as_persisted_config(codex, config):
    persisted = runtime_model(codex)
    persisted.model_entity.reasoning_config = deepcopy(config)
    with pytest.raises(ValueError) as expected:
        build(codex, persisted)
    scoped = runtime_model(codex)
    scoped.reasoning_config_override = deepcopy(config)
    before = deepcopy(entity_values(scoped))
    with pytest.raises(ValueError) as actual:
        build(codex, scoped)
    assert str(actual.value) == str(expected.value)
    assert TOKENS['access_token'] not in str(actual.value)
    assert TOKENS['account_id'] not in str(actual.value)
    assert entity_values(scoped) == before


def test_advanced_args_remain_unchanged(codex):
    model = runtime_model(codex, level='provider_default')
    model.model_entity.extra_args = {'reasoning': {'effort': 'low'}, 'parallel_tool_calls': False}
    before = deepcopy(entity_values(model))
    baseline = build(codex, model)
    model.reasoning_config_override = {'level': 'provider_default'}
    assert build(codex, model) == baseline
    assert entity_values(model) == before


@pytest.mark.asyncio
@pytest.mark.parametrize('streaming', [False, True])
async def test_override_preserves_stream_tools_usage_and_replay(monkeypatch, streaming):
    import json

    call = {'type': 'function_call', 'call_id': 'call_1', 'name': 'lookup', 'arguments': '{}'}
    output = [{'type': 'reasoning', 'encrypted_content': 'opaque-secret'}, call]
    requests = []

    def handler(request):
        requests.append(request)
        return stream(
            [
                {'type': 'response.output_text.delta', 'delta': 'Hello'},
                {'type': 'response.output_item.done', 'item': call, 'output_index': 1},
                {
                    'type': 'response.completed',
                    'response': {
                        'id': 'resp_1',
                        'status': 'completed',
                        'output': output,
                        'usage': {'input_tokens': 4, 'output_tokens': 3},
                    },
                },
            ]
        )

    codex = requester(monkeypatch, handler)
    model = runtime_model(codex)
    scoped = copy(model)
    scoped.reasoning_config_override = {'level': 'low'}
    before = deepcopy(entity_values(model))
    provider_before = dict(vars(model.provider))
    query = SimpleNamespace(query_id='q', variables={})
    messages = [pm.Message(role='user', content='Hi')]
    funcs = [SimpleNamespace(name='lookup', description='Look up', parameters={'type': 'object'})]
    baseline = codex._body(query, model, messages, funcs, None, TOKENS)
    if streaming:
        chunks = [chunk async for chunk in codex.invoke_llm_stream(query, scoped, messages, funcs)]
        assert ''.join(chunk.content or '' for chunk in chunks) == 'Hello'
        assert sum(len(chunk.tool_calls or []) for chunk in chunks) == 1
        assert next(chunk.tool_calls[0] for chunk in chunks if chunk.tool_calls).function.arguments == '{}'
        assert chunks[-1].is_final
        result = pm.Message(
            role='assistant', content='Hello', provider_specific_fields=chunks[-1].provider_specific_fields
        )
    else:
        result, usage = await codex.invoke_llm(query, scoped, messages, funcs)
        assert result.content == 'Hello'
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].function.arguments == '{}'
        assert usage['total_tokens'] == 7
    body = json.loads(requests[0].content)
    assert body.pop('reasoning') == {'effort': 'low', 'summary': 'auto'}
    baseline.pop('reasoning')
    assert body == baseline
    assert query.variables['_stream_usage']['total_tokens'] == 7
    assert 'opaque-secret' not in result.model_dump_json()
    assert codex._body(query, scoped, [result], None, None, TOKENS)['input'] == output
    assert requests[0].headers['authorization'] == 'Bearer ' + TOKENS['access_token']
    assert entity_values(model) == before
    assert vars(model.provider) == provider_before
    assert model.reasoning_config_override is None
    codex.auth.access.assert_awaited_once_with('w', 'p')
