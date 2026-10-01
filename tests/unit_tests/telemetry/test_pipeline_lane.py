"""The Pipeline lane must land its failure on the owning execution trace."""

from __future__ import annotations

import asyncio
import types
from importlib import import_module

import pytest


def get_modules():
    # Import the application package first; the pipeline package is wired into it.
    import_module('langbot.pkg.core.app')
    return (
        import_module('langbot.pkg.pipeline.pipelinemgr'),
        import_module('langbot.pkg.telemetry.execution'),
    )


def get_trace():
    import_module('langbot.pkg.core.app')
    return import_module('langbot.pkg.telemetry.trace')


class FakeManager:
    def __init__(self):
        self.telemetry_config = {'url': 'https://space.example.test', 'execution_trace': 'all'}
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True


CONTEXT = types.SimpleNamespace(instance_uuid='instance-1', workspace_uuid='workspace-1')


def build_pipeline(pipelinemgr, ap):
    pipeline = object.__new__(pipelinemgr.RuntimePipeline)
    pipeline.ap = ap
    pipeline.execution_context = CONTEXT
    return pipeline


def test_lane_failure_marks_the_owned_trace_without_any_prior_stage():
    pipelinemgr, execution = get_modules()
    manager = FakeManager()
    counters = execution.ExecutionCounters(manager)
    ap = types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))
    pipeline = build_pipeline(pipelinemgr, ap)
    query = types.SimpleNamespace(pipeline_config={})

    with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='query-7'):
        pipeline._record_lane_failure(query, 'sandbox exited 127')

    assert len(counters.records) == 1
    record = counters.records[0]
    assert record['query_id'] == 'query-7'
    assert record['error'] == 'sandbox exited 127'
    assert record['features']['trace']['outcome'] == 'failed'
    observations = record['features']['observations']
    assert [(row['family'], row['operation'], row['outcome']) for row in observations] == [
        ('runner', 'execute', 'failed')
    ]


def test_lane_failure_does_not_duplicate_the_runner_node_the_orchestrator_recorded():
    """A break inside a runner is already a node; the lane only carries the reason over."""
    pipelinemgr, execution = get_modules()
    manager = FakeManager()
    counters = execution.ExecutionCounters(manager)
    ap = types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))
    pipeline = build_pipeline(pipelinemgr, ap)
    query = types.SimpleNamespace(pipeline_config={})

    with execution.ingress(ap, 'pipeline_done', CONTEXT, execution_id='query-8'):
        execution.record(
            ap,
            CONTEXT,
            family='runner',
            operation='execute',
            mode='pipeline',
            runner='plugin:langbot-team/LocalAgent/default',
            outcome='failed',
            error='No authorized model for local-agent',
        )
        pipeline._record_lane_failure(query, 'No authorized model for local-agent')

    observations = [
        (row['family'], row['operation'], row['outcome'])
        for record in counters.records
        for row in record['features']['observations']
    ]
    assert observations == [('runner', 'execute', 'failed')]
    assert counters.records[-1]['features']['trace']['outcome'] == 'failed'


def build_counters():
    manager = FakeManager()
    counters = import_module('langbot.pkg.telemetry.execution').ExecutionCounters(manager)
    ap = types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))
    return counters, ap


def build_lane(pipelinemgr, ap):
    # ``process_query`` lives on the RuntimePipeline lane, not on PipelineManager.
    lane = object.__new__(pipelinemgr.RuntimePipeline)
    lane.ap = ap
    lane.execution_context = CONTEXT
    return lane


def build_query(**overrides):
    query = types.SimpleNamespace(query_uuid='exec-lane', query_id=1, pipeline_config={}, variables={})
    for key, value in overrides.items():
        setattr(query, key, value)
    return query


def lane_shapes(counters):
    return [
        (row['family'], row['operation'], row.get('node'), row.get('parent'))
        for record in counters.records
        for row in record['features']['observations']
    ]


async def stop_counters(counters):
    """Cancel the telemetry flush task so no loop is left with pending work."""
    task = counters.task
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    counters.task = None


