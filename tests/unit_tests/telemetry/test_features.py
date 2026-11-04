import contextvars
import json
from types import SimpleNamespace

import pytest

from langbot.pkg.telemetry import features, trace
from tests.unit_tests.telemetry.test_trace import CONTEXT, make_ap, make_counters


@pytest.fixture
def telemetry():
    _, counters = make_counters()
    return make_ap(counters), counters


def model(name='model-a'):
    return SimpleNamespace(model_entity=SimpleNamespace(name=name))


def bind_trace():
    binding = trace.bind()
    binding.state.identity = {'instance_id': CONTEXT.instance_uuid, 'workspace_uuid': CONTEXT.workspace_uuid}
    return binding


def test_features_accumulate_without_nodes_or_uploads(telemetry):
    ap, counters = telemetry
    binding = bind_trace()
    try:
        for group, key in features.COUNTERS:
            features.increment(ap, group, key)
            features.increment(ap, group, key)
        assert binding.state.features == {
            'tool_calls': {'native': 2, 'plugin': 2, 'mcp': 2, 'skill': 2},
            'sandbox': {'execs': 2, 'errors': 2},
            'kb': {'retrievals': 2},
            'activated_skills': 2,
            'llm_calls': 2,
        }
        payload = counters._build_chain_record(binding.state, 'event_done')
        assert payload['features'] == binding.state.features
        features.increment(ap, 'tool_calls', 'native')
        assert payload['features']['tool_calls']['native'] == 2
        assert counters.records == []
        assert counters.task is None
    finally:
        trace.unbind_root(binding)


def test_empty_and_zero_counters_are_omitted(telemetry):
    ap, counters = telemetry
    binding = bind_trace()
    try:
        assert 'features' not in counters._build_chain_record(binding.state, 'event_done')
        features.increment(ap, 'tool_calls', 'mcp')
        features.increment(ap, 'user-content', 'secret')
        assert counters._build_chain_record(binding.state, 'event_done')['features'] == {'tool_calls': {'mcp': 1}}
    finally:
        trace.unbind_root(binding)


@pytest.mark.parametrize('name', ['x' * 200, '模型' * 100])
def test_model_first_write_wins_and_is_utf8_bounded(telemetry, name):
    ap, counters = telemetry
    binding = bind_trace()
    try:
        features.note_llm(ap, model(name))
        first = binding.state.model_name
        features.note_llm(ap, model('other-model'))
        assert first and name.startswith(first)
        assert len(first.encode('utf-8')) <= 128
        assert binding.state.model_name == first
        assert binding.state.features == {'llm_calls': 2}
        binding.state.model_name = name
        assert len(counters._build_chain_record(binding.state, 'event_done')['model_name'].encode('utf-8')) <= 128
    finally:
        trace.unbind_root(binding)


@pytest.mark.parametrize('config', [{}, {'disable_telemetry': True, 'url': 'https://example.test'}, {'url': ''}])
def test_disabled_telemetry_does_not_count_or_resolve(config, monkeypatch):
    _, counters = make_counters(config)
    ap = make_ap(counters)
    monkeypatch.setattr(counters, '_resolve', lambda *_: pytest.fail('disabled telemetry resolved a trace'))
    binding = bind_trace()
    try:
        features.note_llm(ap, model())
        features.increment(ap, 'sandbox', 'execs')
        assert binding.state.features == {}
        assert binding.state.model_name == ''
        assert binding.state.configured is False
    finally:
        trace.unbind_root(binding)


@pytest.mark.parametrize('flag', ['closed', 'unrouted', 'off'])
def test_ineligible_traces_do_not_count(telemetry, flag):
    ap, counters = telemetry
    binding = bind_trace()
    try:
        if flag == 'closed':
            binding.state.closed = True
        elif flag == 'unrouted':
            binding.state.reportable = False
        else:
            counters.manager.telemetry_config['execution_trace'] = 'off'
        features.note_llm(ap, model())
        features.increment(ap, 'kb', 'retrievals')
        assert binding.state.features == {}
        assert binding.state.model_name == ''
    finally:
        trace.unbind_root(binding)


