"""Shared aiohttp.ClientSession to avoid repeated SSL context creation.

Each call to `aiohttp.ClientSession()` creates a new `TCPConnector` which in turn
creates a new `ssl.SSLContext` and loads all system root certificates. This is
extremely expensive in both CPU and memory (~270MB total allocations observed via
memray profiling).

This module provides a shared session pool so that all HTTP client code in LangBot
reuses the same underlying SSL context and connection pool.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import typing

import aiohttp
import httpx

_sessions: dict[str, aiohttp.ClientSession] = {}
DEFAULT_REMOTE_BODY_LIMIT = 10 * 1024 * 1024


class RemoteResponseTooLargeError(ValueError):
    """Raised before an untrusted remote response can exhaust process memory."""


class _LimitedHTTPXAsyncByteStream(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, max_bytes: int) -> None:
        self._inner = inner
        self._max_bytes = max_bytes
        self._read_bytes = 0

    async def __aiter__(self):
        try:
            async for chunk in self._inner:
                self._read_bytes += len(chunk)
                if self._read_bytes > self._max_bytes:
                    raise RemoteResponseTooLargeError(f'Remote response exceeds the {self._max_bytes}-byte limit')
                yield chunk
        except BaseException:
            # HTTPX only closes a response after normal stream exhaustion. If
            # this limiter raises (or its consumer is cancelled), explicitly
            # release the underlying connection before propagating the original
            # failure so persistent clients cannot accumulate stranded streams.
            try:
                await self._inner.aclose()
            except BaseException:
                pass
            raise

    async def aclose(self) -> None:
        await self._inner.aclose()


def httpx_response_limit_hooks(
    max_bytes: int = DEFAULT_REMOTE_BODY_LIMIT,
) -> dict[str, list]:
    """Return hooks that cap HTTPX bodies before its automatic buffering."""

    max_bytes = max(int(max_bytes), 1)

    async def limit_response(response: httpx.Response) -> None:
        content_length = response.headers.get('Content-Length')
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except (TypeError, ValueError):
                declared_size = None
            if declared_size is not None and declared_size > max_bytes:
                await response.aclose()
                raise RemoteResponseTooLargeError(f'Remote response exceeds the {max_bytes}-byte limit')

        if response.is_stream_consumed:
            if len(response.content) > max_bytes:
                await response.aclose()
                raise RemoteResponseTooLargeError(f'Remote response exceeds the {max_bytes}-byte limit')
            return
        response.stream = _LimitedHTTPXAsyncByteStream(response.stream, max_bytes)

    return {'response': [limit_response]}


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


async def read_limited(
    response: aiohttp.ClientResponse,
    *,
    max_bytes: int = DEFAULT_REMOTE_BODY_LIMIT,
) -> bytes:
    """Read an HTTP response incrementally with a strict byte limit."""

    max_bytes = max(int(max_bytes), 1)
    content_length = response.headers.get('Content-Length')
    if content_length is not None:
        try:
            declared_size = int(content_length)
        except (TypeError, ValueError):
            declared_size = None
        if declared_size is not None and declared_size > max_bytes:
            raise RemoteResponseTooLargeError(f'Remote response exceeds the {max_bytes}-byte limit')

    body = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise RemoteResponseTooLargeError(f'Remote response exceeds the {max_bytes}-byte limit')
    return bytes(body)


async def read_text_limited(
    response: aiohttp.ClientResponse,
    *,
    max_bytes: int = DEFAULT_REMOTE_BODY_LIMIT,
) -> str:
    body = await read_limited(response, max_bytes=max_bytes)
    return body.decode(response.charset or 'utf-8', errors='replace')


async def read_json_limited(
    response: aiohttp.ClientResponse,
    *,
    max_bytes: int = DEFAULT_REMOTE_BODY_LIMIT,
) -> typing.Any:
    body = await read_limited(response, max_bytes=max_bytes)
    return await asyncio.to_thread(json.loads, body)


async def parse_json_response(response: typing.Any) -> typing.Any:
    """Parse an already bounded HTTP response without blocking the event loop."""

    parsed = await asyncio.to_thread(response.json)
    if inspect.isawaitable(parsed):
        parsed = await parsed
    return parsed


async def response_text(
    response: typing.Any,
    *,
    max_chars: int = 4096,
) -> str:
    """Decode an already bounded response body off-loop and cap diagnostics."""

    text = await asyncio.to_thread(lambda: str(response.text))
    max_chars = max(int(max_chars), 1)
    if len(text) <= max_chars:
        return text
    return f'{text[:max_chars]}... [truncated]'
