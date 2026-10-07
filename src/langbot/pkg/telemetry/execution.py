"""Point-wise execution records for the existing telemetry sender.

One execution is reported as a chain of independent records that all carry the
same ``event_id``: one ``execution_node`` per workflow node, emitted the moment
that node completes, plus exactly one ``execution_chain`` emitted when the
execution closes. The sender never assembles a trace locally, so there is no
per-trace buffer, no TTL and no per-process trace cap; memory is bounded by the
outbound record buffer, the flush batch size and the small cross-task registry.

Sampling is decided exactly once per event, at ingress, from a stable hash of
the execution identity, so every record of one execution carries the same
decision. A chain that broke is always emitted even when sampling excluded it,
which is why a chain may arrive with zero or partial nodes.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import json
import re
import time
import zlib
from datetime import datetime, timezone

from . import trace as trace_mod
from .identity import workspace_identity
from .resources import snapshot as resources_snapshot
from .resources import begin as resources_begin
from .resources import end as resources_end
from .trace import TraceState

MODES = frozenset({'pipeline', 'agent', 'event_processor', 'none'})
OUTCOMES = frozenset({'success', 'failed', 'cancelled', 'timeout', 'skipped', 'unknown'})
FAMILIES = frozenset({'platform_event', 'event_route', 'pipeline', 'runner', 'platform_api'})
ORIGINS = frozenset({'platform', 'webui', 'api'})
CLOSED_BY = frozenset({'event_done', 'pipeline_done', 'runner_done', 'timeout'})
CHAIN_FAILURES = frozenset({'failed', 'cancelled', 'timeout'})

SCHEMA = 2
TRACE_MODES = frozenset({'off', 'failures', 'sampled', 'all'})
DEFAULT_TRACE_MODE = 'all'
DEFAULT_TRACE_SAMPLE = 20

# Sampling bounds: outbound record buffer, one flush batch, flush cadence.
MAX_BUFFERED_RECORDS = 512
MAX_RECORDS_PER_FLUSH = 128
MAX_FLUSH_BYTES = 200 * 1024
DEFAULT_FLUSH_SECONDS = 180
MAX_FLUSH_ATTEMPTS = 3
FLUSH_RETRY_BACKOFF_SECONDS = 0.2

# Cross-task registry: execution id -> owning execution, bounded and time-limited.
MAX_REGISTRY_KEYS = 256
REGISTRY_TTL_SECONDS = 300

# Failure details are operator-facing: keep the failure class and a short
# machine-ish prefix, never the free text a user or a model produced.
ERROR_LIMIT = 200
ERROR_PREFIX_CHARS = 120
ERROR_PREFIX_TOKENS = 12
_ERROR_CLASS = re.compile(r'[A-Za-z_][\w.]*')

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


def _short_prefix(text: str) -> str:
    """Keep at most a short machine-ish prefix of one failure message."""
    if len(text) > ERROR_PREFIX_CHARS:
        text = text[:ERROR_PREFIX_CHARS]
    parts = text.split(' ')
    if len(parts) > ERROR_PREFIX_TOKENS:
        text = ' '.join(parts[:ERROR_PREFIX_TOKENS])
    return text


def _bounded_error(value, limit: int = ERROR_LIMIT) -> str:
    """Bound and redact one failure detail before it leaves the process.

    The failure class and a short machine-ish prefix survive; control characters
    are stripped, whitespace is collapsed and the result is capped, so a noisy
    failure cannot smuggle user or model content into the payload.
    """
    if value is None:
        return ''
    text = ''.join(ch if ch.isprintable() else ' ' for ch in str(value))
    text = ' '.join(text.split())
    if not text:
        return ''
    head, separator, rest = text.partition(':')
    head = head.strip()
    if separator and len(head) <= 80 and _ERROR_CLASS.fullmatch(head):
        prefix = _short_prefix(rest.strip())
        text = f'{head}: {prefix}' if prefix else head
    else:
        text = _short_prefix(text)
    return text[:limit]


def _duration_ms(started_at: str, ended_at: str) -> int:
    """Wall-clock duration of one execution; 0 when the interval is unusable."""
    try:
        delta = datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)
        return max(int(delta.total_seconds() * 1000), 0)
    except Exception:
        return 0


class ExecutionCounters:
    """Point-wise execution reporting: one record per node, one per closure."""

    def __init__(self, manager):
        self.manager = manager
        self.records: list[dict] = []
        self.task: asyncio.Task | None = None
        # Exposed health: records dropped or accepted by the sender.
        self.dropped = 0
        self.sent = 0
        # Execution identity -> owning execution, for nodes recorded by tasks
        # that no longer share the ingress context (plugin/RPC platform calls).
        # It resolves identity and the sampling decision only; node payloads are
        # never accumulated here.
        self.registry: dict[str, TraceState] = {}
        self.registry_deadlines: dict[str, float] = {}

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

    def health(self) -> dict:
        """Real telemetry health for the instance liveness snapshot."""
        return {
            'records_buffered': len(self.records),
            'records_sent': self.sent,
            'records_dropped': self.dropped,
            'executions_in_flight': len({id(state) for state in self.registry.values()}),
        }

    # ----------------------------------------------------------------- sampling

    def _sampling_decision(self, event_id: str) -> tuple[str, int, bool]:
        """Decide once, deterministically, whether this event is reported.

        The identity is hashed instead of being parsed, so every id shape
        (``platform:...``, uuids, debug ids) samples the same way.
        """
        mode = self.trace_mode()
        if mode == 'sampled':
            denominator = self.trace_sample()
            try:
                sampled_in = zlib.crc32(str(event_id).encode('utf-8')) % denominator == 0
            except Exception:
                sampled_in = False
            return mode, denominator, sampled_in
        # 'off' reports nothing, 'failures' keeps nodes out but still reports a
        # broken chain, 'all' reports everything; denominator is 1 for all three.
        return mode, 1, mode == 'all'

    def configure(
        self,
        state: TraceState,
        context=None,
        *,
        debug: bool = False,
        origin: str = 'platform',
        identity=None,
    ) -> None:
        """Bind the execution identity, the sampling decision and the flags."""
        if state.configured:
            return
        state.configured = True
        state.debug = bool(debug)
        state.origin = origin if origin in ORIGINS else 'platform'
        mode, denominator, sampled_in = self._sampling_decision(state.event_id)
        state.mode = mode
        state.denominator = denominator
        # Debug chains are always emitted (unless reporting is off entirely).
        state.emit_nodes = mode != 'off' and (state.debug or sampled_in)
        if identity is not None:
            state.identity = dict(identity)
        elif context is not None:
            try:
                state.identity = workspace_identity(context)
            except Exception:
                pass

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
            if not self._enabled():
                return
            if family not in FAMILIES or mode not in MODES or outcome not in OUTCOMES:
                return
            # Only code-defined identifiers are accepted; never pass user values.
            if any(not isinstance(v, str) or len(v) > 160 for v in (operation, adapter, runner, node)):
                return
            state = trace_mod.current()
            if state is None:
                # Cross-task work has no inherited context; resolve the owning
                # execution through the registry. It has no open step here, so
                # its node becomes a root of that execution instead of being
                # mirrored from another task's stack.
                lookup = str(execution_id or '').strip() or current_execution_id()
                if lookup:
                    state = self._resolve(lookup)
            if state is None or state.closed:
                # Every observation belongs to exactly one execution chain.
                return
            self.configure(state)
            try:
                identity = workspace_identity(context)
            except Exception:
                # A cross-task caller may only carry the Workspace id; reuse the
                # identity already bound to the owning execution.
                identity = state.identity or {}
            if not identity.get('instance_id') or not identity.get('workspace_uuid'):
                return
            state.identity = identity

            ended_at = datetime.now(timezone.utc).isoformat()
            node_id, seq, started_at, parent = trace_mod.resolve_node(state, str(node or ''), ended_at)
            root = parent == '' and not state.root_seen
            if root:
                state.root_seen = True
            bounded_error = _bounded_error(error)
            state.note_node(outcome=outcome, adapter=adapter, runner=runner, family=family, error=bounded_error)
            if not state.emit_nodes:
                # Sampling excluded this execution: the node is never buffered,
                # only counted so the terminal chain can explain the gap.
                state.dropped_nodes += 1
                return
            self._enqueue_record(
                {
                    'event_type': 'execution_node',
                    'schema': SCHEMA,
                    **self._common_fields(state, ended_at),
                    'node_id': node_id,
                    'parent_node_id': parent,
                    'root': root,
                    'seq': seq,
                    'family': family,
                    'operation': operation,
                    'mode': mode,
                    'adapter': adapter,
                    'runner': runner,
                    'outcome': outcome,
                    'error': bounded_error,
                    'route_ref': trace_mod.current_route(),
                    'run_id': trace_mod.current_run(),
                    'synthetic': bool(synthetic),
                    'started_at': started_at,
                    'ended_at': ended_at,
                }
            )
        except Exception:
            # Observability must never change execution behavior.
            return

    def _common_fields(self, state: TraceState, timestamp: str) -> dict:
        identity = state.identity
        from ..utils import constants

        return {
            'event_id': state.event_id,
            'instance_id': identity['instance_id'],
            'workspace_uuid': identity['workspace_uuid'],
            'version': constants.semantic_version,
            'edition': constants.edition,
            'timestamp': timestamp,
            'debug': bool(state.debug),
            'sample': {'mode': state.mode, 'denominator': state.denominator},
        }

    def _enabled(self) -> bool:
        try:
            cfg = self.manager.telemetry_config
        except Exception:
            return False
        return bool(cfg) and not cfg.get('disable_telemetry', False) and bool(cfg.get('url'))

    def _ensure_loop(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop())

    # --------------------------------------------------------------- registry

    def register_trace(self, state: TraceState, execution_id) -> None:
        """Alias one more execution identity onto an in-flight execution."""
        try:
            exec_id = str(execution_id or '').strip()
            if not exec_id:
                return
            self.configure(state)
            now = time.monotonic()
            self._sweep_registry(now)
            if exec_id not in self.registry and len(self.registry) >= MAX_REGISTRY_KEYS:
                oldest = next(iter(self.registry))
                self.registry.pop(oldest, None)
                self.registry_deadlines.pop(oldest, None)
            self.registry[exec_id] = state
            self.registry_deadlines[exec_id] = now + REGISTRY_TTL_SECONDS
        except Exception:
            return

    def _resolve(self, execution_id: str) -> TraceState | None:
        self._sweep_registry(time.monotonic())
        return self.registry.get(execution_id)

    def _unregister_state(self, state: TraceState) -> None:
        for exec_id in [key for key, value in self.registry.items() if value is state]:
            self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)

    def _sweep_registry(self, now: float) -> None:
        """Drop aliases whose owning execution never closed (leaked bindings)."""
        for exec_id in [key for key, deadline in self.registry_deadlines.items() if deadline <= now]:
            self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)

    # ------------------------------------------------------------------ chains

    def close_trace(self, state: TraceState, reason: str = 'event_done', error: str = '') -> None:
        """Emit the one terminal ``execution_chain`` record of this execution."""
        try:
            if state.closed:
                return
            state.closed = True
            self._unregister_state(state)
            if not self._enabled():
                # Nothing can be uploaded; never grow the buffer for a record
                # the sender would refuse to send.
                return
            self.configure(state)
            if not self._chain_emitted(state):
                return
            self._enqueue_record(self._build_chain_record(state, reason, error))
        except Exception:
            return
        finally:
            # The snapshot was read while building the chain record; stop
            # collecting so a late sibling task cannot leak into the next chain.
            resources_end()

    def _chain_emitted(self, state: TraceState) -> bool:
        if state.mode == 'off':
            return False
        if state.emit_nodes or state.debug:
            return True
        # A chain that broke is always uploaded, even when sampling excluded it.
        return bool(state.failure_reason) or state.outcome() in CHAIN_FAILURES

    def _build_chain_record(self, state: TraceState, reason: str, error: str = '') -> dict:
        ended_at = datetime.now(timezone.utc).isoformat()
        record = {
            'event_type': 'execution_chain',
            'schema': SCHEMA,
            **self._common_fields(state, ended_at),
            'closed_by': reason if reason in CLOSED_BY else 'event_done',
            'outcome': state.outcome(),
            # First failure detail in this chain, so Space can show why it broke.
            'error': _bounded_error(error)
            or _bounded_error(state.failure_reason)
            or _bounded_error(state.first_error)
            or '',
            'duration_ms': _duration_ms(state.started_at, ended_at),
            'stage_count': state.stage_count,
            'dropped_nodes': state.dropped_nodes,
            'origin': state.origin,
            'model_name': state.model_name or '',
            'adapter': state.adapter or state.node_adapter,
            'runner': state.runner or state.node_runner,
            'runner_category': state.runner_category or '',
            'pipeline_plugins': state.pipeline_plugins,
        }
        # Bound resources of this execution, when any lane reported them. The
        # key is omitted entirely when nothing was noted, so the payload stays
        # byte-identical for executions with no bindings.
        resources = resources_snapshot()
        if resources:
            record['resources'] = resources
        return record

    def _enqueue_record(self, record: dict) -> None:
        if len(self.records) >= MAX_BUFFERED_RECORDS:
            self.records.pop(0)
            self.dropped += 1
        self.records.append(record)
        self._ensure_loop()

    # ----------------------------------------------------------------- flushing

    async def _loop(self):
        interval = self.flush_seconds()
        try:
            # The outbound loop exists only to flush the record buffer.
            while self.records:
                await asyncio.sleep(interval)
                await self.flush()
        finally:
            self.task = None

    async def flush(self) -> bool:
        """Upload the buffered prefix; records stay buffered until accepted."""
        if not self.records:
            return True
        batch: list[dict] = []
        size = 0
        for record in self.records:
            if len(batch) >= MAX_RECORDS_PER_FLUSH:
                break
            encoded = len(json.dumps(record, ensure_ascii=False, default=str))
            if batch and size + encoded > MAX_FLUSH_BYTES:
                break
            batch.append(record)
            size += encoded
        if not batch:
            return True
        payload = {'records': batch}
        for attempt in range(MAX_FLUSH_ATTEMPTS):
            try:
                if await self.manager.send(payload):
                    # Peek-then-send: nothing is removed until the sender
                    # accepted the exact batch it was given.
                    del self.records[: len(batch)]
                    self.sent += len(batch)
                    return True
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            if attempt + 1 < MAX_FLUSH_ATTEMPTS:
                await asyncio.sleep(FLUSH_RETRY_BACKOFF_SECONDS * (2**attempt))
        # The batch stays buffered for the next cycle; a permanently unaccepted
        # record is dropped by the buffer bound above and counted there.
        return False

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
        self.dropped += len(self.records)
        self.records.clear()
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
    """Best-effort chain close usable with optional telemetry and test doubles."""
    try:
        counters = _execution_counters(ap)
        if counters is not None:
            counters.close_trace(state, reason, error)
    except Exception:
        pass


def bind_trace(ap, execution_id: str | None = None) -> trace_mod.TraceBinding:
    """Bind an execution and alias its identity for cross-task nodes."""
    binding = trace_mod.bind(execution_id)
    if binding.created:
        resources_begin()
    if execution_id:
        try:
            counters = _execution_counters(ap)
            if counters is not None:
                counters.register_trace(binding.state, execution_id)
        except Exception:
            pass
    return binding


@contextlib.contextmanager
def ingress(
    ap,
    reason: str = 'event_done',
    context=None,
    execution_id: str | None = None,
    *,
    debug: bool = False,
    origin: str = 'platform',
    synthetic_event: str = '',
):
    """Open one execution boundary; only the owner of the chain closes it.

    Nested boundaries (an event routed into a Pipeline, a Runner invoked from a
    dispatch) reuse the in-flight chain instead of starting a second one, and
    only alias their own execution id onto it. ``debug``/``origin`` apply when
    this boundary starts the chain: a WebUI/API run without a real platform
    event synthesizes its virtual inbound event here, so the chain has a real
    identity and a node for the event it stands for.
    """
    binding = trace_mod.bind(execution_id)
    state = binding.state
    if binding.created:
        resources_begin()
    counters = _execution_counters(ap)
    if counters is not None:
        if binding.created:
            counters.configure(state, context, debug=debug, origin=origin)
        if execution_id:
            counters.register_trace(state, execution_id)
    scope = None
    if binding.created and synthetic_event:
        scope = trace_mod.stage_scope()
        node = scope.__enter__()
        record(
            ap,
            context,
            family='platform_event',
            operation=str(synthetic_event)[:160],
            outcome='success',
            synthetic=True,
            node=node,
        )
    failure = ''
    try:
        yield binding
    except BaseException as exc:
        # The boundary itself failed: keep the reason on the chain so the
        # uploaded payload explains the failure instead of reporting a bare
        # outcome, even when sampling had excluded this execution.
        if binding.created:
            failure = f'{type(exc).__name__}: {exc}'
            state.mark_failure(failure)
        raise
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)
        if trace_mod.unbind_root(binding):
            close_trace(ap, state, reason, failure)
