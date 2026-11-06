"""Minimal async client for the Multica chat API.

Only the endpoints the Runner needs are wrapped:

- GET  /api/agents
- POST /api/chat/sessions
- POST /api/chat/sessions/{id}/messages
- GET  /api/chat/sessions/{id}/messages/page
- GET  /api/chat/sessions/{id}/pending-task

Multica exposes no task event stream: a caller can only observe a task's
lifecycle (queued -> running -> gone) and the reply row written at the end.
Authentication uses a Multica personal access token (``mul_...``) sent as a
Bearer token; the target workspace is selected with ``X-Workspace-ID``.
"""

from __future__ import annotations

import json
import re
import typing

import httpx

from pkg.endpoint import endpoint
from pkg.errors import MulticaAPIError

MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_LISTED_NAMES = 10

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

TASK_RUNNING = "running"
TASK_QUEUED = "queued"


def is_uuid(value: str) -> bool:
    return bool(_UUID.match(value))


def short_id(agent_id: typing.Any) -> str:
    return str(agent_id or "")[:8]


def match_agents(agents: list[dict[str, typing.Any]], query: str) -> list[dict[str, typing.Any]]:
    """Match by exact id, then case-insensitive exact name, then name substring."""
    by_id = [a for a in agents if str(a.get("id")) == query]
    if by_id:
        return by_id
    lowered = query.casefold()
    exact = [a for a in agents if str(a.get("name") or "").casefold() == lowered]
    if exact:
        return exact
    return [a for a in agents if lowered in str(a.get("name") or "").casefold()]


def names_hint(agents: list[dict[str, typing.Any]], unnamed: str = "(unnamed)") -> str:
    """Comma-separated names of the first agents, for "did you mean" hints."""
    names = ", ".join(str(a.get("name") or unnamed) for a in agents[:MAX_LISTED_NAMES])
    return names + (", …" if len(agents) > MAX_LISTED_NAMES else "")


def numbered(agents: list[dict[str, typing.Any]], unnamed: str = "(unnamed)") -> str:
    """``1) name [id8] 2) ...``: the numbering ``use <number>`` refers to."""
    return " ".join(
        f"{index}) {a.get('name') or unnamed} [{short_id(a.get('id'))}]" for index, a in enumerate(agents, start=1)
    )


class AgentResolutionError(MulticaAPIError):
    """A name did not select exactly one agent.

    ``candidates`` holds ambiguous matches, ``visible`` the agents searched when
    nothing matched; callers render their own localized message from them.
    """

    def __init__(
        self,
        message: str,
        code: str,
        query: str = "",
        candidates: list[dict[str, typing.Any]] | None = None,
        visible: list[dict[str, typing.Any]] | None = None,
    ):
        super().__init__(message, code=code)
        self.query = query
        self.candidates = candidates or []
        self.visible = visible or []


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

    async def resolve_agent(self, query: str) -> dict[str, typing.Any]:
        """Resolve an agent name or UUID to ``{"id", "name"}``.

        A UUID is returned as-is without a request (``name`` is empty). Otherwise the
        unarchived agents are matched by exact name (case-insensitive) and then by a
        unique name substring. Zero or several matches raise ``AgentResolutionError``.
        """
        query = query.strip()
        if is_uuid(query):
            return {"id": query, "name": ""}
        agents = await self.list_agents()
        matches = match_agents(agents, query)
        if len(matches) == 1:
            return {"id": str(matches[0].get("id")), "name": str(matches[0].get("name") or "")}
        if matches:
            raise AgentResolutionError(
                f"'{query}' matches several Multica agents: {numbered(matches)}",
                code="multica.agent_ambiguous",
                query=query,
                candidates=matches,
            )
        raise AgentResolutionError(
            f"No Multica agent matches '{query}'. Visible agents: {names_hint(agents)}",
            code="multica.agent_not_found",
            query=query,
            visible=agents,
        )

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

    async def pending_tasks(self, session_id: str) -> dict[str, str]:
        """Map the session's pending task ids to ``running`` or ``queued``.

        The head task is ``running`` unless Multica reports another status for it;
        follow-ups listed in ``queued_tasks`` are ``queued``. A finished or cancelled
        task is absent.
        """
        data = await self._request("GET", f"/api/chat/sessions/{session_id}/pending-task")
        if not isinstance(data, dict):
            return {}
        tasks: dict[str, str] = {}
        for queued in data.get("queued_tasks") or []:
            if isinstance(queued, dict) and queued.get("task_id"):
                tasks[str(queued["task_id"])] = TASK_QUEUED
        if data.get("task_id"):
            status = str(data.get("status") or TASK_RUNNING).lower()
            tasks[str(data["task_id"])] = TASK_RUNNING if status == TASK_RUNNING else TASK_QUEUED
        return tasks


def _status_code(status: int) -> str:
    if status in (401, 403):
        return "multica.unauthorized"
    if status == 404:
        return "multica.not_found"
    if status == 429:
        return "multica.rate_limited"
    return "multica.http_error"
