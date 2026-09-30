"""Unit tests for per-event execution traces (pkg/telemetry/trace.py + execution.py)."""

from __future__ import annotations

import asyncio
import time
import types
from importlib import import_module


def get_modules():
    return (
        import_module('langbot.pkg.telemetry.trace'),
        import_module('langbot.pkg.telemetry.execution'),
    )


class FakeManager:
    """Stand-in for TelemetryManager: records payloads instead of posting them."""

    def __init__(self, config=None):
        self.telemetry_config = (
            {'url': 'https://space.example.test', 'disable_telemetry': False} if config is None else config
        )
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True

    def start_send_task(self, payload: dict) -> None:
        self.sent.append(payload)


def make_counters(config=None):
    _, execution = get_modules()
    manager = FakeManager(config)
    return manager, execution.ExecutionCounters(manager)


def make_ap(counters):
    return types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))


def trace_config(**overrides):
    config = {'url': 'https://space.example.test', 'execution_trace': 'all'}
    config.update(overrides)
    return config


CONTEXT = types.SimpleNamespace(instance_uuid='instance-1', workspace_uuid='workspace-1')

STAGE = {
    'family': 'platform_event',
    'operation': 'message.received',
    'mode': 'none',
    'adapter': 'AiocqhttpAdapter',
    'outcome': 'success',
}


class TestTraceIdentity:
    def test_nested_bind_reuses_the_in_flight_trace(self):
        trace, _ = get_modules()
        outer = trace.bind()
        inner = trace.bind()
        try:
            assert outer.created is True
            assert inner.created is False
            assert inner.state is outer.state
            assert trace.current() is outer.state
        finally:
            trace.unbind_root(inner)
            trace.unbind_root(outer)
        assert trace.current() is None

    def test_unbind_root_leaves_a_nested_trace_attached(self):
        trace, _ = get_modules()
        outer = trace.bind()
        inner = trace.bind()
        assert trace.unbind_root(inner) is False
        assert trace.current() is outer.state
        assert trace.unbind_root(outer) is True
        assert trace.current() is None
        # A repeated unbind of the same binding must never raise.
        assert trace.unbind_root(outer) is True

    def test_route_and_run_are_only_pinned_inside_the_block(self):
        trace, _ = get_modules()
        binding = trace.bind()
        token = trace.set_run('run-1')
        try:
            with trace.scope(route_ref='agent:agent-1'):
                inside = trace.current()
                inside.append(
                    family='runner',
                    operation='execute',
                    mode='agent',
                    adapter='',
                    runner='langbot/runner',
                    outcome='success',
                    synthetic=False,
                )
            outside = trace.current()
            outside.append(
                family='platform_api',
                operation='send_message',
                mode='agent',
                adapter='AiocqhttpAdapter',
                runner='',
                outcome='success',
                synthetic=False,
            )
        finally:
            trace.reset_run(token)
            trace.unbind_root(binding)
        assert [(s['route_ref'], s['run_id']) for s in binding.state.stages] == [
            ('agent:agent-1', 'run-1'),
            ('', 'run-1'),
        ]


