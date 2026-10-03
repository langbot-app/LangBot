"""Content-free execution records for the existing telemetry sender.

This module reports observations only. Coverage catalogs and acceptance rules
belong to Space.

One complete execution is one record: the execution identity (Pipeline query,
inbound platform event or Agent run), its bounded ordered stages and its
terminal outcome. Nothing is aggregated or counted across executions — every
record carries the id of the execution it belongs to, so Space can fetch the
whole chain by primary identity. Records are buffered whole and flushed as
``{"records": [...]}`` on the configured cadence and on shutdown; an in-flight
trace is never flushed half-written.

Memory is bounded in stages per trace, buffered traces, buffered records, the
cross-task execution registry and flush batch size.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import json
import time
from datetime import datetime, timezone

from . import trace as trace_mod
from .identity import workspace_identity
from .trace import TraceState

MODES = frozenset({'pipeline', 'agent', 'event_processor', 'none'})
OUTCOMES = frozenset({'success', 'failed', 'cancelled', 'timeout', 'skipped', 'unknown'})

# Trace bounds: stages per trace, traces buffered per process, trace lifetime.
MAX_TRACES = 64
TRACE_TTL_SECONDS = 120
TRACE_MODES = frozenset({'off', 'failures', 'sampled', 'all'})
DEFAULT_TRACE_MODE = 'sampled'
DEFAULT_TRACE_SAMPLE = 20

# Record bounds: buffered records, one flush batch, flush cadence, registry.
MAX_BUFFERED_RECORDS = 512
MAX_RECORDS_PER_FLUSH = 128
MAX_FLUSH_BYTES = 200 * 1024
DEFAULT_FLUSH_SECONDS = 180
MAX_REGISTRY_KEYS = 256

# Set by cross-task call sites (plugin/RPC actions) that run without the
# ingress context but know which execution they belong to.
_execution_id: contextvars.ContextVar[str] = contextvars.ContextVar('telemetry_execution_id', default='')


def set_execution_id(execution_id: str) -> contextvars.Token:
    return _execution_id.set(str(execution_id or '').strip())


def reset_execution_id(token: contextvars.Token | None) -> None:
    if token is None:
        return
    try:
        _execution_id.reset(token)
    except (ValueError, RuntimeError):
        # A token from another context must never break execution.
        pass


def current_execution_id() -> str:
    return _execution_id.get()


def _bounded_error(value, limit: int = 400) -> str:
    """Bound and de-fang one failure detail before it leaves the process.

    Error text is operator-facing: keep it single-line, printable and short so a
    noisy failure cannot smuggle control characters or bloat the payload.
    """
    if value is None:
        return ''
    text = ''.join(ch if ch.isprintable() else ' ' for ch in str(value))
    text = ' '.join(text.split())
    return text[:limit]


def _duration_ms(started_at: str, ended_at: str) -> int:
    """Wall-clock duration of one execution; 0 when the interval is unusable."""
    try:
        delta = datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
        return max(int(delta.total_seconds() * 1000), 0)
    except Exception:
        return 0


class ExecutionCounters:
    def __init__(self, manager):
        self.manager = manager
        self.records: list[dict] = []
        self.task: asyncio.Task | None = None
        self.dropped = 0
        self.traces: dict[str, TraceState] = {}
        self.trace_deadlines: dict[str, float] = {}
        # Execution identity -> in-flight trace, for stages recorded by tasks
        # that no longer share the ingress context (plugin/RPC platform calls).
        self.registry: dict[str, TraceState] = {}
        self.registry_deadlines: dict[str, float] = {}
        self.dropped_traces = 0

    # ------------------------------------------------------------------ config

    def trace_mode(self) -> str:
        # Cloud activity counts must not be computed from sampled successes.
        # Telemetry opt-out is still enforced before recording observations.
        from ..utils import constants

        if constants.edition == 'cloud':
            return 'all'
        mode = str(self.manager.telemetry_config.get('execution_trace', DEFAULT_TRACE_MODE) or '').strip().lower()
        return mode if mode in TRACE_MODES else DEFAULT_TRACE_MODE

    def trace_sample(self) -> int:
        try:
            sample = int(self.manager.telemetry_config.get('execution_trace_sample', DEFAULT_TRACE_SAMPLE))
        except (TypeError, ValueError):
            sample = DEFAULT_TRACE_SAMPLE
        return sample if 1 <= sample <= 100000 else DEFAULT_TRACE_SAMPLE

    def flush_seconds(self) -> int:
        try:
            seconds = int(self.manager.telemetry_config.get('telemetry_flush_seconds', DEFAULT_FLUSH_SECONDS))
        except (TypeError, ValueError):
            seconds = DEFAULT_FLUSH_SECONDS
        return seconds if 1 <= seconds <= 86400 else DEFAULT_FLUSH_SECONDS

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
        error: str = '',
        execution_id: str | None = None,
        node: str = '',
    ):
        try:
            cfg = self.manager.telemetry_config
            if not cfg or cfg.get('disable_telemetry', False) or not cfg.get('url'):
                return
            if family not in {'platform_event', 'event_route', 'pipeline', 'runner', 'platform_api'}:
                return
            if mode not in MODES or outcome not in OUTCOMES:
                return
            # Only code-defined identifiers are accepted; never pass user values.
            if any(not isinstance(v, str) or len(v) > 160 for v in (operation, adapter, runner, node)):
                return
            state = trace_mod.current()
            if state is None:
                # Cross-task work has no inherited trace; resolve the owning
                # execution through the registry instead.
                lookup = str(execution_id or '').strip() or current_execution_id()
                if lookup:
                    state = self.registry.get(lookup)
            if state is None:
                # Every observation belongs to exactly one execution chain.
                return
            try:
                identity = workspace_identity(context)
            except Exception:
                # A cross-task caller may only carry the Workspace id; reuse the
                # identity already bound to the owning trace.
                identity = state.identity or {}
            if not identity.get('instance_id') or not identity.get('workspace_uuid'):
                return
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
                error=_bounded_error(error),
                node=node,
            )
            self._ensure_loop()
        except Exception:
            # Observability must never change execution behavior.
            return

    def _record_trace_stage(
        self,
        state: TraceState,
        *,
        identity,
        family,
        operation,
        mode,
        adapter,
        runner,
        outcome,
        synthetic,
        error: str = '',
        node: str = '',
    ) -> None:
        if state.abandoned:
            return
        if trace_mod.current() is state:
            # Recorded by the task that owns the step: its step stack is exact.
            # A step's own record sits under its enclosing step, never itself.
            parent = trace_mod.current_parent()
            if node and parent == node:
                parent = trace_mod.enclosing_parent()
        else:
            # A cross-task observation (plugin/RPC) cannot see the step
            # contextvar; attach it to the innermost step the owning task has
            # open on the trace.
            parent = state.open_nodes[-1] if state.open_nodes else ''
        if state.trace_id not in self.traces:
            # Never buffer traces this configuration would discard anyway.
            if self.trace_mode() == 'off' or len(self.traces) >= MAX_TRACES:
                self.dropped += 1
                state.abandoned = True
                self._unregister_state(state)
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
            error=error,
            node=node,
            parent=parent,
        )

    def _ensure_loop(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())

    # --------------------------------------------------------------- registry

    def register_trace(self, state: TraceState, execution_id) -> None:
        """Alias one more execution identity onto an in-flight trace."""
        try:
            exec_id = str(execution_id or '').strip()
            if not exec_id or state.abandoned:
                return
            if exec_id not in self.registry and len(self.registry) >= MAX_REGISTRY_KEYS:
                oldest = next(iter(self.registry))
                self.registry.pop(oldest, None)
                self.registry_deadlines.pop(oldest, None)
            self.registry[exec_id] = state
            self.registry_deadlines[exec_id] = time.monotonic() + TRACE_TTL_SECONDS
        except Exception:
            return

    def _unregister_state(self, state: TraceState) -> None:
        for exec_id in [key for key, value in self.registry.items() if value is state]:
            self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)

    def _sweep_registry(self, now: float) -> None:
        """Drop aliases whose owning execution never closed (leaked bindings)."""
        for exec_id in [key for key, deadline in self.registry_deadlines.items() if deadline <= now]:
            self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)

    # ------------------------------------------------------------------ traces

    def close_trace(self, state: TraceState, reason: str = 'event_done', error: str = '') -> None:
        """Buffer one complete execution record when it matches the sample."""
        try:
            if state.closed:
                return
            state.closed = True
            registered = self.traces.pop(state.trace_id, None) is not None
            self.trace_deadlines.pop(state.trace_id, None)
            self._unregister_state(state)
            if not registered and not state.failure_reason:
                return
            if (not state.stages and not state.failure_reason) or not self._trace_emitted(state):
                return
            record = self._build_record(state, reason, error)
            if record is not None:
                self._enqueue_record(record)
        except Exception:
            return

    def _enqueue_record(self, record: dict) -> None:
        if len(self.records) >= MAX_BUFFERED_RECORDS:
            self.records.pop(0)
            self.dropped += 1
        self.records.append(record)
        self._ensure_loop()

    def _trace_emitted(self, state: TraceState) -> bool:
        mode = self.trace_mode()
        if mode == 'off':
            return False
        # A chain that failed must always be uploaded, even when no stage was
        # recorded before it broke: the reason is the whole point of the trace.
        if state.failure_reason:
            return True
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

    def _build_record(self, state: TraceState, reason: str, error: str = '') -> dict | None:
        from ..utils import constants

        identity = state.identity
        if not identity.get('instance_id') or not identity.get('workspace_uuid'):
            return None
        ended_at = datetime.now(timezone.utc).isoformat()
        stages = state.stages
        observations = []
        for stage in stages:
            observation = {
                'seq': stage['seq'],
                'family': stage['family'],
                'operation': stage['operation'],
                'mode': stage['mode'],
                'adapter': stage['adapter'],
                'runner': stage['runner'],
                'outcome': stage['outcome'],
                'synthetic': stage['synthetic'],
                'error': stage['error'],
                'route_ref': stage['route_ref'],
                'run_id': stage['run_id'],
                'first_seen': stage['first_seen'],
                'last_seen': stage['last_seen'],
                'trace_id': state.trace_id,
            }
            # Workflow position is optional: records outside any step omit both
            # keys entirely, so their payloads stay byte-identical.
            if stage.get('node'):
                observation['node'] = stage['node']
            if stage.get('parent'):
                observation['parent'] = stage['parent']
            observations.append(observation)
        return {
            'event_type': 'feature_execution',
            # The execution identity: one record == one chain == one Space row.
            'query_id': state.trace_id,
            'instance_id': identity['instance_id'],
            'workspace_uuid': identity['workspace_uuid'],
            'version': constants.semantic_version,
            'edition': constants.edition,
            'timestamp': ended_at,
            'trusted': True,
            # First failure detail in this chain, so Space can show why it broke.
            'error': _bounded_error(error)
            or state.failure_reason
            or next((stage['error'] for stage in stages if stage['error']), ''),
            # Legacy-compatible columns Space already maps; best effort.
            'duration_ms': _duration_ms(state.started_at, ended_at),
            'model_name': state.model_name or '',
            'adapter': state.adapter or next((stage['adapter'] for stage in stages if stage['adapter']), ''),
            'runner': state.runner or next((stage['runner'] for stage in stages if stage['runner']), ''),
            'runner_category': state.runner_category or '',
            'pipeline_plugins': state.pipeline_plugins,
            'features': {
                'schema': 1,
                'observations': observations,
                'trace': {
                    'closed_by': reason,
                    'started_at': state.started_at,
                    'ended_at': ended_at,
                    'route_ref': next((stage['route_ref'] for stage in stages if stage['route_ref']), ''),
                    'run_id': next((stage['run_id'] for stage in stages if stage['run_id']), ''),
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
        interval = self.flush_seconds()
        last_flush = time.monotonic()
        while self.records or self.traces or self.registry:
            # Traces expire on a short TTL; records keep their own cadence.
            await asyncio.sleep(1 if (self.traces or self.registry) else interval)
            now = time.monotonic()
            self._sweep_traces(now)
            self._sweep_registry(now)
            if self.records and now - last_flush >= interval:
                last_flush = now
                await self.flush()
        self.task = None

    async def flush(self):
        if not self.records:
            return
        batch: list[dict] = []
        size = 0
        while self.records and len(batch) < MAX_RECORDS_PER_FLUSH:
            encoded = len(json.dumps(self.records[0], ensure_ascii=False, default=str))
            if batch and size + encoded > MAX_FLUSH_BYTES:
                break
            batch.append(self.records.pop(0))
            size += encoded
        if not batch:
            return
        payload = {'records': batch}
        if not await self.manager.send(payload):
            await asyncio.sleep(1)
            await self.manager.send(payload)

    async def shutdown(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        try:
            deadline = time.monotonic() + 5
            while self.records and time.monotonic() < deadline:
                remaining = len(self.records)
                await asyncio.wait_for(self.flush(), timeout=2)
                if len(self.records) >= remaining:
                    break
        except (Exception, asyncio.CancelledError):
            pass
        self.records.clear()
        # Executions still in flight cannot be completed during shutdown.
        self.dropped += len(self.traces)
        self.dropped_traces += len(self.traces)
        self.traces.clear()
        self.trace_deadlines.clear()
        self.registry.clear()
        self.registry_deadlines.clear()


def _execution_counters(ap):
    counters = getattr(getattr(ap, 'telemetry', None), 'execution', None)
    return counters if isinstance(counters, ExecutionCounters) else None


def record(ap, context, **observation):
    """Best-effort bridge usable with optional telemetry and test doubles."""
    try:
        counters = _execution_counters(ap)
        if counters is not None:
            counters.record(context, **observation)
    except Exception:
        pass


def close_trace(ap, state, reason: str = 'event_done', error: str = '') -> None:
    """Best-effort trace close usable with optional telemetry and test doubles."""
    try:
        counters = _execution_counters(ap)
        if counters is not None:
            counters.close_trace(state, reason, error)
    except Exception:
        pass


def bind_trace(ap, execution_id: str | None = None) -> trace_mod.TraceBinding:
    """Bind an execution trace and alias its identity for cross-task stages."""
    binding = trace_mod.bind(execution_id)
    if execution_id:
        try:
            counters = _execution_counters(ap)
            if counters is not None:
                counters.register_trace(binding.state, execution_id)
        except Exception:
            pass
    return binding


@contextlib.contextmanager
def ingress(ap, reason: str = 'event_done', context=None, execution_id: str | None = None):
    """Trace one execution boundary; only the owner of the trace closes it.

    Nested boundaries (an event routed into a Pipeline, a Runner invoked from a
    dispatch) reuse the in-flight trace instead of starting a second one, and
    only alias their own execution id onto it.
    """
    binding = trace_mod.bind(execution_id)
    if binding.created and context is not None:
        try:
            binding.state.identity = workspace_identity(context)
        except Exception:
            pass
    if execution_id and not binding.state.abandoned:
        try:
            counters = _execution_counters(ap)
            if counters is not None:
                counters.register_trace(binding.state, execution_id)
        except Exception:
            pass
    failure = ''
    try:
        yield binding
    except BaseException as exc:
        # The boundary itself failed: keep the reason on the trace so the uploaded
        # payload explains the failure instead of reporting a bare outcome.
        if binding.created:
            failure = f'{type(exc).__name__}: {exc}'
            binding.state.mark_failure(failure)
        raise
    finally:
        if trace_mod.unbind_root(binding):
            close_trace(ap, binding.state, reason, failure)
