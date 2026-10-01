"""Content-free per-execution traces.

One trace identity is one execution identity: the id a Pipeline query, inbound
platform event or Agent run is known by, so a stored chain can be joined with
the Space view of that same execution. Stage records appended under it describe
how that one execution was routed and processed, using only code-defined
identifiers. Nothing here is aggregated: a trace is a bounded, ordered sequence
for one execution.

Three bounds keep memory independent of traffic volume:

* ``MAX_STAGES`` stages per trace (further stages are counted, not kept);
* ``MAX_TRACES`` traces in flight, enforced by the sender that owns the buffer;
* a wall-clock TTL, enforced by the sender's sweep.

The identity itself lives in a ContextVar so that asynchronous work spawned
while handling one execution inherits it, mirroring ``telemetry.platform``.
Cross-task stages (plugin/RPC work with no inherited context) are resolved by
the owner's execution-id registry instead.
"""

from __future__ import annotations

import contextlib
import contextvars
import typing
from datetime import datetime, timezone
from uuid import uuid4

MAX_STAGES = 32

_current: contextvars.ContextVar['TraceState | None'] = contextvars.ContextVar('telemetry_trace', default=None)
_route: contextvars.ContextVar[str] = contextvars.ContextVar('telemetry_trace_route', default='')
_run: contextvars.ContextVar[str] = contextvars.ContextVar('telemetry_trace_run', default='')
# Open workflow step nodes, innermost last. Records emitted inside a step carry
# the innermost node as their ``parent``; the step's own record carries the one
# below it (its enclosing step), never itself.
_node: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar('telemetry_trace_node', default=())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceState:
    """Bounded stage buffer for exactly one execution."""

    __slots__ = (
        'trace_id',
        'execution_id',
        'started_at',
        'stages',
        'dropped_stages',
        'synthetic',
        'sequence',
        'node_sequence',
        'open_nodes',
        'identity',
        'abandoned',
        'failure_reason',
        'closed',
        'adapter',
        'runner',
        'runner_category',
        'model_name',
        'pipeline_plugins',
    )

    def __init__(self, execution_id: str | None = None) -> None:
        # The execution identity is the trace identity so a stored chain can be
        # joined to the Space view of that same Pipeline query / event / run.
        self.execution_id = str(execution_id).strip() if execution_id else ''
        self.trace_id = self.execution_id or str(uuid4())
        self.started_at = _now()
        self.stages: list[dict[str, typing.Any]] = []
        self.dropped_stages = 0
        self.synthetic = False
        self.sequence = 0
        # Node ids number the workflow steps of this one execution ("n1", "n2"...).
        self.node_sequence = 0
        # Mirror of the open step stack, readable from any task: cross-task
        # observations (plugin/RPC) resolve their parent through this.
        self.open_nodes: tuple[str, ...] = ()
        self.identity: dict[str, str] = {}
        # Set when the sender refused to buffer this trace: stop appending.
        self.abandoned = False
        self.failure_reason = ''
        self.closed = False
        # Execution-scoped record fields attached by the owning lane when known.
        self.adapter = ''
        self.runner = ''
        self.runner_category = ''
        self.model_name = ''
        self.pipeline_plugins: typing.Any = None

    def append(
        self,
        *,
        family: str,
        operation: str,
        mode: str,
        adapter: str,
        runner: str,
        outcome: str,
        synthetic: bool,
        error: str = '',
        node: str = '',
        parent: str = '',
    ) -> None:
        if len(self.stages) >= MAX_STAGES:
            self.dropped_stages += 1
            return
        seen = _now()
        entry = {
            'family': family,
            'operation': operation,
            'mode': mode,
            'adapter': adapter,
            'runner': runner,
            'outcome': outcome,
            'synthetic': bool(synthetic),
            'seq': self.sequence,
            'route_ref': _route.get(),
            'run_id': _run.get(),
            'first_seen': seen,
            'last_seen': seen,
            'error': error,
        }
        # Only workflow steps carry these; legacy records stay byte-identical.
        if node:
            entry['node'] = node
        if parent:
            entry['parent'] = parent
        self.stages.append(entry)
        self.sequence += 1
        if synthetic:
            self.synthetic = True

    def allocate_node(self) -> str:
        """Mint the next step-node id for this execution ("n1", "n2", ...)."""
        self.node_sequence += 1
        return f'n{self.node_sequence}'

    def mark_failure(self, reason: str) -> None:
        """Remember why this chain broke so the payload can explain itself."""
        if not self.failure_reason:
            self.failure_reason = reason

    def outcome(self) -> str:
        """Terminal outcome of this chain, for space-side display.

        A chain that carries a failure reason never reports ``success``: the
        reason is the point of the trace.
        """
        if self.stages:
            last = self.stages[-1]['outcome']
        else:
            last = 'unknown'
        if self.failure_reason and last in ('success', 'skipped', 'unknown'):
            return 'failed'
        return last


class TraceBinding(typing.NamedTuple):
    state: TraceState
    created: bool
    token: typing.Any


def bind(execution_id: str | None = None) -> TraceBinding:
    """Start a trace unless one is already in flight in this context.

    The execution id becomes the trace id only when this call starts the trace;
    a nested boundary keeps the enclosing execution's identity.
    """
    existing = _current.get()
    if existing is not None:
        return TraceBinding(existing, False, None)
    state = TraceState(execution_id)
    return TraceBinding(state, True, _current.set(state))


def unbind(binding: TraceBinding) -> bool:
    """Detach this binding. Returns True when this caller owns the trace."""
    if binding.token is not None:
        try:
            _current.reset(binding.token)
        except (ValueError, RuntimeError):
            # A token from another context must never break execution.
            pass
    return binding.created


def unbind_root(binding: TraceBinding) -> bool:
    """Detach only when this caller started the trace, else leave it in place."""
    if not binding.created:
        return False
    return unbind(binding)


def current() -> TraceState | None:
    return _current.get()


def current_parent() -> str:
    """The step node that records emitted right now attach to ('' when none)."""
    stack = _node.get()
    return stack[-1] if stack else ''


def enclosing_parent() -> str:
    """The step enclosing the innermost open one; '' when it is a root step."""
    stack = _node.get()
    return stack[-2] if len(stack) > 1 else ''


@contextlib.contextmanager
def stage_scope() -> typing.Iterator[str]:
    """Open one workflow step node for the duration of the block.

    Allocates a node id unique within the execution, publishes it as the current
    parent so that nested observations recorded inside the block attach to it,
    and yields that id so the step's own records can be stamped with ``node=``.
    Outside any trace nothing is allocated and the empty id is yielded.
    """
    state = _current.get()
    if state is None:
        yield ''
        return
    node = state.allocate_node()
    previous_open = state.open_nodes
    state.open_nodes = previous_open + (node,)
    token = _node.set(_node.get() + (node,))
    try:
        yield node
    finally:
        state.open_nodes = previous_open
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
    """Pin routing identity for stages recorded inside this block."""
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
