"""Point-wise execution records for the existing telemetry sender.

One execution is reported as a chain of independent records that all carry the
same ``event_id``: one ``execution_node`` per workflow node, emitted the moment
that node completes, plus exactly one ``execution_chain`` emitted when the
execution closes. The sender never assembles a trace locally, so there is no
per-trace buffer, no TTL and no per-process trace cap; memory is bounded by the
outbound record buffer, the flush batch size and the small cross-task registry.

Platform events are reportable only after a business route, matching plugin
subscription or validated interaction callback admits the execution. Pending
events enqueue neither nodes nor closures, even on failure or in Cloud mode.
Independent API/WebUI executions remain eligible without a Bot route.

An inbound event is one chain even when its work crosses tasks: a routed
message is queued and later run by a query-pool task. ``handoff`` keeps the
chain open and carries its identity and the handing step in the query
variables; the Pipeline lane ``resume``s the same chain (same sequence, nested
under the route step) and releases it. The chain closes when the ingress
boundary exited and every handoff was released: ``completed`` normally,
``merged`` when aggregation folded the event into another query, ``timeout``
when a handoff never reported back before its registry alias expired.

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
import traceback
import zlib
from datetime import datetime, timezone

from . import trace as trace_mod
from .features import bounded_model_name
from .identity import workspace_identity
from .resources import snapshot as resources_snapshot
from .resources import begin as resources_begin
from .resources import end as resources_end
from .resources import attach as resources_attach
from .resources import detach as resources_detach
from .trace import TraceState

MODES = frozenset({'pipeline', 'agent', 'event_processor', 'none'})
OUTCOMES = frozenset({'success', 'failed', 'cancelled', 'timeout', 'skipped', 'unknown'})
FAMILIES = frozenset({'platform_event', 'event_route', 'pipeline', 'runner', 'platform_api', 'tool'})
ORIGINS = frozenset({'platform', 'webui', 'api'})
# Why a chain closed: ``completed`` once the ingress boundary and every task it
# handed work to finished, ``merged`` when message aggregation folded the event
# into another execution, ``timeout`` when handed-off work never reported back.
CLOSED_BY = frozenset({'completed', 'merged', 'timeout'})
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
MAX_REGISTRY_KEYS = 1024
# Long enough for a slow Agent run; a handoff that never reports back is closed
# as ``timeout`` when its alias expires.
REGISTRY_TTL_SECONDS = 1800

# Failure details are operator-facing and must be complete enough to debug a
# broken execution: the exception class, its message, the cause chain and the
# tail of the traceback survive. Secrets are redacted and the text is capped
# below Space's 4096 character bound.
ERROR_LIMIT = 4000
TRACEBACK_FRAMES = 8
CAUSE_DEPTH = 5
_REDACTIONS = (
    (re.compile(r'\bsk-[A-Za-z0-9_\-]{8,}'), 'sk-***'),
    (re.compile(r'(?i)(\bbearer\s+)[A-Za-z0-9._~+/=\-]{8,}'), r'\1***'),
    (
        re.compile(
            r'(?i)((?:api[_-]?key|access[_-]?key|secret|token|password|passwd|authorization)'
            r'["\']?\s*[:=]\s*["\']?)[^\s"\'&,;]{4,}'
        ),
        r'\1***',
    ),
    (
        re.compile(r'(?i)([?&](?:key|api_key|apikey|token|access_token|sig|signature|secret|password)=)[^&\s]+'),
        r'\1***',
    ),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+'), '***@***'),
)

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


def _redact(text: str) -> str:
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def redact_text(text: str) -> str:
    """Redact credential-like values and email addresses from free text."""

    return _redact(text)


def _bounded_error(value, limit: int = ERROR_LIMIT) -> str:
    """Bound and redact one failure detail before it leaves the process.

    Line breaks survive so a traceback stays readable; other control
    characters are stripped, credentials are redacted and the result is capped.
    """
    if value is None:
        return ''
    if isinstance(value, BaseException):
        value = describe_exception(value)
    lines = []
    for line in str(value).splitlines():
        cleaned = ''.join(ch if ch.isprintable() else ' ' for ch in line).rstrip()
        if cleaned.strip():
            lines.append(cleaned)
    text = _redact('\n'.join(lines)).strip()
    if len(text) > limit:
        # Keep both ends: the head names the failure, the tail holds the
        # innermost traceback frames.
        marker = '\n...\n'
        head = limit // 3
        text = text[:head] + marker + text[-(limit - head - len(marker)) :]
    return text


def _short_frame_path(filename: str) -> str:
    normalized = str(filename or '').replace('\\', '/')
    for marker in ('/site-packages/', '/src/'):
        if marker in normalized:
            return normalized.split(marker, 1)[1]
    return normalized.rsplit('/', 3)[-1] if normalized.count('/') > 3 else normalized


def describe_exception(exc: BaseException) -> str:
    """Full operator-facing description: class, message, causes, traceback tail."""
    try:
        parts: list[str] = []
        seen: set[int] = set()
        current: BaseException | None = exc
        depth = 0
        while current is not None and id(current) not in seen and depth < CAUSE_DEPTH:
            seen.add(id(current))
            message = str(current)
            line = f'{type(current).__name__}: {message}' if message else type(current).__name__
            parts.append(line if depth == 0 else f'Caused by: {line}')
            if current.__cause__ is not None:
                current = current.__cause__
            elif not current.__suppress_context__:
                current = current.__context__
            else:
                current = None
            depth += 1
        frames = traceback.extract_tb(exc.__traceback__)[-TRACEBACK_FRAMES:] if exc.__traceback__ else []
        if frames:
            parts.append('Traceback (most recent call last):')
            for frame in frames:
                parts.append(f'  {_short_frame_path(frame.filename)}:{frame.lineno} in {frame.name}')
        return '\n'.join(parts)
    except Exception:
        return type(exc).__name__


def is_cancellation(exc: BaseException | None) -> bool:
    """A cancelled task or a closed generator stopped the work; nothing broke."""
    return isinstance(exc, (asyncio.CancelledError, GeneratorExit))


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
            if not self._enabled() or trace_mod.reporting_suppressed():
                return
            if family not in FAMILIES or mode not in MODES or outcome not in OUTCOMES:
                return
            # Only code-defined identifiers are accepted; never pass user values.
            if any(not isinstance(v, str) or len(v.encode('utf-8')) > 512 for v in (operation, adapter, runner, node)):
                return
            state = trace_mod.current()
            if state is None:
                # Cross-task work has no inherited context; resolve the owning
                # execution through the registry. It owns no step here, so the
                # record attaches to the innermost step the chain has open -
                # the step that caused this work.
                lookup = str(execution_id or '').strip() or current_execution_id()
                if lookup:
                    state = self._resolve(lookup)
            if state is None or state.closed or not state.reportable:
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
                evicted = self.registry.pop(oldest, None)
                self.registry_deadlines.pop(oldest, None)
                self._expire_state(evicted)
            self.registry[exec_id] = state
            self.registry_deadlines[exec_id] = now + REGISTRY_TTL_SECONDS
        except Exception:
            return

    def _resolve(self, execution_id: str) -> TraceState | None:
        now = time.monotonic()
        self._sweep_registry(now)
        state = self.registry.get(execution_id)
        if state is not None:
            # Activity keeps a long-running execution's aliases alive.
            self.registry_deadlines[execution_id] = now + REGISTRY_TTL_SECONDS
        return state

    def _unregister_state(self, state: TraceState) -> None:
        for exec_id in [key for key, value in self.registry.items() if value is state]:
            self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)

    def _sweep_registry(self, now: float) -> None:
        """Drop aliases whose owning execution never closed (leaked bindings)."""
        for exec_id in [key for key, deadline in self.registry_deadlines.items() if deadline <= now]:
            state = self.registry.pop(exec_id, None)
            self.registry_deadlines.pop(exec_id, None)
            self._expire_state(state)

    def _expire_state(self, state: TraceState | None) -> None:
        """Close a chain whose handed-off work never reported back."""
        if state is None or state.closed or not state.root_exited or state.pending <= 0:
            return
        if any(value is state for value in self.registry.values()):
            return
        state.pending = 0
        self.close_trace(state, 'timeout')

    # --------------------------------------------------------------- handoffs

    def handoff(self, state: TraceState) -> None:
        """Keep the chain open until one more downstream task releases it."""
        state.pending += 1
        self.register_trace(state, state.event_id)

    def release(
        self,
        state: TraceState,
        *,
        error: str = '',
        merged_into: str | None = None,
        cancelled: bool = False,
    ) -> None:
        """Release one handoff; close the chain once nothing is outstanding."""
        try:
            if state.closed:
                return
            if cancelled:
                state.mark_cancelled()
            elif error:
                state.mark_failure(_bounded_error(error))
            if merged_into is not None:
                state.merged_into = str(merged_into)[:1024]
                state.close_reason = 'merged'
            state.pending = max(state.pending - 1, 0)
            if state.pending == 0 and state.root_exited:
                self.close_trace(state, state.close_reason or 'completed')
        except Exception:
            return

    # ------------------------------------------------------------------ chains

    def close_trace(self, state: TraceState, reason: str = 'completed', error: str = '') -> None:
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
        if not state.reportable or state.mode == 'off':
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
            'closed_by': reason if reason in CLOSED_BY else 'completed',
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
            'model_name': bounded_model_name(state.model_name or ''),
            'adapter': state.adapter or state.node_adapter,
            'runner': state.runner or state.node_runner,
            'runner_category': state.runner_category or '',
            'pipeline_plugins': state.pipeline_plugins,
        }
        if state.merged_into:
            record['merged_into'] = state.merged_into
        if state.features:
            record['features'] = {
                key: dict(value) if isinstance(value, dict) else value for key, value in state.features.items()
            }
        # Bound resources of this execution, when any lane reported them. The
        # key is omitted entirely when nothing was noted, so the payload stays
        # byte-identical for executions with no bindings.
        resources = resources_snapshot(state.resources) if state.resources is not None else resources_snapshot()
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
        # One request carries one Workspace's records so Space can attribute
        # the whole batch to that Workspace's authenticated reporter.
        workspace = str(self.records[0].get('workspace_uuid') or '')
        for record in self.records:
            if len(batch) >= MAX_RECORDS_PER_FLUSH:
                break
            if str(record.get('workspace_uuid') or '') != workspace:
                break
            encoded = len(json.dumps(record, ensure_ascii=False, default=str))
            if batch and size + encoded > MAX_FLUSH_BYTES:
                break
            batch.append(record)
            size += encoded
        if not batch:
            return True
        payload = {'records': batch, 'workspace_uuid': workspace}
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


def close_trace(ap, state, reason: str = 'completed', error: str = '') -> None:
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
        binding.state.resources = resources_begin()
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
    reason: str = 'completed',
    context=None,
    execution_id: str | None = None,
    *,
    debug: bool = False,
    origin: str = 'platform',
    synthetic_event: str = '',
    require_route: bool = False,
):
    """Open one execution boundary; only the owner of the chain closes it.

    ``require_route`` starts a platform event without reporting permission;
    dispatch calls ``trace.admit`` when a delivery matches. Nested entrypoints
    must reuse that decision instead of implicitly admitting the parent.

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
        if require_route:
            state.reportable = False
        state.resources = resources_begin()
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
            operation=str(synthetic_event)[:512],
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
            failure = _bounded_error(exc)
            if is_cancellation(exc):
                # Cancelled work (a stopped run, a superseding message, an
                # instance shutdown) closes as ``cancelled``, never ``failed``.
                state.mark_cancelled()
            else:
                state.mark_failure(failure)
        raise
    finally:
        if scope is not None:
            scope.__exit__(None, None, None)
        if trace_mod.unbind_root(binding):
            if state.pending > 0 and not state.closed:
                # Work handed to another task (a queued Pipeline query) still
                # belongs to this execution; the last release closes the chain.
                state.root_exited = True
            else:
                close_trace(ap, state, reason, failure)


