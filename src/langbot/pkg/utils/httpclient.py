"""Shared aiohttp.ClientSession to avoid repeated SSL context creation.

Each call to `aiohttp.ClientSession()` creates a new `TCPConnector` which in turn
creates a new `ssl.SSLContext` and loads all system root certificates. This is
extremely expensive in both CPU and memory (~270MB total allocations observed via
memray profiling).

This module provides a shared session pool so that all HTTP client code in LangBot
reuses the same underlying SSL context and connection pool.
"""

from __future__ import annotations

import aiohttp

_sessions: dict[str, aiohttp.ClientSession] = {}


def get_session(*, trust_env: bool = False) -> aiohttp.ClientSession:
    """Get or create a shared aiohttp.ClientSession.

    Args:
        trust_env: Whether to trust environment variables for proxy settings.

    Returns:
        A shared aiohttp.ClientSession instance.
    """
    key = f'trust_env={trust_env}'

    session = _sessions.get(key)
    if session is None or session.closed:
        # Shared transport pools must never share upstream cookie state across
        # Workspace-scoped requests. Callers that need a stateful cookie jar
        # must own a dedicated session instead of using this global pool.
        session = aiohttp.ClientSession(
            trust_env=trust_env,
            cookie_jar=aiohttp.DummyCookieJar(),
        )
        _sessions[key] = session

    return session


async def close_all():
    """Close all shared sessions. Call on application shutdown."""
    for session in _sessions.values():
        if not session.closed:
            await session.close()
    _sessions.clear()
