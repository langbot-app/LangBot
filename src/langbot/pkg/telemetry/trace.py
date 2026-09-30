"""Content-free per-event execution traces.

One trace identity is minted per inbound platform event and survives until the
ingress handler returns. Stage records appended under it describe how that one
event was routed and processed, using only code-defined identifiers. Nothing
here is aggregated: a trace is a bounded, ordered sequence for one event.

Three bounds keep memory independent of traffic volume:

* ``MAX_STAGES`` stages per trace (further stages are counted, not kept);
* ``MAX_TRACES`` traces in flight, enforced by the sender that owns the buffer;
* a wall-clock TTL, enforced by the sender's sweep.

The identity itself lives in a ContextVar so that asynchronous work spawned
while handling one event inherits it, mirroring ``telemetry.platform``.
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceState:
    """Bounded stage buffer for exactly one event."""

    __slots__ = (
        'trace_id',
        'started_at',
        'stages',
        'dropped_stages',
        'synthetic',
        'sequence',
        'identity',
        'abandoned',
    )

    def __init__(self) -> None:
        self.trace_id = str(uuid4())
        self.started_at = _now()
        self.stages: list[dict[str, typing.Any]] = []
        self.dropped_stages = 0
        self.synthetic = False
        self.sequence = 0
        self.identity: dict[str, str] = {}
        # Set when the sender refused to buffer this trace: stop appending.
        self.abandoned = False

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
    ) -> None:
        if len(self.stages) >= MAX_STAGES:
            self.dropped_stages += 1
            return
        seen = _now()
        self.stages.append(
            {
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
            }
        )
        self.sequence += 1
        if synthetic:
            self.synthetic = True

    def outcome(self) -> str:
        """Terminal outcome of the last recorded stage, for space-side display."""
        return self.stages[-1]['outcome'] if self.stages else 'unknown'


class TraceBinding(typing.NamedTuple):
    state: TraceState
    created: bool
    token: typing.Any


def bind() -> TraceBinding:
    """Start a trace unless one is already in flight in this context."""
    existing = _current.get()
    if existing is not None:
        return TraceBinding(existing, False, None)
    state = TraceState()
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