# ---------------------------------------------------------------- handoffs


HANDOFF_EVENT_KEY = '_ingress_event_id'
HANDOFF_PARENT_KEY = '_ingress_parent'
HANDOFF_SUPPRESSED_KEY = '_telemetry_suppressed'
# Marks a handoff as settled (resumed or released) so it is released once.
HANDOFF_SETTLED_KEY = '_telemetry_handoff_settled'


def _claim_handoff(variables) -> str:
    """Return the handoff event id and mark it settled; '' when none is open."""
    if not isinstance(variables, dict) or variables.get(HANDOFF_SETTLED_KEY):
        return ''
    event_id = str(variables.get(HANDOFF_EVENT_KEY) or '')
    if event_id:
        variables[HANDOFF_SETTLED_KEY] = True
    return event_id


def handoff(ap) -> dict:
    """Hand the in-flight execution to a queued task; returns query variables.

    The returned keys travel with the queued query. The Pipeline lane resumes
    the same chain through :func:`resume` and releases the handoff when it
    finishes, so one inbound event is reported as exactly one chain no matter
    how many tasks it crosses.
    """
    try:
        state = trace_mod.current()
        if state is None or state.closed:
            return {}
        if trace_mod.reporting_suppressed():
            return {HANDOFF_SUPPRESSED_KEY: True}
        variables: dict = {HANDOFF_EVENT_KEY: state.event_id}
        stack = trace_mod.node_stack()
        if stack:
            frame = stack[-1]
            variables[HANDOFF_PARENT_KEY] = [frame.node_id, frame.seq, frame.started_at]
        counters = _execution_counters(ap)
        if counters is not None:
            counters.handoff(state)
        return variables
    except Exception:
        return {}