def test_lane_step_owns_the_apis_and_runner_it_calls():
    pipelinemgr, execution = get_modules()
    trace = get_trace()
    counters, ap = build_counters()
    lane = build_lane(pipelinemgr, ap)
    query = build_query()
    seen = {}

    async def fake_process(_query):
        execution.record(
            ap, CONTEXT, family='platform_api', operation='send_message',
            adapter='AiocqhttpAdapter', mode='pipeline', outcome='success',
        )
        with trace.stage_scope() as run_node:
            seen['run'] = run_node
            execution.record(
                ap, CONTEXT, family='runner', operation='execute', mode='pipeline', outcome='success', node=run_node
            )
        # A reply issued after the runner still belongs to the lane.
        execution.record(
            ap, CONTEXT, family='platform_api', operation='reply_message',
            adapter='AiocqhttpAdapter', mode='pipeline', outcome='success',
        )

    lane._process_query = fake_process

    async def scenario():
        await lane.process_query(query)
        await stop_counters(counters)

    asyncio.run(scenario())

    shapes = lane_shapes(counters)
    lane_node = shapes[-1][2]
    assert lane_node == 'n1'
    assert shapes == [
        ('platform_api', 'send_message', None, lane_node),
        ('runner', 'execute', seen['run'], lane_node),
        ('platform_api', 'reply_message', None, lane_node),
        # The lane step is recorded last; a standalone lane is a root.
        ('pipeline', 'run', lane_node, None),
    ]


def test_lane_node_nests_under_the_platform_route_that_called_it():
    pipelinemgr, execution = get_modules()
    trace = get_trace()
    counters, ap = build_counters()
    lane = build_lane(pipelinemgr, ap)
    query = build_query(query_uuid='exec-routed')

    async def fake_process(_query):
        execution.record(
            ap, CONTEXT, family='platform_api', operation='send_message', mode='pipeline', outcome='success'
        )

    lane._process_query = fake_process

    async def scenario():
        # A platform event owns the trace; the route step wraps the Pipeline lane.
        with execution.ingress(ap, 'event_done', CONTEXT, execution_id='exec-routed'):
            with trace.stage_scope() as event_node:
                execution.record(
                    ap, CONTEXT, family='platform_event', operation='message.received',
                    adapter='AiocqhttpAdapter', outcome='success', node=event_node,
                )
                with trace.stage_scope() as route_node:
                    execution.record(
                        ap, CONTEXT, family='event_route', operation='message.received',
                        adapter='AiocqhttpAdapter', outcome='success', node=route_node,
                    )
                    await lane.process_query(query)
        await stop_counters(counters)
        return event_node, route_node

    event_node, route_node = asyncio.run(scenario())

    assert (event_node, route_node) == ('n1', 'n2')
    assert lane_shapes(counters) == [
        ('platform_event', 'message.received', event_node, None),
        ('event_route', 'message.received', route_node, event_node),
        # The API is called by the lane, so it hangs on the lane node.
        ('platform_api', 'send_message', None, 'n3'),
        ('pipeline', 'run', 'n3', route_node),
    ]


def test_broken_lane_records_a_failed_step_with_its_reason():
    pipelinemgr, execution = get_modules()
    counters, ap = build_counters()
    lane = build_lane(pipelinemgr, ap)

    async def fake_process(_query):
        raise RuntimeError('lane exploded')

    lane._process_query = fake_process

    async def scenario():
        try:
            await lane.process_query(build_query())
        finally:
            await stop_counters(counters)

    with pytest.raises(RuntimeError, match='lane exploded'):
        asyncio.run(scenario())

    family, operation, node, parent = lane_shapes(counters)[-1]
    row = counters.records[0]['features']['observations'][-1]
    assert (family, operation, node, parent) == ('pipeline', 'run', 'n1', None)
    assert row['outcome'] == 'failed'
    assert row['error'] == 'lane exploded'


def test_lane_reported_failure_marks_the_step_failed():
    pipelinemgr, execution = get_modules()
    counters, ap = build_counters()
    lane = build_lane(pipelinemgr, ap)
    query = build_query(variables={'_monitoring_has_error': True})

    async def fake_process(_query):
        return None

    lane._process_query = fake_process

    async def scenario():
        await lane.process_query(query)
        await stop_counters(counters)

    asyncio.run(scenario())

    row = counters.records[0]['features']['observations'][-1]
    assert (row['family'], row['operation'], row['outcome']) == ('pipeline', 'run', 'failed')