def test_cross_task_query_and_explicit_run_ids_share_counters(telemetry):
    ap, counters = telemetry
    state = trace.TraceState('event')
    counters.register_trace(state, 'run')
    query = SimpleNamespace(_agent_run_session={'run_id': 'run'})
    foreign = contextvars.Context()
    foreign.run(features.note_llm, ap, model(), query)
    foreign.run(features.increment, ap, 'kb', 'retrievals', execution_id='run')
    foreign.run(features.increment, ap, 'sandbox', 'execs', query=query)
    assert state.model_name == 'model-a'
    assert state.features == {'llm_calls': 1, 'kb': {'retrievals': 1}, 'sandbox': {'execs': 1}}
    foreign.run(features.increment, ap, 'kb', 'retrievals', execution_id='unknown')
    assert state.features['kb']['retrievals'] == 1


def test_sampled_out_traces_still_count_for_failure_closure(telemetry):
    ap, counters = telemetry
    counters.manager.telemetry_config['execution_trace'] = 'failures'
    binding = bind_trace()
    try:
        features.note_llm(ap, model())
        assert binding.state.emit_nodes is False
        assert binding.state.features == {'llm_calls': 1}
    finally:
        trace.unbind_root(binding)


def test_saturating_counters_bound_payload_growth(telemetry):
    ap, counters = telemetry
    binding = bind_trace()
    try:
        for group, key in features.COUNTERS:
            features.increment(ap, group, key)
            target = binding.state.features if key is None else binding.state.features[group]
            target[group if key is None else key] = features.MAX_COUNTER
            features.increment(ap, group, key)
            assert target[group if key is None else key] == features.MAX_COUNTER
        payload = counters._build_chain_record(binding.state, 'event_done')
        baseline = {key: value for key, value in payload.items() if key != 'features'}
        growth = len(json.dumps(payload, separators=(',', ':'))) - len(json.dumps(baseline, separators=(',', ':')))
        assert growth <= 200
    finally:
        trace.unbind_root(binding)


def test_representative_chain_payload_growth(telemetry):
    import httpx

    def encode(record):
        return httpx.Request('POST', 'https://example.test', json=record).content

    ap, counters = telemetry
    growth = []
    workloads = [
        [],
        [('llm_calls', None)],
        [('llm_calls', None), ('tool_calls', 'mcp')],
        [('llm_calls', None), ('kb', 'retrievals')],
        sorted(features.COUNTERS),
    ]
    for workload in workloads:
        binding = bind_trace()
        try:
            before = counters._build_chain_record(binding.state, 'event_done')
            for group, key in workload:
                if group == 'llm_calls':
                    features.note_llm(ap, model())
                else:
                    features.increment(ap, group, key)
            after = counters._build_chain_record(binding.state, 'event_done')
            after['timestamp'] = before['timestamp']
            after['duration_ms'] = before['duration_ms']
            growth.append(len(encode(after)) - len(encode(before)))
            if not workload:
                assert encode(after) == encode(before)
        finally:
            trace.unbind_root(binding)
    assert growth == [0, 34, 57, 56, 165]
    assert sum(growth) / len(growth) <= 200


def test_telemetry_failures_do_not_escape(telemetry, monkeypatch):
    ap, counters = telemetry

    def broken(*args):
        raise RuntimeError('telemetry failure')

    monkeypatch.setattr(counters, '_enabled', broken)
    features.increment(ap, 'llm_calls')
    features.note_llm(ap, model())
    features.increment(SimpleNamespace(), 'llm_calls')


@pytest.mark.asyncio
async def test_chain_close_emits_features_once(telemetry):
    from langbot.pkg.telemetry.execution import ingress

    ap, counters = telemetry
    with ingress(ap, context=CONTEXT) as binding:
        features.note_llm(ap, model())
    counters.close_trace(binding.state)
    assert len(counters.records) == 1
    assert counters.records[0]['features'] == {'llm_calls': 1}
    await counters.shutdown()