def release_handoff(ap, variables, *, error: str = '', merged_into: str | None = None) -> None:
    """Release a handoff whose queued task will never run (dropped or merged).

    Idempotent: a handoff already resumed by the Pipeline lane or released
    earlier is left alone.
    """
    try:
        event_id = _claim_handoff(variables)
        counters = _execution_counters(ap)
        if not event_id or counters is None:
            return
        state = counters._resolve(event_id)
        if state is not None:
            counters.release(state, error=error, merged_into=merged_into)
    except Exception:
        pass


@contextlib.contextmanager
def resume(ap, variables):
    """Continue a handed-off chain in this task; yields the state or None."""
    counters = _execution_counters(ap)
    event_id = _claim_handoff(variables)
    state = counters._resolve(event_id) if counters is not None and event_id else None
    if state is None or state.closed:
        yield None
        return
    parent = None
    raw_parent = variables.get(HANDOFF_PARENT_KEY)
    if isinstance(raw_parent, (list, tuple)) and len(raw_parent) == 3:
        try:
            parent = trace_mod.NodeFrame(str(raw_parent[0]), int(raw_parent[1]), str(raw_parent[2]))
        except (TypeError, ValueError):
            parent = None
    resources_token = resources_attach(state.resources)
    failure = ''
    cancelled = False
    try:
        with trace_mod.adopt(state, parent):
            yield state
    except BaseException as exc:
        failure = _bounded_error(exc)
        cancelled = is_cancellation(exc)
        raise
    finally:
        resources_detach(resources_token)
        counters.release(state, error=failure, cancelled=cancelled)
