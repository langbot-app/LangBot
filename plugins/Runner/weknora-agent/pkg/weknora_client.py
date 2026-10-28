"""WeKnora API client for Runner.

Ported from LangBot's legacy core WeKnora client and kept plugin-local so the
runner can be distributed without importing LangBot core modules.
"""

from __future__ import annotations

import json
import typing

import httpx

from pkg.deadline import deadline
from pkg.endpoint import endpoint
from pkg.errors import WeKnoraAPIError
from pkg.http_limits import limited_body, limited_lines, limited_post


class AsyncWeKnoraClient:
    """Minimal WeKnora API client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8080/api/v1",
    ) -> None:
        self.api_key = api_key
        self.base_url = endpoint(base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    @deadline
    async def create_session(
        self,
        title: str = "",
        description: str = "",
        timeout: float = 30.0,
    ) -> str:
        """Create a WeKnora session and return its id."""
        payload: dict[str, typing.Any] = {}
        if title:
            payload["title"] = title
        if description:
            payload["description"] = description

        try:
            async with httpx.AsyncClient(trust_env=False, timeout=timeout) as http_client:
                response = await limited_post(
                    http_client,
                    self._url("/sessions"),
                    WeKnoraAPIError,
                    headers=self._headers(),
                    json=payload,
                )
        except httpx.TimeoutException:
            raise WeKnoraAPIError(
                f"WeKnora create session timed out after {timeout}s",
                code="weknora.timeout",
                retryable=True,
            ) from None

        if response.status_code not in (200, 201):
            raise WeKnoraAPIError(
                f"WeKnora create session failed: status={response.status_code}, body={response.text}",
                code="weknora.http_error",
            )

        data = response.json()
        try:
            session_id = data["data"]["id"]
        except (KeyError, TypeError) as exc:
            raise WeKnoraAPIError(
                f"WeKnora create session response missing data.id: {data}",
                code="weknora.api_error",
            ) from exc

        if not isinstance(session_id, str) or not session_id:
            raise WeKnoraAPIError(
                f"WeKnora create session returned invalid id: {session_id}",
                code="weknora.api_error",
            )
        return session_id

    @deadline
    async def agent_chat(
        self,
        session_id: str,
        query: str,
        user: str,
        agent_id: str = "",
        knowledge_base_ids: list[str] | None = None,
        web_search_enabled: bool = False,
        timeout: float = 120.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Run WeKnora agent chat and yield parsed SSE data."""
        if knowledge_base_ids is None:
            knowledge_base_ids = []

        payload: dict[str, typing.Any] = {
            "query": query,
            "agent_enabled": True,
            "channel": "im",
        }
        if agent_id:
            payload["agent_id"] = agent_id
        if knowledge_base_ids:
            payload["knowledge_base_ids"] = knowledge_base_ids
        if web_search_enabled:
            payload["web_search_enabled"] = True

        async for data in self._stream_json_lines(
            path=f"/agent-chat/{session_id}",
            payload=payload,
            timeout=timeout,
        ):
            yield data

    @deadline
    async def knowledge_chat(
        self,
        session_id: str,
        query: str,
        user: str,
        agent_id: str = "builtin-quick-answer",
        knowledge_base_ids: list[str] | None = None,
        timeout: float = 120.0,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        """Run WeKnora knowledge-base chat and yield parsed SSE data."""
        if knowledge_base_ids is None:
            knowledge_base_ids = []

        payload: dict[str, typing.Any] = {
            "query": query,
            "channel": "im",
        }
        if agent_id:
            payload["agent_id"] = agent_id
        if knowledge_base_ids:
            payload["knowledge_base_ids"] = knowledge_base_ids

        async for data in self._stream_json_lines(
            path=f"/knowledge-chat/{session_id}",
            payload=payload,
            timeout=timeout,
        ):
            yield data

    async def _stream_json_lines(
        self,
        *,
        path: str,
        payload: dict[str, typing.Any],
        timeout: float,
    ) -> typing.AsyncGenerator[dict[str, typing.Any], None]:
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=timeout) as http_client:
                async with http_client.stream(
                    "POST",
                    self._url(path),
                    headers=self._headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        body = await limited_body(response, WeKnoraAPIError)
                        raise WeKnoraAPIError(
                            f"WeKnora request failed: status={response.status_code}, body={body.decode('utf-8', errors='replace')[:200]}",
                            code="weknora.http_error",
                        )

                    async for line in limited_lines(response, WeKnoraAPIError):
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if not line:
                            continue

                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        if not isinstance(data, dict):
                            continue
                        yield data
                        if data.get("response_type") == "error":
                            return
        except httpx.TimeoutException:
            raise WeKnoraAPIError(
                f"WeKnora request timed out after {timeout}s",
                code="weknora.timeout",
                retryable=True,
            ) from None
