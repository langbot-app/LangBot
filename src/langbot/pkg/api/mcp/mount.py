"""ASGI integration: serve the LangBot MCP server alongside the Quart HTTP app.

The Quart app and the MCP server are both ASGI apps. We front them with a small
dispatcher ASGI callable:

- Requests whose path is (or is under) ``/mcp`` are authenticated with a
  LangBot API key (reusing ``apikey_service.verify_api_key``, which also
  accepts the global API key from ``config.yaml``) and then handed to the
  FastMCP Starlette app.
- Every other request goes to the Quart app unchanged.

The FastMCP streamable-HTTP transport requires its session manager's lifespan
to be running. Rather than rely on the dispatcher receiving ASGI lifespan
events (Quart owns those), we explicitly run the session manager in a background
task managed by LangBot's task manager.
"""

from __future__ import annotations

import contextlib
import typing

from .server import LangBotMCPServer

if typing.TYPE_CHECKING:
    from ...core import app as app_module


# JSON-RPC-ish 401 body returned before the MCP app is reached.
_UNAUTHORIZED_BODY = b'{"error":"unauthorized","message":"A valid LangBot API key is required for MCP access."}'


def _extract_api_key(headers: list[tuple[bytes, bytes]]) -> str:
    """Pull an API key from ASGI headers (X-API-Key or Authorization: Bearer)."""
    header_map = {k.lower(): v for k, v in headers}
    api_key = header_map.get(b'x-api-key', b'').decode('latin-1').strip()
    if api_key:
        return api_key
    auth = header_map.get(b'authorization', b'').decode('latin-1').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    return ''


class MCPMount:
    """Owns the MCP server and produces the dispatcher ASGI app."""

    MCP_PATH_PREFIX = '/mcp'

    def __init__(self, ap: app_module.Application) -> None:
        self.ap = ap
        self.server = LangBotMCPServer(ap)
        self._mcp_asgi = self.server.streamable_http_app()
        self._lifespan_cm: typing.Any = None

    async def start_session_manager(self) -> None:
        """Run the MCP session manager lifespan in the background.

        StreamableHTTPSessionManager.run() is a one-shot async context manager
        (it may only be entered once). We keep it open for the process lifetime;
        it is torn down when the event loop stops.
        """
        cm = self.server.session_manager.run()
        self._lifespan_cm = cm
        await cm.__aenter__()

    async def stop_session_manager(self) -> None:
        if self._lifespan_cm is not None:
            with contextlib.suppress(Exception):
                await self._lifespan_cm.__aexit__(None, None, None)
            self._lifespan_cm = None

    def _is_mcp_path(self, path: str) -> bool:
        return path == self.MCP_PATH_PREFIX or path.startswith(self.MCP_PATH_PREFIX + '/')

    def wrap(self, quart_asgi: typing.Callable) -> typing.Callable:
        """Return a dispatcher ASGI app fronting ``quart_asgi``."""
        mcp_asgi = self._mcp_asgi
        verify_api_key = self.ap.apikey_service.verify_api_key
        is_mcp_path = self._is_mcp_path

        async def dispatcher(scope, receive, send):  # type: ignore[no-untyped-def]
            # Pass through non-HTTP scopes (lifespan, websocket) to Quart so its
            # own startup/shutdown and websocket routes keep working.
            if scope['type'] != 'http' or not is_mcp_path(scope.get('path', '')):
                await quart_asgi(scope, receive, send)
                return

            # Authenticate MCP HTTP requests with a LangBot API key.
            api_key = _extract_api_key(scope.get('headers', []))
            authorized = False
            if api_key:
                with contextlib.suppress(Exception):
                    authorized = await verify_api_key(api_key)

            if not authorized:
                await send(
                    {
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'www-authenticate', b'Bearer'),
                        ],
                    }
                )
                await send({'type': 'http.response.body', 'body': _UNAUTHORIZED_BODY})
                return

            await mcp_asgi(scope, receive, send)

        return dispatcher
