"""Unit tests for per-execution execution chains (pkg/telemetry/trace.py + execution.py).

One execution is one chain of independent records: one ``execution_node`` per
workflow node, emitted the moment the node completes, plus exactly one
``execution_chain`` when the execution closes. Every record of a chain carries
the same ``event_id``.
"""

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


class RejectingManager(FakeManager):
    """Stand-in whose sender refuses every batch until told to accept them."""

    def __init__(self, config=None):
        super().__init__(config)
        self.rejecting = True
        self.attempts = 0

    async def send(self, payload: dict) -> bool:
        self.attempts += 1
        if self.rejecting:
            return False
        self.sent.append(payload)
        return True


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


def nodes(counters):
    return [record for record in counters.records if record.get('event_type') == 'execution_node']


def chains(counters):
    return [record for record in counters.records if record.get('event_type') == 'execution_chain']


CONTEXT = types.SimpleNamespace(instance_uuid='instance-1', workspace_uuid='workspace-1')

STAGE = {
    'family': 'platform_event',
    'operation': 'message.received',
    'mode': 'none',
    'adapter': 'AiocqhttpAdapter',
    'outcome': 'success',
}

NODE_KEYS = {
    'event_type',
    'schema',
    'event_id',
    'instance_id',
    'workspace_uuid',
    'version',
    'edition',
    'timestamp',
    'debug',
    'sample',
    'node_id',
    'parent_node_id',
    'root',
    'seq',
    'family',
    'operation',
    'mode',
    'adapter',
    'runner',
    'outcome',
    'error',
    'route_ref',
    'run_id',
    'synthetic',
    'started_at',
    'ended_at',
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

    def test_event_id_is_the_execution_id(self):
        trace, _ = get_modules()
        binding = trace.bind('exec-1234')
        try:
            assert binding.created is True
            assert binding.state.event_id == 'exec-1234'
        finally:
            trace.unbind_root(binding)

    def test_nested_boundary_keeps_the_enclosing_execution_id(self):
        trace, _ = get_modules()
        outer = trace.bind('event-1')
        inner = trace.bind('query-9')
        try:
            assert inner.created is False
            assert inner.state.event_id == 'event-1'
        finally:
            trace.unbind_root(inner)
            trace.unbind_root(outer)

    def test_route_and_run_are_only_pinned_inside_the_block(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind()
        token = trace.set_run('run-1')
        try:
            with trace.scope(route_ref='agent:agent-1'):
                counters.record(
                    CONTEXT,
                    family='runner',
                    operation='execute',
                    mode='agent',
                    adapter='',
                    runner='langbot/runner',
                    outcome='success',
                    synthetic=False,
                )
            counters.record(
                CONTEXT,
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
        assert [(row['route_ref'], row['run_id']) for row in nodes(counters)] == [
            ('agent:agent-1', 'run-1'),
            ('', 'run-1'),
        ]


class TestTraceRecording:
    def test_stage_carries_sequence_identity_and_timestamps(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **STAGE)
            counters.record(CONTEXT, **{**STAGE, 'family': 'runner', 'operation': 'execute', 'mode': 'pipeline'})
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        rows = nodes(counters)
        assert [row['seq'] for row in rows] == [0, 1]
        # A plain observation starts and ends at the same instant.
        assert rows[0]['started_at'] == rows[0]['ended_at']
        assert {(row['instance_id'], row['workspace_uuid']) for row in rows} == {('instance-1', 'workspace-1')}
        chain = chains(counters)[0]
        assert chain['outcome'] == 'success'
        assert chain['stage_count'] == 2

    def test_oversized_identifier_never_becomes_a_stage(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind()
        try:
            counters.record(CONTEXT, **{**STAGE, 'operation': 'x' * 200})
            counters.record(CONTEXT, **{**STAGE, 'family': 'not-a-family'})
        finally:
            trace.unbind_root(binding)
        assert nodes(counters) == []

    def test_observation_without_an_owning_execution_is_dropped(self):
        _, _ = get_modules()
        _, counters = make_counters()
        # An observation that belongs to no execution is discarded instead of
        # being aggregated into a synthetic bucket.
        counters.record(CONTEXT, **STAGE)
        assert counters.records == []
        assert counters.registry == {}


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

        step_row, api_row = nodes(counters)
        assert step_row['node_id'] == step
        assert step_row['parent_node_id'] == ''  # a root step carries no parent
        assert step_row['root'] is True
        assert api_row['parent_node_id'] == step
        assert api_row['root'] is False
        assert api_row['node_id'] != step  # observations are not step nodes

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

        outer_row, inner_row, api_row = nodes(counters)
        assert (outer_row['node_id'], outer_row['parent_node_id']) == (outer, '')
        # The step's own record sits under its enclosing step, never under itself.
        assert (inner_row['node_id'], inner_row['parent_node_id']) == (inner, outer)
        assert api_row['parent_node_id'] == inner and api_row['node_id'] != inner

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

        assert first and second and first != second
        rows = nodes(counters)
        assert [row['node_id'] for row in rows] == [first, second]
        assert [row['seq'] for row in rows] == [0, 1]
        assert rows[0]['root'] is True
        assert all(row['parent_node_id'] == '' for row in rows)

    def test_cross_task_observation_joins_the_owning_execution(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        binding = execution.bind_trace(make_ap(counters), 'exec-cross')
        try:
            with trace.stage_scope() as lane:
                counters.record(
                    CONTEXT, family='pipeline', operation='run', mode='pipeline', outcome='success', node=lane
                )
                # A plugin/RPC observation arrives on a task that never had the
                # trace context; it is resolved through the execution registry and
                # still lands on the owning chain.
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

        lane_row, foreign_row = nodes(counters)
        assert lane_row['node_id'] == lane and lane_row['parent_node_id'] == '' and lane_row['root'] is True
        # The cross-task node joins the same execution, but never mirrors another
        # task's open-step stack: it is a root of the chain.
        assert foreign_row['event_id'] == 'exec-cross'
        assert foreign_row['parent_node_id'] == ''

    def test_cross_task_observation_without_an_open_step_has_no_parent(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
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

        row = nodes(counters)[0]
        assert row['parent_node_id'] == '' and row['root'] is True

    def test_scope_outside_any_trace_is_inert(self):
        trace, _ = get_modules()
        with trace.stage_scope() as node:
            assert node == ''
            assert trace.current_parent() == ''

    def test_records_outside_any_scope_are_root_nodes(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-legacy')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)

        node = nodes(counters)[0]
        assert set(node) == NODE_KEYS
        assert node['node_id'] and node['parent_node_id'] == '' and node['root'] is True
        assert node['seq'] == 0
        # Node placement lives on node records only; the chain carries none.
        assert 'node_id' not in json.dumps(chains(counters)[0], sort_keys=True)


class TestTraceDelivery:
    def test_close_emits_one_terminal_chain_record_per_execution(self):
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
        assert len(nodes(counters)) == 2
        chain_rows = chains(counters)
        assert len(chain_rows) == 1
        record = chain_rows[0]
        assert record['schema'] == 2
        assert record['event_id'] == 'exec-1'
        assert record['instance_id'] == 'instance-1'
        assert record['workspace_uuid'] == 'workspace-1'
        assert record['closed_by'] == 'event_done'
        assert record['outcome'] == 'success'
        assert record['stage_count'] == 2
        assert isinstance(record['duration_ms'], int) and record['duration_ms'] >= 0
        assert 'query_id' not in record and 'features' not in record

    def test_sampling_decision_is_deterministic_and_keeps_failures(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config(execution_trace='sampled', execution_trace_sample=2))
        in_id = next(i for i in (f'sample-{n}' for n in range(64)) if counters._sampling_decision(i)[2])
        out_id = next(i for i in (f'sample-{n}' for n in range(64)) if not counters._sampling_decision(i)[2])
        # Same id, same answer: the decision is a pure function of the identity.
        assert counters._sampling_decision(in_id) == counters._sampling_decision(in_id)

        excluded = trace.bind(out_id)
        counters.record(CONTEXT, **STAGE)
        assert excluded.state.emit_nodes is False
        assert counters._chain_emitted(excluded.state) is False
        counters.close_trace(excluded.state, 'event_done')
        trace.unbind_root(excluded)
        assert counters.records == []

        included = trace.bind(in_id)
        counters.record(CONTEXT, **STAGE)
        assert included.state.emit_nodes is True
        counters.close_trace(included.state, 'event_done')
        trace.unbind_root(included)
        assert [record['event_type'] for record in counters.records] == ['execution_node', 'execution_chain']

        counters.records.clear()
        broken = trace.bind(out_id)
        counters.record(CONTEXT, **{**STAGE, 'outcome': 'timeout'})
        assert counters._chain_emitted(broken.state) is True
        counters.close_trace(broken.state, 'event_done')
        trace.unbind_root(broken)
        assert [record['event_type'] for record in counters.records] == ['execution_chain']
        assert counters.records[0]['outcome'] == 'timeout'

    def test_failures_mode_keeps_failed_and_debug_chains_only(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config(execution_trace='failures'))

        failed = trace.bind('exec-failed')
        counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        counters.close_trace(failed.state, 'event_done')
        trace.unbind_root(failed)

        debug = trace.bind('exec-debug')
        counters.configure(debug.state, debug=True)
        counters.record(CONTEXT, **STAGE)
        counters.close_trace(debug.state, 'event_done')
        trace.unbind_root(debug)

        sampled_out = trace.bind('exec-sampled')
        counters.record(CONTEXT, **STAGE)
        counters.close_trace(sampled_out.state, 'event_done')
        trace.unbind_root(sampled_out)

        assert [record['event_id'] for record in chains(counters)] == ['exec-failed', 'exec-debug']
        assert chains(counters)[0]['outcome'] == 'failed'
        # Its node was sampled out, but the broken chain still explains itself.
        assert chains(counters)[0]['dropped_nodes'] == 1
        assert chains(counters)[1]['debug'] is True
        assert [record['event_id'] for record in nodes(counters)] == ['exec-debug']

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
        assert disabled.registry == {}

    async def test_shutdown_does_not_claim_an_unfinished_execution(self):
        trace, _ = get_modules()
        manager, counters = make_counters(trace_config())
        binding = trace.bind('exec-open')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
            await counters.shutdown()
        finally:
            trace.unbind_root(binding)
        # The already-emitted node is flushed, but shutdown never fabricates a
        # terminal chain for an execution that never completed.
        assert [record['event_type'] for record in records_sent(manager)] == ['execution_node']
        assert counters.records == []
        assert chains(counters) == []
        assert counters.registry == {}

    async def test_flush_sends_one_batch_of_complete_records(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config())
        ap = make_ap(counters)
        for index in range(2):
            with execution.ingress(ap, 'event_done', CONTEXT, execution_id=f'exec-{index}'):
                counters.record(CONTEXT, **STAGE)
        assert len(counters.records) == 4

        await counters.flush()
        assert len(manager.sent) == 1
        payload = manager.sent[0]
        assert set(payload) == {'records'}
        assert [record['event_type'] for record in payload['records']] == [
            'execution_node',
            'execution_chain',
            'execution_node',
            'execution_chain',
        ]
        assert [record['event_id'] for record in payload['records']] == ['exec-0', 'exec-0', 'exec-1', 'exec-1']
        await counters.shutdown()

    async def test_flush_interval_is_honoured(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config(telemetry_flush_seconds=1))
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='exec-timed'):
            counters.record(CONTEXT, **STAGE)
        assert counters.flush_seconds() == 1
        assert manager.sent == []
        await asyncio.sleep(1.3)
        sent = records_sent(manager)
        assert [record['event_type'] for record in sent] == ['execution_node', 'execution_chain']
        assert {record['event_id'] for record in sent} == {'exec-timed'}
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
                trace.unbind_root(binding)
        finally:
            execution.MAX_BUFFERED_RECORDS = original
        assert [record['event_id'] for record in nodes(counters)] == ['exec-2', 'exec-3', 'exec-4']
        assert counters.dropped == 2


class TestIngress:
    def test_ingress_closes_only_the_trace_it_started(self):
        _, execution = get_modules()
        manager, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', execution_id='exec-outer'):
            with execution.ingress(ap, 'pipeline_done', execution_id='exec-inner'):
                counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'})
        assert [record['event_type'] for record in counters.records] == ['execution_node', 'execution_chain']
        assert all(record['event_id'] == 'exec-outer' for record in counters.records)
        assert chains(counters)[0]['closed_by'] == 'event_done'
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
    def test_registry_joins_nodes_from_a_task_without_a_trace(self):
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
        rows = nodes(counters)
        assert len(rows) == 1
        assert rows[0]['operation'] == 'send_message' and rows[0]['event_id'] == 'run-1'

        counters.close_trace(binding.state, 'event_done')
        assert chains(counters)[0]['event_id'] == 'run-1'

    def test_registry_aliases_a_nested_execution(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='event-1'):
            with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='query-1'):
                pass
            assert set(counters.registry) == {'event-1', 'query-1'}
            counters.record(CONTEXT, **STAGE, execution_id='query-1')
        rows = nodes(counters)
        assert len(rows) == 1 and rows[0]['event_id'] == 'event-1'

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
        rows = nodes(counters)
        assert len(rows) == 1 and rows[0]['event_id'] == 'run-2'

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
        sent = records_sent(manager)
        assert [record['event_type'] for record in sent] == ['execution_node', 'execution_chain']
        assert all(record['event_id'] == 'exec-async' for record in sent)
        await counters.shutdown()


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
        assert nodes(counters)[0]['error'] == 'boom: sandbox exited 127'
        # The detail lives on the node; the chain carries the terminal outcome.
        assert chains(counters)[0]['outcome'] == 'failed'

    def test_successful_stage_reports_no_error(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-ok')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        assert nodes(counters)[0]['error'] == ''
        assert chains(counters)[0]['error'] == ''

    def test_error_detail_is_bounded_and_single_line(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-noisy')
        try:
            counters.record(CONTEXT, **{**STAGE, 'outcome': 'failed'}, error='x' * 1000 + '\n\tboom')
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        detail = chains(counters)[0]['error']
        assert len(detail) <= 200
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
        chain = chains(counters)[0]
        assert chain['error'].startswith('RuntimeError: dispatch exploded')
        assert chain['outcome'] == 'failed'
        assert chain['closed_by'] == 'event_done'

    def test_successful_ingress_still_reports_success(self):
        _, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        with execution.ingress(ap, 'event_done', execution_id='exec-fine'):
            counters.record(CONTEXT, **STAGE)
        chain = chains(counters)[0]
        assert chain['error'] == ''
        assert chain['outcome'] == 'success'


class TestFailureOnlyTrace:
    def test_failure_without_stages_still_uploads(self):
        _, execution = get_modules()
        # failures mode: nodes are not reported, but a broken chain always is.
        _, counters = make_counters({'url': 'https://space.example.test', 'execution_trace': 'failures'})
        ap = make_ap(counters)
        try:
            with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='exec-empty'):
                raise RuntimeError('pipeline exploded before any stage')
        except RuntimeError:
            pass
        rows = chains(counters)
        assert len(rows) == 1
        record = rows[0]
        assert record['error'].startswith('RuntimeError: pipeline exploded')
        assert record['outcome'] == 'failed'
        assert record['stage_count'] == 0
        assert nodes(counters) == []

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
            record = chains(counters)[-1]
            assert record['event_id'] == f'exec-{outcome}'
            assert record['outcome'] == outcome
            assert nodes(counters)[-1]['error'] == reason


class TestLegacyRecordFields:
    def test_chain_carries_execution_scoped_columns(self):
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
        record = chains(counters)[0]
        assert record['model_name'] == 'gpt-4o'
        assert record['pipeline_plugins'] == ['plugin:a']
        assert record['runner_category'] == 'cloud'
        assert record['adapter'] == 'AiocqhttpAdapter'
        assert record['runner'] == 'runner-1'
        assert record['duration_ms'] >= 1000

    def test_legacy_string_fields_are_never_null(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-blank')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        record = chains(counters)[0]
        assert record['model_name'] == ''
        assert record['runner'] == ''
        assert record['runner_category'] == ''
        assert isinstance(record['duration_ms'], int) and record['duration_ms'] >= 0
        assert record['pipeline_plugins'] is None


class TestNoTraceTtl:
    def test_nodes_more_than_two_minutes_apart_still_emit(self):
        trace, _ = get_modules()
        _, counters = make_counters(trace_config())
        binding = trace.bind('exec-long')
        try:
            counters.record(CONTEXT, **STAGE)
            # A gap far beyond the old 120s TTL must not sweep the chain: there is
            # no local trace deadline any more, so both nodes and the terminal
            # chain are still emitted.
            binding.state.started_at = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
            counters.record(CONTEXT, **{**STAGE, 'operation': 'still.alive'})
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        rows = nodes(counters)
        assert [record['seq'] for record in rows] == [0, 1]
        assert [record['operation'] for record in rows] == ['message.received', 'still.alive']
        chain = chains(counters)[0]
        assert chain['stage_count'] == 2
        assert chain['duration_ms'] >= 120_000


class TestFlushDelivery:
    async def test_rejected_batch_stays_buffered_and_is_retried(self):
        trace, execution = get_modules()
        manager = RejectingManager(trace_config())
        counters = execution.ExecutionCounters(manager)
        binding = trace.bind('exec-retry')
        try:
            counters.record(CONTEXT, **STAGE)
            assert await counters.flush() is False
            assert manager.attempts == execution.MAX_FLUSH_ATTEMPTS
            # The record was never lost: it is still buffered and unsent.
            assert len(counters.records) == 1 and manager.sent == []
            manager.rejecting = False
            assert await counters.flush() is True
        finally:
            trace.unbind_root(binding)
        assert counters.records == []
        assert [record['event_id'] for record in records_sent(manager)] == ['exec-retry']
        await counters.shutdown()

    async def test_health_reports_buffered_sent_and_dropped(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        binding = execution.bind_trace(ap, 'exec-health')
        try:
            counters.record(CONTEXT, **STAGE)
            health = counters.health()
            assert health['records_buffered'] == 1
            assert health['records_sent'] == 0
            assert health['records_dropped'] == 0
            assert health['executions_in_flight'] == 1
            await counters.flush()
            health = counters.health()
            assert health['records_buffered'] == 0
            assert health['records_sent'] == 1
        finally:
            trace.unbind_root(binding)

        # Overflowing the outbound buffer is surfaced as dropped records.
        original = execution.MAX_BUFFERED_RECORDS
        execution.MAX_BUFFERED_RECORDS = 1
        try:
            for index in range(3):
                inner = trace.bind(f'exec-drop-{index}')
                counters.record(CONTEXT, **STAGE)
                trace.unbind_root(inner)
        finally:
            execution.MAX_BUFFERED_RECORDS = original
        health = counters.health()
        assert health['records_dropped'] == 2
        assert health['records_buffered'] == 1
        await counters.shutdown()


class TestSiblingTaskIsolation:
    async def test_sibling_stage_scopes_do_not_corrupt_parent_links(self):
        trace, execution = get_modules()
        _, counters = make_counters(trace_config())
        ap = make_ap(counters)
        opened = {}

        async def work(name):
            with trace.stage_scope() as node:
                opened[name] = node
                counters.record(CONTEXT, **{**STAGE, 'operation': name, 'node': node})

        async def scenario():
            with execution.ingress(ap, 'event_done', CONTEXT, execution_id='exec-siblings'):
                await asyncio.gather(work('alpha'), work('beta'))
            snapshot = list(counters.records)
            await counters.shutdown()
            return snapshot

        records = await scenario()
        rows = {record['operation']: record for record in records if record['event_type'] == 'execution_node'}
        assert opened['alpha'] != opened['beta']
        # Each sibling's step is its own root: neither becomes the other's parent.
        assert rows['alpha']['node_id'] == opened['alpha']
        assert rows['beta']['node_id'] == opened['beta']
        assert rows['alpha']['parent_node_id'] == ''
        assert rows['beta']['parent_node_id'] == ''
        assert [record['event_type'] for record in records].count('execution_chain') == 1


class TestSamplingShape:
    def test_platform_prefixed_event_id_is_emitted_at_default_config(self):
        trace, _ = get_modules()
        _, counters = make_counters()  # no execution_trace override -> default mode
        assert counters.trace_mode() == 'all'
        # The identity is hashed, not parsed: a platform-prefixed id samples the
        # same way any other id shape does.
        assert counters._sampling_decision('platform:bot-1:message-1') == ('all', 1, True)
        binding = trace.bind('platform:bot-1:message-1')
        try:
            counters.record(CONTEXT, **STAGE)
            counters.close_trace(binding.state, 'event_done')
        finally:
            trace.unbind_root(binding)
        assert [record['event_type'] for record in counters.records] == ['execution_node', 'execution_chain']
        assert all(record['event_id'] == 'platform:bot-1:message-1' for record in counters.records)
