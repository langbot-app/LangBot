"""
Unit tests for HTTP client session pool.

Tests session management, reuse, and cleanup.
"""

from __future__ import annotations

import pytest
import aiohttp
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
