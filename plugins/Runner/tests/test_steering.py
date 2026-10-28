"""Tests for run-scoped steering (follow-up input) support in native runners.

The shared turn-loop lives in each plugin's ``pkg/steering.py`` (identical
copies). These tests exercise the loop logic directly and verify that each
native runner's ``run()`` wires the loop so follow-up input is drained at turn
boundaries, reusing the same agent session.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from langbot_plugin.api.entities.builtin.provider.message import MessageChunk
from langbot_plugin.api.entities.builtin.runner import (
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    ConversationContext,
    DeliveryContext,
    RunnerContext,
    RunnerResult,
)
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
    ContextAPICapabilities,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_plugin(plugin_dir: str):
    """Load a plugin's runner module and return its ``pkg`` submodules."""
    for module_name in list(sys.modules):
        if module_name == "pkg" or module_name.startswith("pkg."):
            del sys.modules[module_name]
    plugin_root = ROOT / plugin_dir
    sys.path.insert(0, str(plugin_root))
    try:
        module_path = plugin_root / "components" / "runner" / "default.py"
        spec = importlib.util.spec_from_file_location(
            f"test_steering_{plugin_dir.replace('-', '_')}_runner", module_path
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(plugin_root))


async def _collect(generator) -> list[RunnerResult]:
    return [item async for item in generator]


def _type(result: RunnerResult) -> str:
    return getattr(result.type, "value", str(result.type))


def _ctx(*, steering: bool, config: dict[str, Any] | None = None, text: str = "hello") -> RunnerContext:
    return RunnerContext(
        run_id="run_steering",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="evt_1", event_type="message.received", source="test"),
        conversation=ConversationContext(conversation_id="conv-1", session_id="sess-1"),
        input=AgentInput(text=text),
        delivery=DeliveryContext(surface="test", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(conversation={}),
        runtime=AgentRuntimeContext(),
        context=ContextAccess(available_apis=ContextAPICapabilities(steering_pull=steering)),
        config=config or {},
    )


class _FakeRunApi:
    """Returns queued steering batches, one per ``steering_pull`` call."""

    def __init__(self, batches: list[list[str]]) -> None:
        self._batches = batches
        self.calls = 0

    async def steering_pull(self, mode: str = "all", limit: int | None = None) -> SimpleNamespace:
        batch = self._batches[self.calls] if self.calls < len(self._batches) else []
        self.calls += 1
        items = [SimpleNamespace(input=AgentInput(text=text)) for text in batch]
        return SimpleNamespace(items=items)


def _steering_module():
    _load_plugin("codex-agent")
    return sys.modules["pkg.steering"]


# --------------------------------------------------------------------------- #
# Shared turn-loop (pkg/steering.py)
# --------------------------------------------------------------------------- #


def _make_turn_recorder(steering, session_key: str):
    """Build a fake single-turn executor that records its (prompt, resume) calls."""
    calls: list[tuple[str, str]] = []

    async def run_turn(prompt: str, resume_session_id: str):
        calls.append((prompt, resume_session_id))
        if len(calls) == 1:
            # First turn reports a freshly created session id.
            yield RunnerResult.state_updated("run_steering", session_key, "session-xyz", scope="conversation")
        yield RunnerResult.message_delta("run_steering", MessageChunk(role="assistant", content=f"reply:{prompt}"))
        yield RunnerResult.run_completed("run_steering", finish_reason="stop")

    return run_turn, calls


def test_steering_loop_drains_followups_and_resumes_session() -> None:
    steering = _steering_module()
    key = "external.session"
    run_turn, calls = _make_turn_recorder(steering, key)
    api = _FakeRunApi([["follow up one"], ["follow up two"], []])
    ctx = _ctx(steering=True)

    results = asyncio.run(
        _collect(
            steering.run_with_steering(
                ctx,
                lambda: api,
                run_turn,
                initial_prompt="hello",
                initial_resume_session_id="",
                session_state_key=key,
            )
        )
    )

    # Initial turn + two follow-ups; follow-ups resume the captured session id.
    assert calls == [
        ("hello", ""),
        ("follow up one", "session-xyz"),
        ("follow up two", "session-xyz"),
    ]
    # Exactly one terminal run.completed despite three turns.
    assert [_type(r) for r in results].count("run.completed") == 1
    assert _type(results[-1]) == "run.completed"
    # Each turn's assistant message is forwarded.
    assert sum(1 for r in results if _type(r) == "message.delta") == 3


