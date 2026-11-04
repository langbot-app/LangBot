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
from pkg.http_limits import MAX_STREAM_BUDGET_MB, MAX_STREAM_BYTES, limited_bytes, limited_lines


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


@pytest.mark.asyncio
async def test_raised_budget_lifts_single_event_cap_proportionally():
    observation = "z" * (3 * 1024 * 1024)
    payload = (
        'data: {"event": "agent_thought", "tool": "read_file", "observation": "' + observation + '"}\n\n'
    ).encode()
    events = [event async for event in _iter_sse_json(FakeResponse([payload]), max_stream_bytes=64 * 1024 * 1024)]
    assert events[0]["observation"] == observation


@pytest.mark.asyncio
async def test_oversized_event_reports_its_size_and_limit():
    payload = b'data: {"event": "agent_thought", "observation": "' + b"z" * 64 + b'"}\n\n'
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in limited_lines(FakeResponse([payload]), DifyAPIError, max_stream_bytes=1024, max_line_bytes=32):
            pass
    assert "Provider event too large" in excinfo.value.message
    assert "limit is 32 bytes" in excinfo.value.message
    assert "runtime limit" not in excinfo.value.message


@pytest.mark.asyncio
async def test_budget_error_names_last_event_and_tool(caplog):
    first = b'data: {"event": "agent_thought", "tool": "get_class_source", "observation": ""}\n\n'
    second = b'data: {"event": "agent_thought", "observation": "' + b"y" * 200 + b'"}\n\n'
    with caplog.at_level("WARNING", logger="pkg.dify_client"):
        with pytest.raises(DifyAPIError) as excinfo:
            async for _ in _iter_sse_json(FakeResponse([first, second]), max_stream_bytes=len(first) + 10):
                pass
    assert excinfo.value.code == "dify.stream_limit_exceeded"
    assert "stream budget exceeded" in excinfo.value.message
    assert "last event: agent_thought, last tool: get_class_source" in excinfo.value.message
    assert "last tool: get_class_source" in caplog.text


@pytest.mark.asyncio
async def test_budget_error_names_workflow_node():
    first = b'data: {"event": "node_finished", "data": {"title": "Tool observation 3", "outputs": {}}}\n\n'
    second = b"data: " + b"x" * 100 + b"\n\n"
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in _iter_sse_json(FakeResponse([first, second]), max_stream_bytes=len(first) + 10):
            pass
    assert "last event: node_finished, last tool: Tool observation 3" in excinfo.value.message


@pytest.mark.asyncio
async def test_default_budget_keeps_native_1mib_event_cap():
    payload = b'data: {"event": "agent_thought", "observation": "' + b"z" * (1024 * 1024) + b'"}\n\n'
    with pytest.raises(DifyAPIError) as excinfo:
        async for _ in _iter_sse_json(FakeResponse([payload])):
            pass
    assert "limit is 1048576 bytes" in excinfo.value.message
