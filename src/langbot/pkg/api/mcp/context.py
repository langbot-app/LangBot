from __future__ import annotations

import contextvars

from ..http.context import RequestContext


_request_context: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    'langbot_mcp_request_context',
    default=None,
)


def bind_request_context(context: RequestContext) -> contextvars.Token[RequestContext | None]:
    """Bind the authenticated MCP request while its ASGI request is executing."""

    return _request_context.set(context)


def reset_request_context(token: contextvars.Token[RequestContext | None]) -> None:
    _request_context.reset(token)


def get_request_context() -> RequestContext:
    """Return the current trusted MCP context or fail closed."""

    context = _request_context.get()
    if context is None:
        raise RuntimeError('MCP Workspace context is unavailable')
    return context
