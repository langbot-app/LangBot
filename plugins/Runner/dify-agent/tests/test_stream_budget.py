"""Configurable stream byte budget for Dify streaming responses.

Covers the runner-facing fix for the hardcoded 16 MiB SSE budget: the budget
must be configurable from the runner config, and the over-budget error must
report the actual byte count and the limit instead of the misleading
"runtime limit" wording.
"""

from types import SimpleNamespace

import pytest
from components.runner.default import DefaultRunner
from pkg.dify_client import AsyncDifyClient, DifyAPIError, DifyConfigError, _iter_sse_json
from pkg.http_limits import MAX_STREAM_BUDGET_MB, MAX_STREAM_BYTES, limited_bytes


class FakeResponse:
    """Minimal stand-in exposing only the aiter_bytes() surface the limiters use."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


def _runner_ctx(config: dict) -> SimpleNamespace:
    return SimpleNamespace(
        config=config,
        actor=SimpleNamespace(actor_id="u1", actor_type="person"),
        conversation=None,
        state=SimpleNamespace(conversation={}),
        run_id="run",
    )


@pytest.mark.asyncio
async def test_default_budget_still_rejects_over_16mib_stream():
    response = FakeResponse([b"x" * (MAX_STREAM_BYTES + 1)])
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in limited_bytes(response, DifyAPIError):
            pass
    assert "stream budget" in excinfo.value.message
    assert str(MAX_STREAM_BYTES) in excinfo.value.message


@pytest.mark.asyncio
async def test_stream_at_default_budget_passes():
    response = FakeResponse([b"x" * MAX_STREAM_BYTES])
    received = bytearray()
    async for chunk in limited_bytes(response, DifyAPIError):
        received.extend(chunk)
    assert len(received) == MAX_STREAM_BYTES


@pytest.mark.asyncio
async def test_custom_budget_overrides_default_and_reports_actual_bytes():
    response = FakeResponse([b"x" * 11])
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in limited_bytes(response, DifyAPIError, max_stream_bytes=10):
            pass
    assert "11 bytes received" in excinfo.value.message
    assert "limit is 10 bytes" in excinfo.value.message
    assert "runtime limit" not in excinfo.value.message


@pytest.mark.asyncio
async def test_custom_budget_above_default_allows_more_bytes():
    response = FakeResponse([b"x" * 20])
    received = bytearray()
    async for chunk in limited_bytes(response, DifyAPIError, max_stream_bytes=32):
        received.extend(chunk)
    assert len(received) == 20


@pytest.mark.asyncio
async def test_sse_iteration_honors_custom_budget():
    payload = b'data: {"event": "agent_thought", "observation": "' + b"y" * 40 + b'"}\n\n'
    response = FakeResponse([payload])
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in _iter_sse_json(response, max_stream_bytes=16):
            pass
    assert "stream budget" in excinfo.value.message


def test_client_stores_custom_budget():
    client = AsyncDifyClient(api_key="k", max_stream_bytes=64 * 1024 * 1024)
    assert client.max_stream_bytes == 64 * 1024 * 1024
    default_client = AsyncDifyClient(api_key="k")
    assert default_client.max_stream_bytes == MAX_STREAM_BYTES


def test_client_rejects_budget_above_safety_cap():
    with pytest.raises(ValueError, match="max_stream_bytes"):
        AsyncDifyClient(api_key="k", max_stream_bytes=(MAX_STREAM_BUDGET_MB + 1) * 1024 * 1024)


def _validate(runner_ctx, monkeypatch):
    monkeypatch.setattr("components.runner.default.scoped_identity", lambda runner, ctx, tag: tag)
    runner = SimpleNamespace()
    runner._get_user_tag = lambda ctx: "person_u1"
    return DefaultRunner._validate_config(runner, runner_ctx)


def test_runner_config_default_budget_is_16mib(monkeypatch):
    ctx = _runner_ctx({"api-key": "k", "base-url": "https://dify.example/v1", "app-type": "chat"})
    config = _validate(ctx, monkeypatch)
    assert config["stream_budget_bytes"] == 16 * 1024 * 1024


def test_runner_config_honors_custom_budget(monkeypatch):
    ctx = _runner_ctx(
        {
            "api-key": "k",
            "base-url": "https://dify.example/v1",
            "app-type": "chat",
            "stream-budget-mb": 64,
        }
    )
    config = _validate(ctx, monkeypatch)
    assert config["stream_budget_bytes"] == 64 * 1024 * 1024


def test_runner_config_rejects_non_positive_budget(monkeypatch):
    for bad in (0, -1):
        ctx = _runner_ctx(
            {
                "api-key": "k",
                "base-url": "https://dify.example/v1",
                "app-type": "chat",
                "stream-budget-mb": bad,
            }
        )
        with pytest.raises(DifyConfigError) as excinfo:
            _validate(ctx, monkeypatch)
        assert "positive integer" in excinfo.value.message


def test_runner_config_rejects_budget_above_safety_cap(monkeypatch):
    ctx = _runner_ctx(
        {
            "api-key": "k",
            "base-url": "https://dify.example/v1",
            "app-type": "chat",
            "stream-budget-mb": MAX_STREAM_BUDGET_MB + 1,
        }
    )
    with pytest.raises(DifyConfigError, match=str(MAX_STREAM_BUDGET_MB)):
        _validate(ctx, monkeypatch)


def test_runner_config_falls_back_to_default_for_garbage_budget(monkeypatch):
    ctx = _runner_ctx(
        {
            "api-key": "k",
            "base-url": "https://dify.example/v1",
            "app-type": "chat",
            "stream-budget-mb": "not-a-number",
        }
    )
    config = _validate(ctx, monkeypatch)
    assert config["stream_budget_bytes"] == 16 * 1024 * 1024