def test_steering_loop_single_turn_when_disabled() -> None:
    steering = _steering_module()
    key = "external.session"
    run_turn, calls = _make_turn_recorder(steering, key)
    api = _FakeRunApi([["should-not-be-pulled"]])
    ctx = _ctx(steering=False)

    results = asyncio.run(
        _collect(
            steering.run_with_steering(
                ctx,
                lambda: api,
                run_turn,
                initial_prompt="hello",
                initial_resume_session_id="",
                session_state_key=key,
            )
        )
    )

    assert calls == [("hello", "")]
    assert api.calls == 0  # steering_pull never invoked when not authorized
    assert [_type(r) for r in results].count("run.completed") == 1


def test_steering_loop_stops_on_failed_turn_without_draining() -> None:
    steering = _steering_module()
    key = "external.session"
    api = _FakeRunApi([["never-pulled"]])
    ctx = _ctx(steering=True)

    async def failing_turn(prompt: str, resume_session_id: str):
        yield RunnerResult.message_delta("run_steering", MessageChunk(role="assistant", content="partial"))
        yield RunnerResult.run_failed("run_steering", error="boom", code="x.fail")

    results = asyncio.run(
        _collect(
            steering.run_with_steering(
                ctx,
                lambda: api,
                failing_turn,
                initial_prompt="hello",
                initial_resume_session_id="",
                session_state_key=key,
            )
        )
    )

    assert api.calls == 0  # failure short-circuits; no follow-up drain
    assert [_type(r) for r in results] == ["message.delta", "run.failed"]


def test_steering_loop_stops_on_action_request_without_completing() -> None:
    steering = _steering_module()
    api = _FakeRunApi([["never-pulled"]])
    ctx = _ctx(steering=True)

    async def pausing_turn(prompt: str, resume_session_id: str):
        yield RunnerResult.state_updated(
            "run_steering",
            "external.pending_interaction",
            {"interaction_id": "question-1"},
            scope="conversation",
        )
        yield RunnerResult.action_requested(
            "run_steering",
            "interaction.requested",
            {"interaction_id": "question-1"},
        )

    results = asyncio.run(
        _collect(
            steering.run_with_steering(
                ctx,
                lambda: api,
                pausing_turn,
                initial_prompt="hello",
                initial_resume_session_id="",
                session_state_key="external.session",
            )
        )
    )

    assert api.calls == 0
    assert [_type(r) for r in results] == ["state.updated", "action.requested"]


def test_steering_loop_survives_pull_errors() -> None:
    steering = _steering_module()
    key = "external.session"
    run_turn, calls = _make_turn_recorder(steering, key)
    ctx = _ctx(steering=True)

    class _RaisingApi:
        async def steering_pull(self, mode: str = "all", limit: int | None = None):
            raise RuntimeError("host unavailable")

    results = asyncio.run(
        _collect(
            steering.run_with_steering(
                ctx,
                lambda: _RaisingApi(),
                run_turn,
                initial_prompt="hello",
                initial_resume_session_id="",
                session_state_key=key,
            )
        )
    )

    # A failing pull must not break the otherwise-successful run.
    assert calls == [("hello", "")]
    assert [_type(r) for r in results].count("run.completed") == 1
    assert _type(results[-1]) == "run.completed"


# --------------------------------------------------------------------------- #
# Runner argv
# --------------------------------------------------------------------------- #


