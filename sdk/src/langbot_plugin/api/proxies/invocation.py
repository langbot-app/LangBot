"""Task-local API binding shared by plugin and component methods."""

from __future__ import annotations

from contextlib import aclosing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import inspect
from types import MappingProxyType
from typing import Any, Mapping

from langbot_plugin.entities.io.context import InstallationBinding


def freeze_config(value: Any) -> Any:
    """Return an immutable invocation snapshot without sharing tenant objects."""

    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): freeze_config(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_config(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_config(item) for item in value)
    return value


def thaw_config(value: Any) -> Any:
    """Return a recursively JSON-safe copy of an immutable config snapshot."""

    if isinstance(value, Mapping):
        return {str(key): thaw_config(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_config(item) for item in value]
    if isinstance(value, frozenset):
        return [thaw_config(item) for item in value]
    return value


@dataclass
class Invocation:
    handler: Any
    api: Any
    config: Mapping[str, Any] | None = None
    binding: InstallationBinding | None = None
    active: bool = True

    def require_active(self) -> None:
        if not self.active:
            raise RuntimeError("Plugin invocation has ended")


_current: ContextVar[Invocation | None] = ContextVar("plugin_invocation", default=None)


@dataclass
class _AuditCorrelation:
    value: Any
    active: bool = True


_audit_correlation: ContextVar[_AuditCorrelation | None] = ContextVar(
    "plugin_audit_correlation", default=None
)
AUDIT_CORRELATION_FIELD = "_host_audit_id"


@contextmanager
def audit_correlation_scope(value):
    correlation = _AuditCorrelation(value)
    token = _audit_correlation.set(correlation)
    try:
        yield
    finally:
        correlation.active = False
        _audit_correlation.reset(token)


def current_audit_correlation():
    correlation = _audit_correlation.get()
    if correlation is None or correlation.value is None:
        return None
    if not correlation.active:
        raise RuntimeError("Plugin audit invocation has ended")
    return correlation.value


def relay_audit_correlation(data):
    correlation = current_audit_correlation()
    if correlation is None or AUDIT_CORRELATION_FIELD in data:
        return data
    return {**data, AUDIT_CORRELATION_FIELD: correlation}


@dataclass
class _EventOrigin:
    query_uuid: str
    active: bool = True


_event_origin: ContextVar[_EventOrigin | None] = ContextVar(
    "plugin_event_origin", default=None
)
EVENT_ORIGIN_FIELD = "origin_query_uuid"


@contextmanager
def event_origin_scope(query_uuid: str | None):
    """Mark plugin calls made while handling one event as caused by its Query.

    The origin is attribution only: LangBot uses it to link monitoring
    records to the triggering message, never to authorize an action.
    Work that escapes the handler (for example a detached task) stops
    reporting the origin once the handler returns.
    """
    if not query_uuid:
        yield
        return
    origin = _EventOrigin(str(query_uuid))
    token = _event_origin.set(origin)
    try:
        yield
    finally:
        origin.active = False
        _event_origin.reset(token)


def current_event_origin() -> str | None:
    """Return the Query uuid of the event being handled, if still active."""
    origin = _event_origin.get()
    if origin is None or not origin.active:
        return None
    return origin.query_uuid


def relay_event_origin(data: dict[str, Any]) -> dict[str, Any]:
    """Attach the active event origin to an outbound action payload."""
    origin = current_event_origin()
    if origin is None or EVENT_ORIGIN_FIELD in data:
        return data
    return {**data, EVENT_ORIGIN_FIELD: origin}


@contextmanager
def bind_invocation(
    handler,
    api=None,
    *,
    config: Mapping[str, Any] | None = None,
    binding: InstallationBinding | None = None,
):
    invocation = Invocation(
        handler,
        api,
        config=freeze_config(config or {}) if config is not None else None,
        binding=binding,
    )
    token = _current.set(invocation)
    try:
        yield
    finally:
        invocation.active = False
        _current.reset(token)


def current_api(handler):
    invocation = _current.get()
    if invocation is None or invocation.handler is not handler:
        return None
    if not invocation.active:
        raise RuntimeError("Runner invocation has ended")
    return invocation.api


def current_invocation(handler=None) -> Invocation | None:
    """Return the active task-local invocation, rejecting escaped background work."""

    invocation = _current.get()
    if invocation is None:
        return None
    if handler is not None and invocation.handler is not handler:
        return None
    if not invocation.active:
        raise RuntimeError("Plugin invocation has ended")
    return invocation


def invocation_capability(handler=None) -> Invocation | None:
    """Return the current revocable authority object for outbound boundaries."""

    invocation = _current.get()
    if invocation is None or (
        handler is not None and invocation.handler is not handler
    ):
        return None
    invocation.require_active()
    return invocation


def current_config(handler=None) -> Mapping[str, Any] | None:
    invocation = current_invocation(handler)
    return None if invocation is None else invocation.config


def current_binding(handler=None) -> InstallationBinding | None:
    invocation = current_invocation(handler)
    return None if invocation is None else invocation.binding


def run_scoped(method):
    """Use the same public method with the current Runner authorization, if any."""
    signature = inspect.signature(method)

    def target(instance, args, kwargs):
        api = current_api(instance.plugin_runtime_handler)
        if api is None:
            return method, (instance, *args), kwargs
        bound = signature.bind(instance, *args, **kwargs)
        arguments = dict(bound.arguments)
        arguments.pop("self")
        if method.__name__ == "call_tool":
            arguments.pop("session", None)
            arguments.pop("query_id", None)
        return getattr(api, method.__name__), (), arguments

    if inspect.isasyncgenfunction(method):

        @wraps(method)
        async def stream(self, *args, **kwargs):
            fn, positional, named = target(self, args, kwargs)
            async with aclosing(fn(*positional, **named)) as owned_stream:
                async for item in owned_stream:
                    yield item

        return stream

    @wraps(method)
    async def call(self, *args, **kwargs):
        fn, positional, named = target(self, args, kwargs)
        return await fn(*positional, **named)

    return call
