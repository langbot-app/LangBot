"""Minimal async client for the Multica chat API.

Only the endpoints the Runner needs are wrapped:

- GET  /api/agents
- POST /api/chat/sessions
- POST /api/chat/sessions/{id}/messages
- GET  /api/chat/sessions/{id}/messages/page
- GET  /api/chat/sessions/{id}/pending-task

Authentication uses a Multica personal access token (``mul_...``) sent as a
Bearer token; the target workspace is selected with ``X-Workspace-ID``.
"""

from __future__ import annotations

import json
import typing

import httpx

from pkg.endpoint import endpoint
from pkg.errors import MulticaAPIError

MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class AsyncMulticaClient:
    """Stateless Multica REST client; one instance per run."""

    def __init__(
        self,
        server_url: str,
        token: str,
        workspace_id: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.server_url = endpoint(server_url).rstrip("/")
        self.token = token
        self.workspace_id = workspace_id
        self.timeout = timeout
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "X-Workspace-ID": self.workspace_id,
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, typing.Any] | None = None,
        payload: dict[str, typing.Any] | None = None,
    ) -> typing.Any:
        url = f"{self.server_url}{path}"
        try:
            async with httpx.AsyncClient(
                trust_env=False,
                follow_redirects=False,
                timeout=self.timeout,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    json=payload,
                ) as response:
                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE_BYTES:
                            raise MulticaAPIError("Multica response exceeds the runtime limit")
                    status = response.status_code
        except httpx.TimeoutException:
            raise MulticaAPIError(
                f"Multica request {method} {path} timed out after {self.timeout}s",
                code="multica.timeout",
                retryable=True,
            ) from None
        except httpx.HTTPError as exc:
            raise MulticaAPIError(
                f"Multica request {method} {path} failed: {exc.__class__.__name__}",
                code="multica.network_error",
                retryable=True,
            ) from None

        text = bytes(body).decode("utf-8", errors="replace")
        if status >= 400:
            message = text
            try:
                decoded = json.loads(text)
                if isinstance(decoded, dict) and decoded.get("error"):
                    message = str(decoded["error"])
            except ValueError:
                pass
            raise MulticaAPIError(
                f"Multica {method} {path} returned {status}: {message[:500]}",
                code=_status_code(status),
                retryable=status >= 500 or status == 429,
                status=status,
            )
        if not text.strip():
            return None
        try:
            return json.loads(text)
        except ValueError:
            raise MulticaAPIError(
                f"Multica {method} {path} returned a non-JSON body",
                code="multica.invalid_response",
            ) from None

    async def list_agents(self) -> list[dict[str, typing.Any]]:
        data = await self._request("GET", "/api/agents")
        if isinstance(data, dict):
            data = data.get("agents", [])
        if not isinstance(data, list):
            raise MulticaAPIError("Multica agent list has an unexpected shape", code="multica.invalid_response")
        return [item for item in data if isinstance(item, dict) and not item.get("archived_at")]

    async def create_session(self, agent_id: str, title: str) -> str:
        data = await self._request("POST", "/api/chat/sessions", payload={"agent_id": agent_id, "title": title})
        session_id = data.get("id") if isinstance(data, dict) else None
        if not session_id:
            raise MulticaAPIError("Multica did not return a chat session id", code="multica.invalid_response")
        return str(session_id)

    async def send_message(self, session_id: str, content: str) -> str:
        data = await self._request(
            "POST",
            f"/api/chat/sessions/{session_id}/messages",
            payload={"content": content},
        )
        task_id = data.get("task_id") if isinstance(data, dict) else None
        if not task_id:
            raise MulticaAPIError("Multica did not return a task id for the message", code="multica.invalid_response")
        return str(task_id)

    async def recent_messages(self, session_id: str, limit: int = 30) -> list[dict[str, typing.Any]]:
        data = await self._request(
            "GET",
            f"/api/chat/sessions/{session_id}/messages/page",
            params={"limit": limit},
        )
        messages = data.get("messages") if isinstance(data, dict) else data
        if not isinstance(messages, list):
            raise MulticaAPIError("Multica message page has an unexpected shape", code="multica.invalid_response")
        return [m for m in messages if isinstance(m, dict)]

    async def pending_task_ids(self, session_id: str) -> set[str]:
        """Return ids of the running task and queued follow-ups of a session."""
        data = await self._request("GET", f"/api/chat/sessions/{session_id}/pending-task")
        if not isinstance(data, dict):
            return set()
        ids = {str(data["task_id"])} if data.get("task_id") else set()
        for queued in data.get("queued_tasks") or []:
            if isinstance(queued, dict) and queued.get("task_id"):
                ids.add(str(queued["task_id"]))
        return ids


def _status_code(status: int) -> str:
    if status in (401, 403):
        return "multica.unauthorized"
    if status == 404:
        return "multica.not_found"
    if status == 429:
        return "multica.rate_limited"
    return "multica.http_error"
