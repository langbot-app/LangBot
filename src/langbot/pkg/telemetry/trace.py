"""Per-execution telemetry context for the v2 execution chain.

One execution identity (a Pipeline query, inbound platform event or Agent run)
is one chain. The chain is not assembled here: every workflow node is emitted
by ``telemetry.execution`` the moment it completes, carrying its own identity
and the identity of the execution it belongs to. This module only holds the
small execution-scoped context the emitter needs:

* the execution state (identity, the once-per-event sampling decision, the
  execution-scoped display fields);
* the routing/run identity pinned around the block that produced a node;
* the open-step stack, which lives in a ContextVar holding *one task's own
  immutable tuple*. Child tasks inherit a snapshot at creation; no shared
  mutable stack exists, so sibling tasks can never corrupt each other's parent
  links.

Cross-task callers (plugin/RPC work with no inherited context) resolve their
execution through the owner's execution-id registry instead, which only
carries the execution state - never node payloads. Such a caller owns no step
of its own, yet its work is still caused by a step of the chain: the sandbox
tool a Runner invoked, the platform API a plugin called back over RPC. The
execution state therefore also keeps the ordered set of steps any task
currently has open, and a record emitted with no open step of its own attaches
to the innermost one of those instead of becoming a root of the chain.
"""

from __future__ import annotations

import contextlib
import contextvars
import typing
from datetime import datetime, timezone
from uuid import uuid4

_current: contextvars.ContextVar['TraceState | None'] = contextvars.ContextVar('telemetry_trace', default=None)
_route: contextvars.ContextVar[str] = contextvars.ContextVar('telemetry_trace_route', default='')
_run: contextvars.ContextVar[str] = contextvars.ContextVar('telemetry_trace_run', default='')
_reporting_suppressed: contextvars.ContextVar[bool] = contextvars.ContextVar(
    'telemetry_reporting_suppressed', default=False
)
# Open workflow step frames of the current task, innermost last. The tuple is
# never mutated in place: opening a step publishes a new tuple on this task's
# context only, and closing it restores the previous one.
_node: contextvars.ContextVar[tuple['NodeFrame', ...]] = contextvars.ContextVar('telemetry_trace_node', default=())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeFrame(typing.NamedTuple):
    """One workflow step open in the task that opened it."""

    node_id: str
    seq: int
    started_at: str


class TraceState:
    """The small per-execution context; node payloads never accumulate here."""

    __slots__ = (
        'event_id',
        'identity',
        'configured',
        'reportable',
        'mode',
        'denominator',
        'emit_nodes',
        'debug',
        'origin',
        'started_at',
        'node_seq',
        'root_seen',
        'stage_count',
        'dropped_nodes',
        'last_outcome',
        'first_error',
        'failure_reason',
        'runner_failed',
        'closed',
        'adapter',
        'runner',
        'runner_category',
        'model_name',
        'pipeline_plugins',
        'node_adapter',
        'node_runner',
        'open_frames',
    )

    def __init__(self, execution_id: str | None = None) -> None:
        # The execution identity every record of this chain carries.
        self.event_id = str(execution_id).strip() if execution_id else str(uuid4())
        self.identity: dict[str, str] = {}
        self.configured = False
        # Platform ingress starts pending; an actual route admits the shared
        # execution before work starts. Independent API/debug runs are eligible.
        self.reportable = not reporting_suppressed()
        # Sampling, decided exactly once per event (at ingress or first touch).
        self.mode = 'all'
        self.denominator = 1
        self.emit_nodes = False
        self.debug = False
        self.origin = 'platform'
        self.started_at = _now()
        self.node_seq = 0
        self.root_seen = False
        self.stage_count = 0
        self.dropped_nodes = 0
        self.last_outcome = ''
        self.first_error = ''
        self.failure_reason = ''
        # Set when a runner node already reported a non-success outcome.
        self.runner_failed = False
        self.closed = False
        # Execution-scoped record fields attached by the owning lane when known.
        self.adapter = ''
        self.runner = ''
        self.runner_category = ''
        self.model_name = ''
        self.pipeline_plugins: typing.Any = None
        # First adapter/runner seen on a node, used for the chain record.
        self.node_adapter = ''
        self.node_runner = ''
        # Steps currently open anywhere in this chain, in the order they were
        # opened. A record emitted by a task that owns no step of its own
        # attaches to the innermost entry here.
        self.open_frames: dict[str, NodeFrame] = {}

    def allocate_seq(self) -> int:
        """Mint the next chain-local node order."""
        seq = self.node_seq
        self.node_seq += 1
        return seq

    def open_lane(self) -> str:
        """The innermost step open in this chain, whichever task opened it."""
        frames = list(self.open_frames)
        return frames[-1] if frames else ''

    def open_step(self, frame: NodeFrame) -> None:
        self.open_frames[frame.node_id] = frame

    def close_step(self, frame: NodeFrame) -> None:
        self.open_frames.pop(frame.node_id, None)

    def note_node(
        self,
        *,
        outcome: str,
        adapter: str = '',
        runner: str = '',
        family: str = '',
        error: str = '',
    ) -> None:
        """Remember only what the terminal chain record needs from a node."""
        self.stage_count += 1
        self.last_outcome = outcome or 'unknown'
        if adapter and not self.node_adapter:
            self.node_adapter = adapter
        if runner and not self.node_runner:
            self.node_runner = runner
        if family == 'runner' and outcome not in ('success', 'skipped'):
            # The lane records its own failed runner step only when the runner
            # orchestrator has not already landed one.
            self.runner_failed = True
        if outcome in ('failed', 'cancelled', 'timeout') and error and not self.first_error:
            # The chain must explain itself even when the break was reported as
            # a failed node rather than as an exception at the boundary.
            self.first_error = error

    def mark_failure(self, reason: str) -> None:
        """Remember why this chain broke so the payload can explain itself."""
        if not self.failure_reason:
            self.failure_reason = reason

    def outcome(self) -> str:
        """Terminal outcome of this chain; a broken chain never reports success."""
        if self.failure_reason and self.last_outcome in ('', 'success', 'skipped', 'unknown'):
            return 'failed'
        return self.last_outcome or 'unknown'