def test_claude_argv_uses_resume_to_continue_session() -> None:
    # Verified e2e: `claude -p --session-id <existing>` errors ("already in
    # use"); continuing a session requires `--resume`. New sessions still use
    # `--session-id` so the runner controls the id.
    module = _load_plugin("claude-code-agent")
    runner = object.__new__(module.DefaultRunner)
    config = {"command": "claude", "args": []}

    create = runner._argv(config, session_id="sid-1", mcp_config_path="", resume=False)
    assert "--session-id" in create and "sid-1" in create and "--resume" not in create

    cont = runner._argv(config, session_id="sid-1", mcp_config_path="", resume=True)
    assert "--resume" in cont and "sid-1" in cont and "--session-id" not in cont


# --------------------------------------------------------------------------- #
# Runner run() wiring
# --------------------------------------------------------------------------- #


def _patch_turn(runner, attr: str, session_key: str, *, emit_session: bool = True) -> list[tuple[str, str]]:
    """Replace a runner's single-turn executor with a recorder; return its calls."""
    calls: list[tuple[str, str]] = []

    async def fake_turn(ctx, config, prompt, resume_session_id, *args):
        calls.append((prompt, resume_session_id))
        if emit_session and len(calls) == 1:
            yield RunnerResult.state_updated(ctx.run_id, session_key, "session-xyz", scope="conversation")
        yield RunnerResult.message_delta(ctx.run_id, MessageChunk(role="assistant", content=f"reply:{prompt}"))
        yield RunnerResult.run_completed(ctx.run_id, finish_reason="stop")

    setattr(runner, attr, fake_turn)
    return calls


def test_codex_run_drains_steering() -> None:
    module = _load_plugin("codex-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner._plugin_config = {}
    runner._plugin_runtime_handler = None
    calls = _patch_turn(runner, "_run_local_or_ssh", native.SESSION_STATE_KEY)
    api = _FakeRunApi([["second message"], []])
    runner.get_run_api = lambda ctx: api

    ctx = _ctx(steering=True, config={"location": "local", "workspace": "/tmp", "command": "codex"})
    results = asyncio.run(_collect(runner.run(ctx)))

    assert calls == [("hello", ""), ("second message", "session-xyz")]
    assert [_type(r) for r in results].count("run.completed") == 1


def test_claude_run_drains_steering() -> None:
    module = _load_plugin("claude-code-agent")
    native = sys.modules["pkg.native_cli"]
    runner = object.__new__(module.DefaultRunner)
    runner._plugin_config = {}
    runner._plugin_runtime_handler = None
    calls = _patch_turn(runner, "_run_local_or_ssh", native.SESSION_STATE_KEY, emit_session=False)
    api = _FakeRunApi([["second message"], []])
    runner.get_run_api = lambda ctx: api

    ctx = _ctx(steering=True, config={"location": "local", "workspace": "/tmp", "command": "claude"})
    results = asyncio.run(_collect(runner.run(ctx)))

    # Claude generates a client-side session id, so follow-ups resume that id.
    assert len(calls) == 2
    assert calls[0][0] == "hello"
    assert calls[1][0] == "second message"
    assert calls[1][1] == calls[0][1]  # same session id reused across turns
    assert [_type(r) for r in results].count("run.completed") == 1


def test_acp_run_drains_steering() -> None:
    module = _load_plugin("acp-agent-runner")
    runner = object.__new__(module.DefaultRunner)
    runner._plugin_config = {}
    runner._plugin_runtime_handler = None
    calls = _patch_turn(runner, "_run_acp_turn", module.ACP_SESSION_STATE_KEY)
    api = _FakeRunApi([["second message"], []])
    runner.get_run_api = lambda ctx: api

    ctx = _ctx(
        steering=True,
        config={
            "provider": "claude-code",
            "location": "local",
            "workspace": "/tmp",
            "append-run-scope-prompt": False,
        },
    )
    results = asyncio.run(_collect(runner.run(ctx)))

    assert [prompt for prompt, _ in calls] == ["hello", "second message"]
    assert calls[1][1] == "session-xyz"  # follow-up resumes captured session id
    assert [_type(r) for r in results].count("run.completed") == 1
