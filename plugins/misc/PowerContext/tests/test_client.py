from __future__ import annotations

import httpx
import pytest

from powercontext_client import (
    PowerContextClient,
    PowerContextError,
    validate_server_url,
)


def test_server_url_rejects_remote_cleartext_by_default() -> None:
    with pytest.raises(ValueError, match="remote HTTP"):
        validate_server_url("http://powercontext.example:8000")


def test_server_url_allows_loopback_and_explicit_remote_http() -> None:
    assert validate_server_url("http://127.0.0.1:8000/") == "http://127.0.0.1:8000"
    assert (
        validate_server_url(
            "http://powercontext.example:8000", allow_insecure_http=True
        )
        == "http://powercontext.example:8000"
    )


@pytest.mark.asyncio
async def test_client_sends_bearer_and_preserves_request_id() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert request.url.path == "/v1/context/prepare"
        return httpx.Response(
            200,
            headers={"X-PowerContext-Request-ID": "req-1"},
            json={
                "schema": "powercontext.prepared-context.v1",
                "status": "empty",
                "content": None,
                "content_bytes": 0,
            },
        )

    client = PowerContextClient(
        server_url="http://localhost:8000",
        api_token="secret-token",
        transport=httpx.MockTransport(handler),
    )
    response = await client.prepare_context(
        scope_id="scope-1", query="hello", max_bytes=4000
    )

    assert response.request_id == "req-1"
    assert response.data["status"] == "empty"


@pytest.mark.asyncio
async def test_api_error_is_bounded_and_redacts_token() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-PowerContext-Request-ID": "req-denied"},
            json={
                "error": {
                    "code": "forbidden",
                    "message": "bad credential secret-token",
                }
            },
        )

    client = PowerContextClient(
        server_url="http://localhost:8000",
        api_token="secret-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PowerContextError) as captured:
        await client.liveness()

    summary = captured.value.safe_summary()
    assert "secret-token" not in summary
    assert "[REDACTED]" in summary
    assert "forbidden" in summary
    assert "req-denied" in summary


@pytest.mark.asyncio
async def test_source_capture_accepts_only_202_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/sources/content"
        return httpx.Response(
            202,
            json={
                "status": "accepted",
                "source": {
                    "source_type": "content",
                    "source_id": "turn-1",
                    "revision": 1,
                },
                "position": 1,
            },
        )

    client = PowerContextClient(
        server_url="http://localhost:8000",
        transport=httpx.MockTransport(handler),
    )
    response = await client.capture_content(
        scope_id="scope-1",
        source_id="turn-1",
        content="hello",
        metadata={"integration": "langbot"},
    )
    assert response.data["status"] == "accepted"
