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
import uuid

from ..http.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext
from .context import bind_request_context, reset_request_context
from .server import LangBotMCPServer

if typing.TYPE_CHECKING:
    from ...core import app as app_module


# JSON-RPC-ish 401 body returned before the MCP app is reached.
_UNAUTHORIZED_BODY = b'{"error":"unauthorized","message":"A valid LangBot API key is required for MCP access."}'
_ENTITLEMENT_UNAVAILABLE_BODY = (
    b'{"error":"entitlement_unavailable","message":"Workspace entitlement is unavailable for MCP access."}'
)


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
        authenticate_api_key = self.ap.apikey_service.authenticate_api_key
        is_mcp_path = self._is_mcp_path

        async def dispatcher(scope, receive, send):  # type: ignore[no-untyped-def]
            # Pass through non-HTTP scopes (lifespan, websocket) to Quart so its
            # own startup/shutdown and websocket routes keep working.
            if scope['type'] != 'http' or not is_mcp_path(scope.get('path', '')):
                await quart_asgi(scope, receive, send)
                return

            # Authenticate MCP HTTP requests with a LangBot API key.
            api_key = _extract_api_key(scope.get('headers', []))
            identity = None
            if api_key:
                with contextlib.suppress(Exception):
                    identity = await authenticate_api_key(api_key)

            if identity is None:
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

            deployment_admission = getattr(self.ap, 'deployment_admission', None)
            try:
                if deployment_admission is not None:
                    deployment_admission.require_active()
                entitlement_revision = 0
                deployment = getattr(self.ap, 'deployment', None)
                if deployment is not None and getattr(deployment, 'multi_workspace_enabled', False):
                    resolver = getattr(self.ap, 'entitlement_resolver', None)
                    if resolver is None or identity.instance_uuid != resolver.instance_uuid:
                        raise RuntimeError('Workspace entitlement resolver is unavailable')
                    entitlement = await resolver.resolve(identity.workspace_uuid)
                    entitlement_revision = entitlement.entitlement_revision
            except Exception:
                await send(
                    {
                        'type': 'http.response.start',
                        'status': 403,
                        'headers': [(b'content-type', b'application/json')],
                    }
                )
                await send({'type': 'http.response.body', 'body': _ENTITLEMENT_UNAVAILABLE_BODY})
                return

            request_context = RequestContext(
                instance_uuid=identity.instance_uuid,
                placement_generation=identity.placement_generation,
                request_id=str(uuid.uuid4()),
                auth_type='api-key',
                principal=PrincipalContext(
                    principal_type=PrincipalType.API_KEY,
                    api_key_uuid=identity.api_key_uuid,
                ),
                workspace=WorkspaceContext(
                    workspace_uuid=identity.workspace_uuid,
                    membership_uuid=None,
                    role=None,
                    permissions=identity.permissions,
                ),
                entitlement_revision=entitlement_revision,
            )
            tenant_scope = getattr(self.ap.persistence_mgr, 'tenant_scope', None)
            if not callable(tenant_scope):
                raise RuntimeError('MCP request persistence scope is unavailable')
            async with tenant_scope(identity.workspace_uuid):
                token = bind_request_context(request_context)
                try:
                    await mcp_asgi(scope, receive, send)
                    if deployment_admission is not None:
                        deployment_admission.require_active()
                finally:
                    reset_request_context(token)

        return dispatcher