class TraceBinding(typing.NamedTuple):
    state: TraceState
    created: bool
    token: typing.Any


def bind(execution_id: str | None = None) -> TraceBinding:
    """Start a chain unless one is already in flight in this context.

    The execution id becomes the chain identity only when this call starts it;
    a nested boundary keeps the enclosing execution's identity.
    """
    existing = _current.get()
    if existing is not None:
        return TraceBinding(existing, False, None)
    state = TraceState(execution_id)
    return TraceBinding(state, True, _current.set(state))


def unbind(binding: TraceBinding) -> bool:
    """Detach this binding. Returns True when this caller owns the chain."""
    if binding.token is not None:
        try:
            _current.reset(binding.token)
        except (ValueError, RuntimeError):
            # A token from another context must never break execution.
            pass
    return binding.created


def unbind_root(binding: TraceBinding) -> bool:
    """Detach only when this caller started the chain, else leave it in place."""
    if not binding.created:
        return False
    return unbind(binding)


def current() -> TraceState | None:
    return _current.get()


def reporting_suppressed() -> bool:
    return _reporting_suppressed.get()


def admit() -> None:
    """Admit a matched delivery without revoking any concurrent sibling's choice."""
    state = current()
    if state is not None and not state.closed and not reporting_suppressed():
        state.reportable = True


@contextlib.contextmanager
def suppress_reporting():
    """Keep discarded branch side effects local even if a sibling is admitted."""
    token = _reporting_suppressed.set(True)
    try:
        yield
    finally:
        _reporting_suppressed.reset(token)


def node_stack() -> tuple[NodeFrame, ...]:
    """This task's own open-step frames, innermost last."""
    return _node.get()


def current_parent() -> str:
    """The step node that records emitted right now attach to ('' when none)."""
    stack = _node.get()
    return stack[-1].node_id if stack else ''


def enclosing_parent() -> str:
    """The step enclosing the innermost open one; '' when it is a root step."""
    stack = _node.get()
    return stack[-2].node_id if len(stack) > 1 else ''


def resolve_node(
    state: TraceState,
    node: str,
    fallback_started_at: str,
) -> tuple[str, int, str, str]:
    """Resolve one record to ``(node_id, seq, started_at, parent_node_id)``.

    A record stamped with a ``node`` the calling task has open reuses that
    step's identity, order and start time; anything else (a plain observation,
    or a node opened by another task) is a fresh node under the innermost step
    open in this task. A task that inherited no step at all - plugin/RPC work
    that only knows the execution - attaches to the innermost step the chain
    has open, which is the step that caused the work.
    """
    stack = _node.get()
    if node:
        for index in range(len(stack) - 1, -1, -1):
            frame = stack[index]
            if frame.node_id == node:
                parent = stack[index - 1].node_id if index > 0 else ''
                return frame.node_id, frame.seq, frame.started_at, parent
    parent = stack[-1].node_id if stack else state.open_lane()
    return node or uuid4().hex, state.allocate_seq(), fallback_started_at, parent


@contextlib.contextmanager
def stage_scope() -> typing.Iterator[str]:
    """Open one workflow step node for the duration of the block.

    Allocates a globally unique node id and the chain-local order, publishes the
    frame on this task's own stack so nested observations attach to it as their
    parent, and yields the node id so the step's own record can be stamped with
    ``node=``. Outside any execution nothing is allocated and '' is yielded.
    """
    state = _current.get()
    if state is None:
        yield ''
        return
    frame = NodeFrame(uuid4().hex, state.allocate_seq(), _now())
    token = _node.set(_node.get() + (frame,))
    state.open_step(frame)
    try:
        yield frame.node_id
    finally:
        state.close_step(frame)
        try:
            _node.reset(token)
        except (ValueError, RuntimeError):
            # A token from another context must never break execution.
            pass


def set_run(run_id: str) -> typing.Any:
    return _run.set(run_id)


def reset_run(token: typing.Any) -> None:
    if token is None:
        return
    try:
        _run.reset(token)
    except (ValueError, RuntimeError):
        # A token from another context must never break execution.
        pass


@contextlib.contextmanager
def scope(*, route_ref: str | None = None) -> typing.Iterator[None]:
    """Pin routing identity for nodes recorded inside this block."""
    if not route_ref:
        yield
        return
    token = _route.set(route_ref)
    try:
        yield
    finally:
        try:
            _route.reset(token)
        except (ValueError, RuntimeError):
            pass


def current_route() -> str:
    return _route.get()


def current_run() -> str:
    return _run.get()
