"""Cancelled work is reported as ``cancelled``, never as a failed execution."""

from __future__ import annotations

import asyncio
import types
from importlib import import_module

import pytest


CONTEXT = types.SimpleNamespace(instance_uuid='instance-1', workspace_uuid='workspace-1')


class FakeManager:
    def __init__(self):
        self.telemetry_config = {'url': 'https://space.example.test', 'execution_trace': 'all'}
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True


def build():
    execution = import_module('langbot.pkg.telemetry.execution')
    counters = execution.ExecutionCounters(FakeManager())
    ap = types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))
    return execution, counters, ap


def chains(counters):
    return [record for record in counters.records if record['event_type'] == 'execution_chain']


async def stop(counters):
    if counters.task is not None:
        counters.task.cancel()
        await asyncio.gather(counters.task, return_exceptions=True)
        counters.task = None


@pytest.mark.parametrize('exc', [asyncio.CancelledError(), GeneratorExit()])
async def test_cancelled_ingress_closes_the_chain_as_cancelled(exc):
    execution, counters, ap = build()
    with pytest.raises(type(exc)):
        with execution.ingress(ap, 'completed', CONTEXT, execution_id='event-cancelled'):
            execution.record(ap, CONTEXT, family='runner', operation='execute', outcome='success')
            raise exc
    await stop(counters)
    (chain,) = chains(counters)
    assert chain['outcome'] == 'cancelled'


async def test_failed_ingress_still_closes_the_chain_as_failed():
    execution, counters, ap = build()
    with pytest.raises(RuntimeError):
        with execution.ingress(ap, 'completed', CONTEXT, execution_id='event-failed'):
            execution.record(ap, CONTEXT, family='runner', operation='execute', outcome='success')
            raise RuntimeError('boom')
    await stop(counters)
    (chain,) = chains(counters)
    assert chain['outcome'] == 'failed'
    assert chain['error'].startswith('RuntimeError: boom')


async def test_cancelled_handed_off_lane_closes_the_chain_as_cancelled():
    execution, counters, ap = build()
    with execution.ingress(ap, 'completed', CONTEXT, execution_id='event-handoff'):
        variables = execution.handoff(ap)
    with pytest.raises(asyncio.CancelledError):
        with execution.resume(ap, variables):
            raise asyncio.CancelledError()
    await stop(counters)
    (chain,) = chains(counters)
    assert chain['outcome'] == 'cancelled'


@pytest.mark.parametrize(
    ('result', 'expected'),
    [
        (None, 'success'),
        (False, 'failed'),
        ({'errcode': 40001}, 'failed'),
        ({}, 'unknown'),
        ({'message_id': 'm-1'}, 'success'),
    ],
)
def test_platform_api_result_outcome(result, expected):
    platform = import_module('langbot.pkg.telemetry.platform')
    assert platform.result_outcome(result) == expected


async def test_reply_that_returns_nothing_is_recorded_as_success():
    execution, counters, ap = build()
    platform = import_module('langbot.pkg.telemetry.platform')

    class Adapter:
        def get_supported_apis(self):
            return ['reply_message']

        async def reply_message(self, *args, **kwargs):
            return None

    adapter = Adapter()
    platform.observe_adapter(ap, CONTEXT, adapter)
    with execution.ingress(ap, 'completed', CONTEXT, execution_id='event-reply'):
        await adapter.reply_message()
    await stop(counters)
    (node,) = [record for record in counters.records if record['event_type'] == 'execution_node']
    assert (node['family'], node['operation'], node['outcome']) == ('platform_api', 'reply_message', 'success')
