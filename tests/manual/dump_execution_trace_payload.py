"""Dump one real execution-trace payload for the Space wire-format contract test.

Run from the repository root with the project interpreter, e.g.:

    PYTHONPATH=src python tests/manual/dump_execution_trace_payload.py

`langbot-space` keeps the output as
`internal/service/testdata/execution_trace_payload.json` and asserts that its
ingest validator accepts it. Regenerate that file whenever the payload shape
changes; the Space test documents the same command.
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
from importlib import import_module


class CaptureManager:
    """Captures what TelemetryManager would have posted."""

    def __init__(self):
        self.telemetry_config = {'url': 'https://space.langbot.test', 'execution_trace': 'all'}
        self.sent: list[dict] = []

    async def send(self, payload: dict) -> bool:
        self.sent.append(payload)
        return True

    def start_send_task(self, payload: dict) -> None:
        self.sent.append(payload)


async def main() -> int:
    execution = import_module('langbot.pkg.telemetry.execution')
    trace = import_module('langbot.pkg.telemetry.trace')

    manager = CaptureManager()
    counters = execution.ExecutionCounters(manager)
    context = types.SimpleNamespace(instance_uuid='instance-1', workspace_uuid='workspace-1')
    route_ref = 'agent:11111111-1111-4111-8111-111111111111'
    run_id = '22222222-2222-4222-8222-222222222222'

    with execution.ingress(types.SimpleNamespace(telemetry=types.SimpleNamespace(execution=counters))):
        # Inbound platform event.
        counters.record(
            context,
            family='platform_event',
            operation='message.received',
            adapter='AiocqhttpAdapter',
            outcome='success',
        )
        # Route decision for that event.
        with trace.scope(route_ref=route_ref):
            counters.record(
                context,
                family='event_route',
                operation='message.received',
                mode='agent',
                adapter='AiocqhttpAdapter',
                outcome='success',
            )
            # Runner execution of the routed processor.
            run_token = trace.set_run(run_id)
            try:
                counters.record(
                    context,
                    family='runner',
                    operation='execute',
                    mode='agent',
                    runner='langbot/runner-demo',
                    outcome='success',
                )
                # Outbound platform API call made by the runner.
                counters.record(
                    context,
                    family='platform_api',
                    operation='send_message',
                    mode='agent',
                    adapter='AiocqhttpAdapter',
                    outcome='success',
                )
            finally:
                trace.reset_run(run_token)

    if len(manager.sent) != 1:
        print(f'expected exactly one payload, captured {len(manager.sent)}', file=sys.stderr)
        return 1
    print(json.dumps(manager.sent[0], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
