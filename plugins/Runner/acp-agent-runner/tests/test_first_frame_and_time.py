from __future__ import annotations

import types
from datetime import UTC

import pytest
from components.commands import session_commands
from components.commands.session_commands import _format_session_time
from components.runner import default as runner_module
from components.runner.default import DefaultRunner
from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import RunnerResult


@pytest.mark.parametrize(
    ("tz", "expected"),
    [
        ("Asia/Shanghai", "2026-11-08 10:16 CST"),
        ("UTC", "2026-11-08 02:16 UTC"),
        ("America/New_York", "2026-11-07 21:16 EST"),
    ],
)
def test_format_session_time_uses_tz_and_labels_zone(monkeypatch, tz, expected):
    monkeypatch.setenv("TZ", tz)
    assert _format_session_time("2026-11-08T02:16:33Z") == expected


def test_format_session_time_without_tz_uses_host_local_zone(monkeypatch):
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(session_commands, "_display_timezone", lambda: UTC)
    assert _format_session_time("2026-11-08T02:16:33Z") == "2026-11-08 02:16 UTC"


def test_format_session_time_falls_back_for_unparseable_and_naive_values(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Shanghai")
    assert _format_session_time("") == ""
    assert _format_session_time("not-a-time") == "not-a-time"
    assert _format_session_time("2026-11-08T02:16:33") == "2026-11-08 02:16"


class _FakeHub:
    def __init__(self, *, daemon_error: Exception | None = None):
        self.daemon_error = daemon_error

    async def start(self, **_kwargs):
        return None

    async def wait_for_daemon(self, *_args):
        if self.daemon_error is not None:
            raise self.daemon_error

    async def run_job(self, **_kwargs):
        chunk = MessageChunk(role="assistant", content="hi", all_content="hi", msg_sequence=1)
        yield RunnerResult.message_delta("run-1", chunk).model_dump(mode="json")


def _daemon_config(streaming: bool = True) -> dict:
    return {
        "streaming": streaming,
        "daemon_hub": {"host": "127.0.0.1", "port": 0, "token": "t"},
        "daemon_id": "daemon-1",
        "daemon_connect_timeout": 1,
        "mcp_bridge_enabled": False,
        "timeout": 5,
    }


async def _collect(runner: DefaultRunner, config: dict) -> list[RunnerResult]:
    ctx = types.SimpleNamespace(run_id="run-1")
    return [result async for result in runner._run_daemon(ctx, config, "hello", "")]


@pytest.mark.asyncio
async def test_run_daemon_emits_placeholder_before_first_frame(monkeypatch):
    monkeypatch.setattr(runner_module, "get_agent_runtime_daemon_hub", lambda *_a, **_k: _FakeHub())
    runner = DefaultRunner()
    monkeypatch.setattr(runner, "_daemon_payload", lambda *_a: {})

    results = await _collect(runner, _daemon_config())

    assert [r.type for r in results] == ["message.delta", "message.delta"]
    assert results[0].data["chunk"]["all_content"] == "⏳"
    assert results[1].data["chunk"]["all_content"] == "hi"


@pytest.mark.asyncio
async def test_run_daemon_skips_placeholder_when_not_streaming(monkeypatch):
    monkeypatch.setattr(runner_module, "get_agent_runtime_daemon_hub", lambda *_a, **_k: _FakeHub())
    runner = DefaultRunner()
    monkeypatch.setattr(runner, "_daemon_payload", lambda *_a: {})

    results = await _collect(runner, _daemon_config(streaming=False))

    assert [r.data["chunk"]["all_content"] for r in results] == ["hi"]


@pytest.mark.asyncio
async def test_run_daemon_emits_no_placeholder_when_daemon_is_offline(monkeypatch):
    hub = _FakeHub(daemon_error=TimeoutError("daemon offline"))
    monkeypatch.setattr(runner_module, "get_agent_runtime_daemon_hub", lambda *_a, **_k: hub)
    runner = DefaultRunner()
    emitted: list[RunnerResult] = []

    with pytest.raises(TimeoutError):
        async for result in runner._run_daemon(types.SimpleNamespace(run_id="run-1"), _daemon_config(), "hello", ""):
            emitted.append(result)

    assert emitted == []
