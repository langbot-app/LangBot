"""Keep credential-bearing request targets out of httpx's request log.

httpx logs every response as ``HTTP Request: <METHOD> <full URL> ...`` at INFO,
and the plugin runtime logs at INFO. Some Dify targets carry a credential that
cannot move into a header: the human-input form token is a path segment (and
submits the form on its own through Dify's web API), and input file URLs may be
signed in their query or path.

Changing the ``httpx`` logger level would alter every co-located plugin's logs,
so this module instead installs one filter on that logger that is inert unless
the current task is inside :func:`redacted_target`. Only the log record of the
request opened within that block is rewritten; nothing is suppressed.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
from urllib.parse import urlsplit

_target: contextvars.ContextVar[str | None] = contextvars.ContextVar("dify_agent_redacted_target", default=None)


class _RedactRequestTarget(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        target = _target.get()
        if target is None:
            return True
        args = record.args
        if isinstance(args, tuple) and len(args) >= 2 and str(record.msg).startswith("HTTP Request:"):
            record.args = (args[0], target, *args[2:])
        else:
            record.msg, record.args = "HTTP request to %s (details redacted)", (target,)
        return True


_FILTER = _RedactRequestTarget()
logging.getLogger("httpx").addFilter(_FILTER)


def redact(url: str, keep_path: str | None = None) -> str:
    """Return ``scheme://host[:port]`` plus ``keep_path`` (or ``/[redacted]``)."""
    parts = urlsplit(str(url))
    origin = f"{parts.scheme}://{parts.netloc.rsplit('@', 1)[-1]}"
    return origin + (keep_path if keep_path is not None else "/[redacted]")


@contextlib.contextmanager
def redacted_target(target: str):
    """Log ``target`` instead of the real URL for requests sent inside this block.

    Keep the block around opening the request only; never yield to a consumer
    from inside it.
    """
    token = _target.set(target)
    try:
        yield
    finally:
        _target.reset(token)
