"""Unit tests for per-execution execution traces (pkg/telemetry/trace.py + execution.py)."""

from __future__ import annotations

import asyncio
import contextvars
import json
import time
import types
from datetime import datetime, timedelta, timezone
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


def records_sent(manager):
    """Flatten the buffered-record batches a FakeManager received."""
    return [record for payload in manager.sent for record in payload.get('records', [])]


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

    def test_trace_id_is_the_execution_id(self):
        trace, _ = get_modules()
        binding = trace.bind('exec-1234')
        try:
            assert binding.created is True
            assert binding.state.trace_id == 'exec-1234'
            assert binding.state.execution_id == 'exec-1234'
        finally:
            trace.unbind_root(binding)

    def test_nested_boundary_keeps_the_enclosing_execution_id(self):
        trace, _ = get_modules()
        outer = trace.bind('event-1')
        inner = trace.bind('query-9')
        try:
            assert inner.created is False
            assert inner.state.trace_id == 'event-1'
        finally:
            trace.unbind_root(inner)
            trace.unbind_root(outer)

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

    def test_observation_without_an_owning_execution_is_dropped(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        # Clustering is gone: an observation that belongs to no execution is
        # discarded instead of being aggregated into a synthetic bucket.
        counters.record(CONTEXT, **STAGE)
        assert counters.records == []
        assert counters.traces == {}


class TestTraceNodeScope:
    """Workflow step nodes: a step's own record and the observations it calls."""

    @staticmethod
    def _step(**overrides):
        return {
            'family': 'runner',
            'operation': 'execute',
            'mode': 'agent',
            'runner': 'runner-1',
            'outcome': 'success',
            **overrides,
        }

    def test_nested_observation_carries_the_step_node_as_parent(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            with trace.stage_scope() as step:
                counters.record(CONTEXT, node=step, **self._step())
                counters.record(CONTEXT, **{**STAGE, 'family': 'platform_api', 'operation': 'send_message'})
        finally:
            trace.unbind_root(binding)

        step_row, api_row = binding.state.stages
        assert step_row['node'] == step
        assert 'parent' not in step_row  # a root step carries no parent
        assert api_row['parent'] == step
        assert 'node' not in api_row  # observations are not step nodes

    def test_nested_step_records_its_enclosing_step_as_parent(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            with trace.stage_scope() as outer:
                counters.record(CONTEXT, node=outer, **self._step(mode='pipeline'))
                with trace.stage_scope() as inner:
                    counters.record(CONTEXT, node=inner, **self._step())
                    counters.record(CONTEXT, **{**STAGE, 'family': 'platform_api', 'operation': 'send_message'})
        finally:
            trace.unbind_root(binding)

        outer_row, inner_row, api_row = binding.state.stages
        assert (outer_row['node'], outer_row.get('parent')) == (outer, None)
        # The step's own record sits under its enclosing step, never under itself.
        assert (inner_row['node'], inner_row.get('parent')) == (inner, outer)
        assert api_row.get('parent') == inner and 'node' not in api_row

    def test_sequential_steps_get_distinct_ids_and_roots_have_no_parent(self):
        trace, _ = get_modules()
        _, counters = make_counters()
        binding = trace.bind()
        try:
            with trace.stage_scope() as first:
                counters.record(CONTEXT, node=first, **self._step())
            with trace.stage_scope() as second:
                counters.record(CONTEXT, node=second, **self._step())
        finally:
            trace.unbind_root(binding)

        assert (first, second) == ('n1', 'n2')
        assert [row['node'] for row in binding.state.stages] == [first, second]
        assert all('parent' not in row for row in binding.state.stages)

    def test_cross_task_observation_attaches_to_the_open_step(self):
        trace, execution = get_modules()
        _, counters = make_counters()
        binding = execution.bind_trace(make_ap(counters), 'exec-cross')
        try:
            with trace.stage_scope() as lane:
                counters.record(
                    CONTEXT, family='pipeline', operation='run', mode='pipeline', outcome='success', node=lane
                )
                # A plugin/RPC observation arrives on a task that never had the
                # trace context; it is resolved through the execution registry and
                # must still hang off the step the owning task has open.
                foreign = contextvars.Context()
                foreign.run(execution.set_execution_id, 'exec-cross')
                foreign.run(
                    counters.record,
                    CONTEXT,
                    family='platform_api',
                    operation='send_message',
                    mode='pipeline',
                    outcome='success',
                )
        finally:
            trace.unbind_root(binding)

        rows = binding.state.stages
        assert rows[0]['node'] == lane and 'parent' not in rows[0]
        assert rows[1].get('parent') == lane and 'node' not in rows[1]

    def test_cross_task_observation_without_an_open_step_has_no_parent(self):
        trace, execution = get_modules()
        _, counters = make_counters()
        binding = execution.bind_trace(make_ap(counters), 'exec-bare')
        try:
            foreign = contextvars.Context()
            foreign.run(execution.set_execution_id, 'exec-bare')
            foreign.run(
                counters.record,
                CONTEXT,
                family='platform_api',
                operation='send_message',
                mode='pipeline',
                outcome='success',
            )
        finally:
            trace.unbind_root(binding)

        row = binding.state.stages[0]
        assert 'node' not in row and 'parent' not in row

    def test_scope_outside_any_trace_is_inert(self):
        trace, _ = get_modules()
        with trace.stage_scope() as node:
            assert node == ''
            assert trace.current_parent() == ''

    def test_records_outside_any_scope_serialize_without_node_keys(self):
        trace, execution = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind('exec-legacy')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)

        stage = binding.state.stages[0]
        assert set(stage) == {
            'family',
            'operation',
            'mode',
            'adapter',
            'runner',
            'outcome',
            'synthetic',
            'seq',
            'route_ref',
            'run_id',
            'first_seen',
            'last_seen',
            'error',
        }
        observation = counters.records[0]['features']['observations'][0]
        assert 'node' not in json.dumps(observation, sort_keys=True)
        assert 'parent' not in json.dumps(observation, sort_keys=True)


class TestTraceDelivery:
    def test_close_buffers_one_record_per_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind('exec-1')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.record(
                CONTEXT, **{**STAGE, 'family': 'runner', 'operation': 'execute', 'mode': 'agent', 'runner': 'runner-1'}
            )
            counters.close_trace(binding.state, 'event_done')
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)

        # Closing buffers; nothing is sent before the flush cadence.
        assert manager.sent == []
        assert len(counters.records) == 1
        assert counters.traces == {}

        record = counters.records[0]
        assert record['event_type'] == 'feature_execution'
        assert record['query_id'] == 'exec-1'
        assert record['instance_id'] == 'instance-1'
        assert record['workspace_uuid'] == 'workspace-1'
        assert record['trusted'] is True
        features = record['features']
        assert features['schema'] == 1
        assert 'count' not in json.dumps(record)
        assert [row['seq'] for row in features['observations']] == [0, 1]
        assert [row['trace_id'] for row in features['observations']] == ['exec-1'] * 2
        assert features['trace'] == {
            'closed_by': 'event_done',
            'started_at': binding.state.started_at,
            'ended_at': features['trace']['ended_at'],
            'route_ref': '',
            'run_id': '',
            'outcome': 'success',
            'dropped_stages': 0,
        }

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
        _, counters = make_counters(trace_config(execution_trace='failures', execution_trace_sample=1000000))

        failed = trace.bind('exec-failed')
        counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        counters.close_trace(failed.state, 'event_done')
        trace.unbind_root(failed)

        debug = trace.bind('exec-debug')
        counters.record(CONTEXT, **{**STAGE, 'synthetic': True})
        counters.close_trace(debug.state, 'event_done')
        trace.unbind_root(debug)

        sampled_out = trace.bind('exec-sampled')
        counters.record(CONTEXT, **STAGE)
        counters.close_trace(sampled_out.state, 'event_done')
        trace.unbind_root(sampled_out)

        assert [record['query_id'] for record in counters.records] == ['exec-failed', 'exec-debug']
        assert counters.records[0]['features']['observations'][0]['outcome'] == 'failed'
        assert counters.records[1]['features']['observations'][0]['synthetic'] is True

    def test_off_mode_and_opt_out_buffer_nothing(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config(execution_trace='off'))
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        assert manager.sent == []
        assert counters.records == []

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
        assert disabled.records == []
        assert disabled.traces == {}

    def test_ttl_sweep_closes_stale_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind('exec-ttl')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.trace_deadlines[binding.state.trace_id] = 0
            counters._sweep_traces(time.monotonic())
        finally:
            trace.unbind_root(binding)
        assert counters.records[0]['features']['trace']['closed_by'] == 'ttl'
        assert counters.traces == {}
        assert counters.trace_deadlines == {}
        assert manager.sent == []

    async def test_shutdown_drops_open_traces(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind('exec-open')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            await counters.shutdown()
        finally:
            trace.unbind_root(binding)
        # Shutdown must not claim a trace that never completed.
        assert records_sent(manager) == []
        assert counters.records == []
        assert counters.traces == {}
        assert counters.registry == {}
        assert counters.dropped_traces == 1

    async def test_loop_sweeps_and_flushes_expired_trace(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config(telemetry_flush_seconds=1))
        binding = trace.bind('exec-ttl-loop')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            counters.trace_deadlines[binding.state.trace_id] = 0
            await asyncio.sleep(1.3)
            assert [record['features']['trace']['closed_by'] for record in records_sent(manager)] == ['ttl']
            assert counters.traces == {}
        finally:
            await counters.shutdown()
            trace.unbind_root(binding)

    async def test_flush_sends_one_batch_of_complete_records(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config())
        ap = make_ap(counters)
        for index in range(2):
            with execution.ingress(ap, 'event_done', CONTEXT, execution_id=f'exec-{index}'):
                counters.record(CONTEXT, **STAGE)
        assert len(counters.records) == 2

        await counters.flush()
        assert len(manager.sent) == 1
        payload = manager.sent[0]
        assert set(payload) == {'records'}
        assert [record['query_id'] for record in payload['records']] == ['exec-0', 'exec-1']
        assert 'count' not in json.dumps(payload)

    async def test_flush_interval_is_honoured(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config(telemetry_flush_seconds=1))
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='exec-timed'):
            counters.record(CONTEXT, **STAGE)
        assert counters.flush_seconds() == 1
        assert manager.sent == []
        await asyncio.sleep(1.3)
        assert [record['query_id'] for record in records_sent(manager)] == ['exec-timed']
        await counters.shutdown()

    def test_flush_interval_config_is_bounded(self):
        _, counters = make_counters(trace_config())
        assert counters.flush_seconds() == 180
        counters.manager.telemetry_config = trace_config(telemetry_flush_seconds='nope')
        assert counters.flush_seconds() == 180
        counters.manager.telemetry_config = trace_config(telemetry_flush_seconds=0)
        assert counters.flush_seconds() == 180
        counters.manager.telemetry_config = trace_config(telemetry_flush_seconds=300)
        assert counters.flush_seconds() == 300

    def test_buffered_record_cap_drops_oldest(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        original = execution.MAX_BUFFERED_RECORDS
        execution.MAX_BUFFERED_RECORDS = 3
        try:
            for index in range(5):
                binding = trace.bind(f'exec-{index}')
                counters.record(CONTEXT, **STAGE)
                counters.close_trace(binding.state, 'event_done')
                trace.unbind_root(binding)
        finally:
            execution.MAX_BUFFERED_RECORDS = original
        assert [record['query_id'] for record in counters.records] == ['exec-2', 'exec-3', 'exec-4']
        assert counters.dropped == 2


class TestIngress:
    def test_ingress_closes_only_the_trace_it_started(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', execution_id='exec-outer'):
            with execution.ingress(ap, 'pipeline_done', execution_id='exec-inner'):
                counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        assert len(counters.records) == 1
        assert counters.records[0]['query_id'] == 'exec-outer'
        assert counters.records[0]['features']['trace']['closed_by'] == 'event_done'
        assert manager.sent == []

    def test_ingress_without_telemetry_is_a_no_op(self):
        _, execution = get_modules()
        with execution.ingress(types.SimpleNamespace(), 'event_done', execution_id='exec-x'):
            pass

    def test_ingress_registers_every_execution_alias(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', execution_id='event-1') as outer:
            with execution.ingress(ap, 'pipeline_done', execution_id='query-1') as inner:
                assert inner.state is outer.state
        assert counters.registry == {}
        # Closing the owning trace unregisters every alias it held.
        assert counters.registry_deadlines == {}


class TestCrossTaskAttribution:
    def test_registry_joins_stages_from_a_task_without_a_trace(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        binding = execution.bind_trace(ap, 'run-1')
        trace.unbind_root(binding)
        # The plugin/RPC task has no inherited trace context.
        assert trace.current() is None

        counters.record(CONTEXT, **{**STAGE, 'family': 'platform_api', 'operation': 'send_message'})
        counters.record(
            CONTEXT, **{**STAGE, 'family': 'platform_api', 'operation': 'send_message'}, execution_id='run-1'
        )
        assert len(binding.state.stages) == 1
        assert binding.state.stages[0]['operation'] == 'send_message'

        counters.close_trace(binding.state, 'event_done')
        assert counters.records[0]['query_id'] == 'run-1'

    def test_registry_aliases_a_nested_execution(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='event-1') as binding:
            with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='query-1'):
                pass
            assert set(counters.registry) == {'event-1', 'query-1'}
            counters.record(CONTEXT, **STAGE, execution_id='query-1')
        assert counters.records[0]['query_id'] == 'event-1'
        assert len(binding.state.stages) == 1

    def test_contextvar_execution_id_is_used_when_no_kwarg(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        binding = execution.bind_trace(ap, 'run-2')
        trace.unbind_root(binding)
        token = execution.set_execution_id('run-2')
        try:
            counters.record(CONTEXT, **STAGE)
        finally:
            execution.reset_execution_id(token)
        assert len(binding.state.stages) == 1

    def test_registry_alias_is_swept_when_never_closed(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        binding = execution.bind_trace(ap, 'run-3')
        trace.unbind_root(binding)
        counters.registry_deadlines['run-3'] = 0
        counters._sweep_registry(time.monotonic())
        assert counters.registry == {}
        assert counters.registry_deadlines == {}


class TestTraceDispatch:
    async def test_flush_awaits_the_manager_send(self):
        _, execution = get_modules()
        manager = AsyncSendManager(trace_config())
        counters = execution.ExecutionCounters(manager)
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='exec-async'):
            counters.record(CONTEXT, **STAGE)
        await counters.flush()
        assert [record['query_id'] for record in records_sent(manager)] == ['exec-async']
        assert manager.sent[0]['records'][0]['event_type'] == 'feature_execution'


class AsyncSendManager(FakeManager):
    """Stand-in whose send is a coroutine, like TelemetryManager."""

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True


class TestTraceFailureDetail:
    def test_failed_stage_carries_the_reason(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-fail')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'}, error='boom: sandbox exited 127')
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        record = counters.records[0]
        assert record['error'] == 'boom: sandbox exited 127'
        assert record['features']['observations'][0]['error'] == 'boom: sandbox exited 127'

    def test_successful_stage_reports_no_error(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-ok')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        record = counters.records[0]
        assert record['error'] == ''
        assert record['features']['observations'][0]['error'] == ''

    def test_error_detail_is_bounded_and_single_line(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-noisy')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'}, error='x' * 1000 + '\n\tboom')
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        detail = counters.records[0]['error']
        assert len(detail) <= 400
        assert '\n' not in detail and '\t' not in detail


class TestIngressFailureDetail:
    def test_ingress_records_the_failure_reason(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        raised = False
        try:
            with execution.ingress(ap, 'event_done', execution_id='exec-boom'):
                counters.record(CONTEXT, **STAGE)
                raise RuntimeError('dispatch exploded')
        except RuntimeError:
            raised = True
        assert raised is True
        record = counters.records[0]
        assert record['error'].startswith('RuntimeError: dispatch exploded')
        assert record['features']['trace']['outcome'] == 'failed'
        assert record['features']['trace']['closed_by'] == 'event_done'

    def test_successful_ingress_still_reports_success(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', execution_id='exec-fine'):
            counters.record(CONTEXT, **STAGE)
        record = counters.records[0]
        assert record['error'] == ''
        assert record['features']['trace']['outcome'] == 'success'


class TestFailureOnlyTrace:
    def test_failure_without_stages_still_uploads(self):
        _, execution = get_modules()
        # sampled-out config: only failures are guaranteed to be kept
        _, counters = make_counters({'url': 'https://space.example.test', 'execution_trace_sample': 1})
        ap = make_ap(counters)
        try:
            with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='exec-empty'):
                raise RuntimeError('pipeline exploded before any stage')
        except RuntimeError:
            pass
        assert len(counters.records) == 1
        record = counters.records[0]
        assert record['error'].startswith('RuntimeError: pipeline exploded')
        assert record['features']['trace']['outcome'] == 'failed'
        assert record['features']['observations'] == []

    def test_cancelled_and_timeout_chains_report_their_outcome(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        for outcome, reason in (('cancelled', 'run cancelled by operator'), ('timeout', 'deadline exhausted')):
            binding = trace.bind(f'exec-{outcome}')
            try:
                counters.record(CONTEXT, **{**STAGE, 'outcome': outcome}, error=reason)
                counters.close_trace(binding.state, 'runner_done')
            finally:
                trace.unbind_root(binding)
            assert len(counters.records) == 1
            record = counters.records.pop(0)
            assert record['query_id'] == f'exec-{outcome}'
            assert record['features']['trace']['outcome'] == outcome
            assert record['error'] == reason


class TestLegacyRecordFields:
    def test_record_carries_legacy_top_level_columns(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-legacy')
        binding.state.started_at = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        binding.state.model_name = 'gpt-4o'
        binding.state.pipeline_plugins = ['plugin:a']
        binding.state.runner_category = 'cloud'
        try:
            counters.record(CONTEXT, **STAGE)
            counters.record(
                CONTEXT, **{**STAGE, 'family': 'runner', 'operation': 'execute', 'mode': 'agent', 'runner': 'runner-1'}
            )
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        record = counters.records[0]
        assert record['model_name'] == 'gpt-4o'
        assert record['pipeline_plugins'] == ['plugin:a']
        assert record['runner_category'] == 'cloud'
        assert record['adapter'] == 'AiocqhttpAdapter'
        assert record['runner'] == 'runner-1'
        assert record['duration_ms'] >= 1000
        assert record['timestamp'] == record['features']['trace']['ended_at']

    def test_legacy_string_fields_are_never_null(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-blank')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        record = counters.records[0]
        assert record['model_name'] == ''
        assert record['runner'] == ''
        assert record['runner_category'] == ''
        assert isinstance(record['duration_ms'], int) and record['duration_ms'] >= 0
        assert record['pipeline_plugins'] is None
