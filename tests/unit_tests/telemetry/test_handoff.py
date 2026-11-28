"""One inbound platform event is exactly one execution chain across the queue.

A routed message is handled by the platform listener task, queued, and later
run by a query-pool task that does not inherit the listener's context. These
tests drive that real shape: the ingress boundary, the route step, a handoff
through query variables and the RuntimePipeline lane in a fresh context.
"""

from __future__ import annotations

import asyncio
import contextvars
import types
from importlib import import_module

from test_pipeline_lane import CONTEXT, build_counters, build_lane, build_query, stop_counters


def modules():
    import_module('langbot.pkg.core.app')
    return (
        import_module('langbot.pkg.pipeline.pipelinemgr'),
        import_module('langbot.pkg.telemetry.execution'),
        import_module('langbot.pkg.telemetry.trace'),
    )


def nodes(counters):
    return [record for record in counters.records if record['event_type'] == 'execution_node']


def chains(counters):
    return [record for record in counters.records if record['event_type'] == 'execution_chain']


def platform_listener(ap, execution, trace, event_id, queue, **record_kwargs):
    """Mirror RuntimeBot._handle_platform_event routing into a Pipeline."""

    async def run():
        with execution.ingress(ap, 'completed', CONTEXT, event_id, require_route=True) as binding:
            binding.state.adapter = 'AiocqhttpAdapter'
            with trace.stage_scope() as root:
                trace.admit()
                with trace.stage_scope() as route:
                    # aggregator.add_message
                    queue.append({**execution.handoff(ap)})
                    execution.record(
                        ap,
                        CONTEXT,
                        family='event_route',
                        operation='message.received',
                        mode='pipeline',
                        outcome='success',
                        node=route,
                    )
                execution.record(
                    ap,
                    CONTEXT,
                    family='platform_event',
                    operation='message.received',
                    adapter='AiocqhttpAdapter',
                    outcome='success',
                    node=root,
                    **record_kwargs,
                )

    return run


async def run_in_fresh_context(coro_fn):
    return await asyncio.create_task(coro_fn(), context=contextvars.Context())


async def test_routed_event_and_its_queued_pipeline_report_one_chain():
    pipelinemgr, execution, trace = modules()
    counters, ap = build_counters()
    queue: list[dict] = []
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-1', queue))
    # The listener returned after queuing: nothing may close yet.
    assert chains(counters) == []

    lane = build_lane(pipelinemgr, ap)

    async def fake_process(_query):
        state = trace.current()
        state.model_name = 'gpt-x'
        execution.record(
            ap, CONTEXT, family='runner', operation='execute', mode='pipeline', runner='r', outcome='success'
        )

    lane._process_query = fake_process

    async def pipeline_worker():
        await lane.process_query(build_query(variables=queue.pop()))

    await run_in_fresh_context(pipeline_worker)
    await stop_counters(counters)

    [chain] = chains(counters)
    assert chain['event_id'] == 'msg-1'
    assert chain['closed_by'] == 'completed'
    assert chain['outcome'] == 'success'
    assert chain['model_name'] == 'gpt-x'
    assert chain['adapter'] == 'AiocqhttpAdapter'
    by_family = {record['family']: record for record in nodes(counters)}
    assert chain['stage_count'] == len(nodes(counters)) == 4
    root = by_family['platform_event']
    route = by_family['event_route']
    lane_node = by_family['pipeline']
    runner = by_family['runner']
    # One tree in the order things happened.
    assert root['root'] and root['parent_node_id'] == ''
    assert route['parent_node_id'] == root['node_id']
    assert lane_node['parent_node_id'] == route['node_id'] and not lane_node['root']
    assert runner['parent_node_id'] == lane_node['node_id']
    assert root['seq'] < route['seq'] < lane_node['seq'] < runner['seq']
    assert len({record['seq'] for record in nodes(counters)}) == 4


async def test_pipeline_failure_lands_on_the_single_chain_with_full_detail():
    pipelinemgr, execution, trace = modules()
    counters, ap = build_counters()
    queue: list[dict] = []
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-2', queue))
    lane = build_lane(pipelinemgr, ap)

    async def fake_process(_query):
        try:
            raise ConnectionError('upstream reset')
        except ConnectionError as exc:
            raise RuntimeError('provider returned 500') from exc

    lane._process_query = fake_process

    async def pipeline_worker():
        try:
            await lane.process_query(build_query(variables=queue.pop()))
        except RuntimeError:
            pass

    await run_in_fresh_context(pipeline_worker)
    await stop_counters(counters)

    [chain] = chains(counters)
    assert chain['outcome'] == 'failed'
    assert chain['error'].startswith('RuntimeError: provider returned 500')
    assert 'Caused by: ConnectionError: upstream reset' in chain['error']
    assert 'Traceback (most recent call last):' in chain['error']


async def test_dropped_query_closes_the_chain_once_with_its_reason():
    _, execution, trace = modules()
    counters, ap = build_counters()
    queue: list[dict] = []
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-3', queue))
    variables = queue.pop()
    execution.release_handoff(ap, variables, error='Query dropped before its Pipeline ran')
    execution.release_handoff(ap, variables, error='released twice')
    await stop_counters(counters)

    [chain] = chains(counters)
    assert chain['closed_by'] == 'completed'
    assert chain['outcome'] == 'failed'
    assert chain['error'] == 'Query dropped before its Pipeline ran'


async def test_aggregated_event_closes_as_merged_into_the_running_chain():
    _, execution, trace = modules()
    counters, ap = build_counters()
    queue: list[dict] = []
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-a', queue))
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-b', queue))
    first, second = queue
    execution.release_handoff(ap, second, merged_into='msg-a')
    await stop_counters(counters)

    [chain] = chains(counters)
    assert chain['event_id'] == 'msg-b'
    assert chain['closed_by'] == 'merged'
    assert chain['merged_into'] == 'msg-a'
    assert first.get(execution.HANDOFF_SETTLED_KEY) is None


async def test_handoff_that_never_reports_back_closes_as_timeout():
    _, execution, trace = modules()
    counters, ap = build_counters()
    queue: list[dict] = []
    await run_in_fresh_context(platform_listener(ap, execution, trace, 'msg-t', queue))
    for key in list(counters.registry_deadlines):
        counters.registry_deadlines[key] = 0
    counters._sweep_registry(1)
    await stop_counters(counters)

    [chain] = chains(counters)
    assert chain['closed_by'] == 'timeout'


async def test_discarded_route_keeps_the_queued_lane_unreported():
    pipelinemgr, execution, trace = modules()
    counters, ap = build_counters()
    lane = build_lane(pipelinemgr, ap)

    async def fake_process(_query):
        execution.record(ap, CONTEXT, family='runner', operation='execute', mode='pipeline', outcome='success')

    lane._process_query = fake_process
    with trace.suppress_reporting():
        variables = execution.handoff(ap) or {execution.HANDOFF_SUPPRESSED_KEY: True}
    await lane.process_query(build_query(variables=variables))
    await stop_counters(counters)
    assert counters.records == []


def test_flush_batches_one_workspace_per_request():
    _, execution, _ = modules()
    counters, _ = build_counters()
    counters.records = [
        {'workspace_uuid': 'ws-1', 'event_type': 'execution_node'},
        {'workspace_uuid': 'ws-2', 'event_type': 'execution_node'},
    ]
    sent = []

    async def send(payload):
        sent.append(payload)
        return True

    counters.manager = types.SimpleNamespace(send=send, telemetry_config={})
    asyncio.run(counters.flush())
    assert sent[0]['workspace_uuid'] == 'ws-1' and len(sent[0]['records']) == 1
