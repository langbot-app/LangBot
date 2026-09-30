"""Bounded, content-free execution counters for the existing telemetry sender.

This module reports observations only. Coverage catalogs and acceptance rules
belong to Space. Aggregation keys include both immutable execution identities.

Two shapes share one payload type:

* window counters, aggregated by ``(family, operation, mode, adapter, runner,
  outcome, synthetic)`` — unchanged coverage reporting;
* per-event traces, one bounded payload per traced event, keyed by
  ``query_id = trace_id`` so Space can fetch a whole chain by primary identity.

Traces are additive: they never alter the counters, and both are bounded in
memory, batch size and send concurrency.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import datetime, timezone
from uuid import uuid4

from . import trace as trace_mod
from .identity import workspace_identity
from .trace import TraceState

MAX_KEYS = 512
MAX_BATCH = 32
FLUSH_SECONDS = 60
MODES = frozenset({'pipeline', 'agent', 'event_processor', 'none'})
OUTCOMES = frozenset({'success', 'failed', 'cancelled', 'timeout', 'skipped', 'unknown'})

# Trace bounds: stages per trace, traces buffered per process, trace lifetime.
MAX_TRACES = 64
TRACE_TTL_SECONDS = 120
TRACE_MODES = frozenset({'off', 'failures', 'sampled', 'all'})
DEFAULT_TRACE_MODE = 'sampled'
DEFAULT_TRACE_SAMPLE = 20


class ExecutionCounters:
    def __init__(self, manager):
        self.manager = manager
        self.pending: dict[tuple, dict] = {}
        self.task: asyncio.Task | None = None
        self.dropped = 0
        self.traces: dict[str, TraceState] = {}
        self.trace_deadlines: dict[str, float] = {}
        self.dropped_traces = 0

    # ------------------------------------------------------------------ config

    def trace_mode(self) -> str:
        mode = str(self.manager.telemetry_config.get('execution_trace', DEFAULT_TRACE_MODE) or '').strip().lower()
        return mode if mode in TRACE_MODES else DEFAULT_TRACE_MODE

    def trace_sample(self) -> int:
        try:
            sample = int(self.manager.telemetry_config.get('execution_trace_sample', DEFAULT_TRACE_SAMPLE))
        except (TypeError, ValueError):
            sample = DEFAULT_TRACE_SAMPLE
        return sample if 1 <= sample <= 100000 else DEFAULT_TRACE_SAMPLE

    # --------------------------------------------------------------- recording

    def record(
        self,
        context,
        *,
        family: str,
        operation: str,
        mode: str = 'none',
        adapter: str = '',
        runner: str = '',
        outcome: str = 'unknown',
        synthetic: bool = False,
    ):
        try:
            cfg = self.manager.telemetry_config
            if not cfg or cfg.get('disable_telemetry', False) or not cfg.get('url'):
                return
            if family not in {'platform_event', 'event_route', 'runner', 'platform_api'}:
                return
            if mode not in MODES or outcome not in OUTCOMES:
                return
            # Only code-defined identifiers are accepted; never pass user values.
            if any(not isinstance(v, str) or len(v) > 160 for v in (operation, adapter, runner)):
                return
            identity = workspace_identity(context)
            state = trace_mod.current()
            if state is not None:
                self._record_trace_stage(
                    state,
                    identity=identity,
                    family=family,
                    operation=operation,
                    mode=mode,
                    adapter=adapter,
                    runner=runner,
                    outcome=outcome,
                    synthetic=synthetic,
                )
            key = (
                identity['instance_id'],
                identity['workspace_uuid'],
                family,
                operation,
                mode,
                adapter,
                runner,
                outcome,
                bool(synthetic),
            )
            row = self.pending.get(key)
            if row is None:
                if len(self.pending) >= MAX_KEYS:
                    self.dropped += 1
                    return
                row = {'count': 0, 'first_seen': datetime.now(timezone.utc).isoformat()}
                self.pending[key] = row
            row['count'] = min(row['count'] + 1, 2147483647)
            row['last_seen'] = datetime.now(timezone.utc).isoformat()
            self._ensure_loop()
        except Exception:
            # Observability must never change execution behavior.
            return

    def _record_trace_stage(
        self, state: TraceState, *, identity, family, operation, mode, adapter, runner, outcome, synthetic
    ) -> None:
        if state.abandoned:
            return
        if state.trace_id not in self.traces:
            # Never buffer traces this configuration would discard anyway.
            if self.trace_mode() == 'off' or len(self.traces) >= MAX_TRACES:
                self.dropped += 1
                state.abandoned = True
                return
            self.traces[state.trace_id] = state
            self.trace_deadlines[state.trace_id] = time.monotonic() + TRACE_TTL_SECONDS
            state.identity = identity
        state.append(
            family=family,
            operation=operation,
            mode=mode,
            adapter=adapter,
            runner=runner,
            outcome=outcome,
            synthetic=bool(synthetic),
        )

    def _ensure_loop(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())

    # ------------------------------------------------------------------ traces

    def close_trace(self, state: TraceState, reason: str = 'event_done') -> None:
        """Emit one trace payload when it matches the configured sample."""
        try:
            if self.traces.pop(state.trace_id, None) is None:
                return
            self.trace_deadlines.pop(state.trace_id, None)
            if not state.stages or not self._trace_emitted(state):
                return
            payload = self._build_trace_payload(state, reason)
            if payload is not None:
                self.manager.start_send_task(payload)
        except Exception:
            return

    def _trace_emitted(self, state: TraceState) -> bool:
        mode = self.trace_mode()
        if mode == 'off':
            return False
        if mode == 'all':
            return True
        # A failed, cancelled or timed-out stage is always worth keeping.
        if any(stage['outcome'] not in ('success', 'skipped') for stage in state.stages):
            return True
        # WebUI debug runs are deliberately traced; they stay flagged synthetic.
        if state.synthetic:
            return True
        if mode == 'failures':
            return False
        try:
            return int(state.trace_id[:8], 16) % self.trace_sample() == 0
        except ValueError:
            return False

    def _build_trace_payload(self, state: TraceState, reason: str) -> dict | None:
        from ..utils import constants

        identity = state.identity
        if not identity.get('instance_id') or not identity.get('workspace_uuid'):
            return None
        observations = [{**stage, 'trace_id': state.trace_id, 'count': 1} for stage in state.stages]
        return {
            'event_type': 'feature_execution',
            # One payload per trace: lookup uses the indexed query_id column.
            'query_id': state.trace_id,
            'instance_id': identity['instance_id'],
            'workspace_uuid': identity['workspace_uuid'],
            'version': constants.semantic_version,
            'edition': constants.edition,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'features': {
                'schema': 1,
                'observations': observations,
                'trace': {
                    'closed_by': reason,
                    'started_at': state.started_at,
                    'ended_at': datetime.now(timezone.utc).isoformat(),
                    'route_ref': next((s['route_ref'] for s in state.stages if s['route_ref']), ''),
                    'run_id': next((s['run_id'] for s in state.stages if s['run_id']), ''),
                    'outcome': state.outcome(),
                    'dropped_stages': state.dropped_stages,
                },
            },
        }

    def _sweep_traces(self, now: float) -> None:
        for trace_id in [key for key, deadline in self.trace_deadlines.items() if deadline <= now]:
            state = self.traces.get(trace_id)
            if state is not None:
                self.close_trace(state, 'ttl')

    # ----------------------------------------------------------------- flushing

    async def _loop(self):
        last_flush = time.monotonic()
        while self.pending or self.traces:
            # Traces expire on a short TTL; counters keep their minute cadence.
            await asyncio.sleep(1 if self.traces else FLUSH_SECONDS)
            now = time.monotonic()
            self._sweep_traces(now)
            if self.pending and now - last_flush >= FLUSH_SECONDS:
                last_flush = now
                await self.flush()
        self.task = None

    async def flush(self):
        from ..utils import constants

        # Remove only one bounded batch; subsequent windows drain the remainder.
        # Drain one tenant per minute, at most one request, round-robin by insertion.
        if not self.pending:
            return
        tenant = next(iter(self.pending))[:2]
        keys = [key for key in self.pending if key[:2] == tenant][:MAX_BATCH]
        groups: dict[tuple[str, str], list[dict]] = {}
        for key in keys:
            row = self.pending.pop(key)
            instance, workspace, family, operation, mode, adapter, runner, outcome, synthetic = key
            groups.setdefault((instance, workspace), []).append(
                {
                    **row,
                    'family': family,
                    'operation': operation,
                    'mode': mode,
                    'adapter': adapter,
                    'runner': runner,
                    'outcome': outcome,
                    'synthetic': synthetic,
                }
            )
        for (instance, workspace), observations in groups.items():
            payload = {
                'event_type': 'feature_execution',
                'query_id': str(uuid4()),
                'instance_id': instance,
                'workspace_uuid': workspace,
                'version': constants.semantic_version,
                'edition': constants.edition,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'features': {'schema': 1, 'observations': observations},
            }
            if not await self.manager.send(payload):
                await asyncio.sleep(1)
                await self.manager.send(payload)

    async def shutdown(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        try:
            await asyncio.wait_for(self.flush(), timeout=2)
        except (Exception, asyncio.CancelledError):
            pass
        self.pending.clear()
        # Traces of in-flight events cannot be completed during shutdown.
        self.dropped += len(self.traces)
        self.dropped_traces += len(self.traces)
        self.traces.clear()
        self.trace_deadlines.clear()


def record(ap, context, **observation):
    """Best-effort bridge usable with optional telemetry and test doubles."""
    try:
        counters = getattr(getattr(ap, 'telemetry', None), 'execution', None)
        if isinstance(counters, ExecutionCounters):
            counters.record(context, **observation)
    except Exception:
        pass


def close_trace(ap, state, reason: str = 'event_done') -> None:
    """Best-effort trace close usable with optional telemetry and test doubles."""
    try:
        counters = getattr(getattr(ap, 'telemetry', None), 'execution', None)
        if isinstance(counters, ExecutionCounters):
            counters.close_trace(state, reason)
    except Exception:
        pass


@contextlib.contextmanager
def ingress(ap, reason: str = 'event_done'):
    """Trace one ingress boundary; only the owner of the trace closes it.

    Nested boundaries (an event routed into a Pipeline, a Runner invoked from a
    dispatch) reuse the in-flight trace instead of starting a second one.
    """
    binding = trace_mod.bind()
    try:
        yield binding
    finally:
        if trace_mod.unbind_root(binding):
            close_trace(ap, binding.state, reason)
