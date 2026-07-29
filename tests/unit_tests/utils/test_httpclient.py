"""
Unit tests for HTTP client session pool.

Tests session management, reuse, and cleanup.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import aiohttp
import httpx
from aiohttp import web

from langbot.pkg.utils import httpclient


pytestmark = pytest.mark.asyncio


class TestGetSession:
    """Tests for get_session function."""

    async def test_get_session_returns_client_session(self):
        """get_session returns an aiohttp.ClientSession."""
        session = httpclient.get_session()

        assert isinstance(session, aiohttp.ClientSession)
        assert not session.closed
        assert isinstance(session.cookie_jar, aiohttp.DummyCookieJar)

        # Cleanup
        await session.close()

    async def test_get_session_returns_same_instance(self):
        """get_session returns the same session for same trust_env."""
        session1 = httpclient.get_session(trust_env=False)
        session2 = httpclient.get_session(trust_env=False)

        assert session1 is session2

        # Cleanup
        await session1.close()

    async def test_get_session_different_trust_env_creates_different(self):
        """Different trust_env values create different sessions."""
        session1 = httpclient.get_session(trust_env=False)
        session2 = httpclient.get_session(trust_env=True)

        assert session1 is not session2

        # Cleanup
        await session1.close()
        await session2.close()

    async def test_get_session_recreates_if_closed(self):
        """get_session creates new session if previous is closed."""
        session1 = httpclient.get_session()
        await session1.close()

        session2 = httpclient.get_session()

        assert session2 is not session1
        assert not session2.closed

        # Cleanup
        await session2.close()


class TestCloseAll:
    """Tests for close_all function."""

    async def test_close_all_closes_all_sessions(self):
        """close_all closes all sessions."""
        # Create multiple sessions
        session1 = httpclient.get_session(trust_env=False)
        session2 = httpclient.get_session(trust_env=True)

        await httpclient.close_all()

        assert session1.closed
        assert session2.closed

    async def test_close_all_clears_pool(self):
        """close_all clears the session pool."""
        httpclient.get_session()
        httpclient.get_session(trust_env=True)

        await httpclient.close_all()

        assert len(httpclient._sessions) == 0


class TestReadLimited:
    async def test_rejects_oversized_content_length_before_reading(self):
        content = SimpleNamespace(iter_chunked=None)
        response = SimpleNamespace(headers={'Content-Length': '11'}, content=content)

        with pytest.raises(httpclient.RemoteResponseTooLargeError):
            await httpclient.read_limited(response, max_bytes=10)

    async def test_rejects_chunked_body_that_crosses_limit(self):
        class Content:
            async def iter_chunked(self, _chunk_size):
                yield b'12345'
                yield b'678901'

        response = SimpleNamespace(headers={}, content=Content())

        with pytest.raises(httpclient.RemoteResponseTooLargeError):
            await httpclient.read_limited(response, max_bytes=10)

    async def test_returns_body_within_limit(self):
        class Content:
            async def iter_chunked(self, _chunk_size):
                yield b'12345'
                yield b'67890'

        response = SimpleNamespace(headers={}, content=Content())

        assert await httpclient.read_limited(response, max_bytes=10) == b'1234567890'

    async def test_json_reader_uses_same_limit(self):
        class Content:
            async def iter_chunked(self, _chunk_size):
                yield b'{"ok":true}'

        response = SimpleNamespace(
            headers={},
            content=Content(),
        )

        assert await httpclient.read_json_limited(response, max_bytes=16) == {'ok': True}

    async def test_response_json_parse_runs_off_event_loop(self):
        event_loop_thread = threading.get_ident()
        response = SimpleNamespace(json=lambda: threading.get_ident())

        assert await httpclient.parse_json_response(response) != event_loop_thread

    async def test_response_json_parse_supports_async_test_doubles(self):
        response = SimpleNamespace(json=AsyncMock(return_value={'ok': True}))

        assert await httpclient.parse_json_response(response) == {'ok': True}

    async def test_response_text_runs_off_loop_and_caps_diagnostics(self):
        event_loop_thread = threading.get_ident()

        class Response:
            @property
            def text(self):
                return f'{threading.get_ident()}:abcdef'

        value = await httpclient.response_text(Response(), max_chars=4)

        assert not value.startswith(str(event_loop_thread))
        assert value.endswith('[truncated]')

    async def test_httpx_hook_rejects_before_automatic_buffer_grows(self):
        class Source(httpx.AsyncByteStream):
            def __init__(self):
                self.closed = False

            async def __aiter__(self):
                yield b'123'
                yield b'45'

            async def aclose(self):
                self.closed = True

        source = Source()
        transport = httpx.MockTransport(lambda _request: httpx.Response(200, stream=source))
        async with httpx.AsyncClient(
            transport=transport,
            event_hooks=httpclient.httpx_response_limit_hooks(max_bytes=4),
        ) as client:
            with pytest.raises(httpclient.RemoteResponseTooLargeError, match='4-byte'):
                await client.get('https://example.invalid')

        assert source.closed

    async def test_httpx_limited_stream_closes_source_when_consumer_is_cancelled(self):
        class Source(httpx.AsyncByteStream):
            def __init__(self):
                self.closed = False

            async def __aiter__(self):
                yield b'123'
                await asyncio.Event().wait()

            async def aclose(self):
                self.closed = True

        source = Source()
        stream = httpclient._LimitedHTTPXAsyncByteStream(source, max_bytes=4)
        first_chunk_consumed = asyncio.Event()

        async def consume():
            async for _chunk in stream:
                first_chunk_consumed.set()

        task = asyncio.create_task(consume())
        await first_chunk_consumed.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert source.closed

    async def test_close_all_handles_already_closed(self):
        """close_all handles already closed sessions gracefully."""
        session = httpclient.get_session()
        await session.close()

        # Should not raise
        await httpclient.close_all()

    async def test_close_all_idempotent(self):
        """close_all can be called multiple times."""
        httpclient.get_session()

        await httpclient.close_all()
        await httpclient.close_all()  # Should not raise

        assert len(httpclient._sessions) == 0


class TestSessionPoolIntegration:
    """Integration tests for session pool behavior."""

    async def test_session_can_make_request(self):
        """Session can be used for HTTP requests without relying on external network."""
        app = web.Application()

        async def handle_get(request):
            return web.json_response({'ok': True})

        app.router.add_get('/get', handle_get)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        session = httpclient.get_session()

        try:
            async with session.get(
                f'http://127.0.0.1:{port}/get',
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                assert resp.status == 200
                assert await resp.json() == {'ok': True}
        finally:
            await httpclient.close_all()
            await runner.cleanup()

    async def test_multiple_requests_same_session(self):
        """Multiple requests can use the same session."""
        session = httpclient.get_session()

        # Both calls return the same session
        session2 = httpclient.get_session()

        assert session is session2

        await httpclient.close_all()

    async def test_shared_session_does_not_persist_cookies(self):
        """Shared transport pooling never creates cross-Workspace cookie state."""
        session = httpclient.get_session()

        session.cookie_jar.update_cookies({'workspace_session': 'secret'})

        assert list(session.cookie_jar) == []
        await httpclient.close_all()