class TestTraceRecording:
    def test_stage_carries_sequence_identity_and_timestamps(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **STAGE)
            counters.record(CONTEXT, **{**STAGE, 'family': 'runner', 'operation': 'execute', 'mode': 'pipeline'})
        finally:
            trace.unbind_root(binding)
        stages = binding.state.stages
        assert [stage['seq'] for stage in stages] == [0, 1]
        assert stages[0]['first_seen'] == stages[0]['last_seen']
        assert binding.state.identity == {'instance_id': 'instance-1', 'workspace_uuid': 'workspace-1'}
        assert binding.state.outcome() == 'success'

    def test_stage_buffer_is_bounded_and_counts_overflow(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            for _ in range(trace.MAX_STAGES + 5):
                counters.record(CONTEXT, **STAGE)
        finally:
            trace.unbind_root(binding)
        assert len(binding.state.stages) == trace.MAX_STAGES
        assert binding.state.dropped_stages == 5

    def test_oversized_identifier_never_becomes_a_stage(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'operation': 'x' * 200})
            counters.record(CONTEXT, **{**STAGE, 'family': 'not-a-family'})
        finally:
            trace.unbind_root(binding)
        assert binding.state.stages == []

    def test_trace_limit_abandons_further_traces(self):
        trace, execution = get_modules()
        _, counters = make_counters()
        bindings = []
        for _ in range(execution.MAX_TRACES + 1):
            binding = trace.bind()
            bindings.append(binding)
            counters.record(CONTEXT, **STAGE)
            trace.unbind_root(binding)
        assert trace.current() is None
        assert len(counters.traces) == execution.MAX_TRACES
        assert counters.dropped == 1
        assert bindings[-1].state.abandoned is True
        assert bindings[-1].state.stages == []

    def test_counters_keep_aggregating_while_tracing(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            for _ in range(3):
                counters.record(CONTEXT, **STAGE)
        finally:
            trace.unbind_root(binding)
        assert list(counters.pending.values())[0]['count'] == 3


class TestTraceDelivery:
    def test_close_emits_one_payload_per_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **STAGE)
            counters.record(
                CONTEXT, **{**STAGE, 'family': 'runner', 'operation': 'execute', 'mode': 'agent', 'runner': 'runner-1'}
            )
            counters.close_trace(binding.state, 'event_done')
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)

        assert len(manager.sent) == 1
        payload = manager.sent[0]
        assert payload['event_type'] == 'feature_execution'
        assert payload['query_id'] == binding.state.trace_id
        assert len(payload['query_id']) == 36
        assert payload['instance_id'] == 'instance-1'
        assert payload['workspace_uuid'] == 'workspace-1'
        features = payload['features']
        assert features['schema'] == 1
        assert [row['count'] for row in features['observations']] == [1, 1]
        assert [row['seq'] for row in features['observations']] == [0, 1]
        assert [row['trace_id'] for row in features['observations']] == [binding.state.trace_id] * 2
        assert features['trace'] == {
            'closed_by': 'event_done',
            'started_at': binding.state.started_at,
            'ended_at': features['trace']['ended_at'],
            'route_ref': '',
            'run_id': '',
            'outcome': 'success',
            'dropped_stages': 0,
        }
        assert counters.traces == {}

    def test_sampling_decision_is_deterministic_and_keeps_failures(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config(execution_trace='sampled', execution_trace_sample=2))
        binding = trace.bind()
        try:
            binding.state.trace_id = '00000001-0000-4000-8000-000000000000'
            counters.record(CONTEXT, **STAGE)
            assert counters._trace_emitted(binding.state) is False
            binding.state.trace_id = '00000000-0000-4000-8000-000000000000'
            assert counters._trace_emitted(binding.state) is True
            binding.state.trace_id = '00000001-0000-4000-8000-000000000001'
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'timeout'})
            assert counters._trace_emitted(binding.state) is True
        finally:
            trace.unbind_root(binding)

    def test_failures_mode_keeps_failed_and_debug_traces_only(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config(execution_trace='failures', execution_trace_sample=1000000))

        failed = trace.bind()
        counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        counters.close_trace(failed.state, 'event_done')
        trace.unbind_root(failed)

        debug = trace.bind()
        counters.record(CONTEXT, **{**STAGE, 'synthetic': True})
        counters.close_trace(debug.state, 'event_done')
        trace.unbind_root(debug)

        sampled_out = trace.bind()
        counters.record(CONTEXT, **STAGE)
        counters.close_trace(sampled_out.state, 'event_done')
        trace.unbind_root(sampled_out)

        assert [payload['features']['observations'][0]['outcome'] for payload in manager.sent] == ['failed', 'success']
        assert manager.sent[1]['features']['observations'][0]['synthetic'] is True

    def test_off_mode_and_opt_out_emit_nothing(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config(execution_trace='off'))
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        assert manager.sent == []

        disabled_manager, disabled = make_counters(
            {'url': 'https://space.example.test', 'disable_telemetry': True, 'execution_trace': 'all'}
        )
        binding = trace.bind()
        try:
            disabled.record(CONTEXT, **STAGE)
            disabled.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        assert disabled_manager.sent == []
        assert disabled.pending == {}
        assert disabled.traces == {}

    def test_ttl_sweep_closes_stale_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.trace_deadlines[binding.state.trace_id] = 0
            counters._sweep_traces(time.monotonic())
        finally:
            trace.unbind_root(binding)
        assert manager.sent[0]['features']['trace']['closed_by'] == 'ttl'
        assert counters.traces == {}
        assert counters.trace_deadlines == {}

    async def test_shutdown_drops_open_traces(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            await counters.shutdown()
        finally:
            trace.unbind_root(binding)
        # Shutdown may still flush window counters; it must not claim a trace.
        assert [payload for payload in manager.sent if 'trace' in payload['features']] == []
        assert counters.traces == {}
        assert counters.dropped_traces == 1

    async def test_loop_sweeps_and_sends_expired_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.trace_deadlines[binding.state.trace_id] = 0
            await asyncio.sleep(1.2)
            assert [payload['features']['trace']['closed_by'] for payload in manager.sent] == ['ttl']
            assert counters.traces == {}
        finally:
            await counters.shutdown()
            trace.unbind_root(binding)


class TestIngress:
    def test_ingress_closes_only_the_trace_it_started(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done'):
            with execution.ingress(ap, 'pipeline_done'):
                counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        assert len(manager.sent) == 1
        assert manager.sent[0]['features']['trace']['closed_by'] == 'event_done'

    def test_ingress_without_telemetry_is_a_no_op(self):
        _, execution = get_modules()
        with execution.ingress(types.SimpleNamespace(), 'event_done'):
            pass


class AsyncSendManager(FakeManager):
    """Stand-in whose start_send_task is a coroutine, like TelemetryManager."""

    async def start_send_task(self, payload: dict) -> None:
        self.sent.append(payload)


class TestTraceDispatch:
    async def test_close_trace_schedules_the_coroutine_send(self):
        trace, execution = get_modules()
        manager = AsyncSendManager(trace_config())
        counters = execution.ExecutionCounters(manager)
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
            # The payload is only delivered once the scheduled task runs.
            assert manager.sent == []
            await asyncio.sleep(0)
        finally:
            trace.unbind_root(binding)
        assert len(manager.sent) == 1
        assert manager.sent[0]['event_type'] == 'feature_execution'
