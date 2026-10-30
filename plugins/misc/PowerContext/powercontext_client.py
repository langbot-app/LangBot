from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from typing import Any, Iterable
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class PowerContextResponse:
    data: dict[str, Any]
    request_id: str | None = None


class PowerContextError(RuntimeError):
    """A bounded, credential-free PowerContext transport or API error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id

    def safe_summary(self) -> str:
        parts = [str(self)]
        if self.error_code:
            parts.append(f"code={self.error_code}")
        if self.status_code is not None:
            parts.append(f"http={self.status_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return "; ".join(parts)


def validate_server_url(server_url: str, *, allow_insecure_http: bool = False) -> str:
    value = str(server_url or "").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("server_url must be an absolute http:// or https:// URL")
    if parsed.username or parsed.password:
        raise ValueError("server_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("server_url must not contain a query string or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("server_url must not contain a path")
    if (
        parsed.scheme == "http"
        and not allow_insecure_http
        and not _is_loopback(parsed.hostname)
    ):
        raise ValueError("remote HTTP requires allow_insecure_http=true; prefer HTTPS")
    return value


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class PowerContextClient:
    def __init__(
        self,
        *,
        server_url: str,
        api_token: str = "",
        timeout_seconds: float = 8.0,
        allow_insecure_http: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.server_url = validate_server_url(
            server_url,
            allow_insecure_http=allow_insecure_http,
        )
        self._api_token = str(api_token or "").strip()
        self._timeout_seconds = max(0.5, min(float(timeout_seconds), 60.0))
        self._transport = transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        expected_statuses: Iterable[int] = (200,),
    ) -> PowerContextResponse:
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"

        try:
            async with httpx.AsyncClient(
                base_url=self.server_url,
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, json=payload)
        except httpx.TimeoutException as exc:
            raise PowerContextError("PowerContext request timed out") from exc
        except httpx.HTTPError as exc:
            raise PowerContextError("PowerContext transport failed") from exc

        request_id = response.headers.get("X-PowerContext-Request-ID")
        try:
            body = response.json()
        except ValueError:
            body = None

        if response.status_code not in set(expected_statuses):
            error = body.get("error", {}) if isinstance(body, dict) else {}
            code = error.get("code") if isinstance(error, dict) else None
            message = error.get("message") if isinstance(error, dict) else None
            safe_message = str(message or "PowerContext request failed")[:500]
            if self._api_token:
                safe_message = safe_message.replace(self._api_token, "[REDACTED]")
            raise PowerContextError(
                safe_message,
                status_code=response.status_code,
                error_code=str(code) if code else None,
                request_id=request_id,
            )
        if not isinstance(body, dict):
            raise PowerContextError(
                "PowerContext returned a non-object JSON response",
                status_code=response.status_code,
                request_id=request_id,
            )
        return PowerContextResponse(data=body, request_id=request_id)

    async def liveness(self) -> PowerContextResponse:
        return await self.request("GET", "/health/live")

    async def capabilities(self) -> PowerContextResponse:
        return await self.request("GET", "/v1/capabilities")

    async def resolve_scope(
        self,
        *,
        explicit_scope_id: str | None,
        binding_keys: list[dict[str, str]],
        allow_default: bool,
    ) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/scope-bindings/resolve",
            payload={
                "explicit_scope_id": explicit_scope_id or None,
                "binding_keys": binding_keys,
                "allow_default": allow_default,
            },
        )

    async def set_scope_binding(
        self,
        *,
        key: dict[str, str],
        scope_id: str,
    ) -> PowerContextResponse:
        return await self.request(
            "PUT",
            "/v1/scope-bindings",
            payload={"key": key, "scope_id": scope_id},
        )

    async def clear_scope_binding(self, *, key: dict[str, str]) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/scope-bindings/clear",
            payload={"key": key},
        )

    async def prepare_context(
        self,
        *,
        scope_id: str,
        query: str,
        max_bytes: int,
    ) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/context/prepare",
            payload={"scope_id": scope_id, "query": query, "max_bytes": max_bytes},
        )

    async def capture_content(
        self,
        *,
        scope_id: str,
        source_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/sources/content",
            payload={
                "scope_id": scope_id,
                "source_id": source_id,
                "content": content,
                "metadata": metadata,
            },
            expected_statuses=(202,),
        )

    async def remember(
        self,
        *,
        scope_id: str,
        kind: str,
        text: str,
        reason: str | None = None,
    ) -> PowerContextResponse:
        payload: dict[str, Any] = {"scope_id": scope_id, "kind": kind, "text": text}
        if reason:
            payload["reason"] = reason
        return await self.request("POST", "/v1/memory/remember", payload=payload)

    async def search_memory(
        self,
        *,
        scope_id: str,
        query: str,
        limit: int,
        mode: str = "auto",
    ) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/memory/search",
            payload={
                "scope_id": scope_id,
                "query": query,
                "limit": limit,
                "mode": mode,
            },
        )

    async def list_memory(
        self,
        *,
        scope_id: str,
        include_inactive: bool = False,
    ) -> PowerContextResponse:
        return await self.request(
            "POST",
            "/v1/memory/entries/list",
            payload={"scope_id": scope_id, "include_inactive": include_inactive},
        )

    async def retire_memory(
        self,
        *,
        scope_id: str,
        citation: dict[str, Any],
        reason: str | None = None,
    ) -> PowerContextResponse:
        payload: dict[str, Any] = {"scope_id": scope_id, "citation": citation}
        if reason:
            payload["reason"] = reason
        return await self.request("POST", "/v1/memory/entries/retire", payload=payload)
