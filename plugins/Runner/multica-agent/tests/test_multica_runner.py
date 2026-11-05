"""Multica runner behavior against a simulated Multica HTTP API (httpx MockTransport)."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest
from langbot_plugin.api.entities.builtin.runner import (
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    DeliveryContext,
    RunnerContext,
)

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from pkg.multica_client import AsyncMulticaClient  # noqa: E402

spec = importlib.util.spec_from_file_location("multica_runner", PLUGIN_ROOT / "components/runner/default.py")
runner_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner_module)

AGENTS = [
    {"id": "agent-1", "name": "Coder", "archived_at": None},
    {"id": "agent-2", "name": "Writer", "archived_at": None},
    {"id": "agent-3", "name": "Old", "archived_at": "2026-01-01T00:00:00Z"},
]


class FakeMultica:
    """In-memory model of the Multica chat endpoints the runner uses."""

    def __init__(self, *, reply_after_polls: int = 1, outcome: str = "reply"):
        self.sessions: dict[str, dict] = {}
        self.requests: list[tuple[str, str, dict | None]] = []
        self.reply_after_polls = reply_after_polls
        self.outcome = outcome
        self.polls = 0
        self.deleted: set[str] = set()

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.requests.append((request.method, request.url.path, body))
        assert request.headers["authorization"] == "Bearer mul_test"
        assert request.headers["x-workspace-id"] == "ws-1"
        path = request.url.path

        if request.method == "GET" and path == "/api/agents":
            return httpx.Response(200, json=AGENTS)
        if request.method == "POST" and path == "/api/chat/sessions":
            session_id = f"session-{len(self.sessions) + 1}"
            self.sessions[session_id] = {"agent_id": body["agent_id"], "messages": [], "pending": []}
            return httpx.Response(201, json={"id": session_id, "agent_id": body["agent_id"]})

        parts = path.strip("/").split("/")
        session_id = parts[3]
        if session_id in self.deleted or session_id not in self.sessions:
            return httpx.Response(404, json={"error": "chat session not found"})
        session = self.sessions[session_id]
        tail = "/".join(parts[4:])

        if request.method == "POST" and tail == "messages":
            task_id = f"task-{len(self.requests)}"
            session["messages"].append({"role": "user", "content": body["content"], "task_id": None})
            session["pending"].append(task_id)
            self.polls = 0
            return httpx.Response(201, json={"message_id": "m", "task_id": task_id})
        if request.method == "GET" and tail == "messages/page":
            self.polls += 1
            if session["pending"] and self.polls >= self.reply_after_polls:
                task_id = session["pending"].pop(0)
                if self.outcome == "reply":
                    session["messages"].append(
                        {"role": "assistant", "content": f"echo:{session['agent_id']}", "task_id": task_id}
                    )
                elif self.outcome == "fail":
                    session["messages"].append(
                        {
                            "role": "assistant",
                            "content": "runtime offline",
                            "task_id": task_id,
                            "failure_reason": "agent_error",
                        }
                    )
                # outcome == "cancel": task disappears without a reply row
            return httpx.Response(200, json={"messages": session["messages"][-30:], "has_more": False})
        if request.method == "GET" and tail == "pending-task":
            if not session["pending"]:
                return httpx.Response(200, json={"supports_queue": True})
            return httpx.Response(200, json={"task_id": session["pending"][0], "status": "running"})
        return httpx.Response(405)


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch):
    clock = {"now": 1000.0}

    async def advance(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(runner_module, "_sleep", advance)
    monkeypatch.setattr(runner_module, "_monotonic", lambda: clock["now"])


def make_runner(fake: FakeMultica):
    runner = object.__new__(runner_module.DefaultRunner)
    transport = httpx.MockTransport(fake.handler)

    def make_client(config):
        return AsyncMulticaClient(config["server_url"], config["token"], config["workspace_id"], transport=transport)

    runner._make_client = make_client
    return runner


def make_ctx(text: str, state: dict | None = None, **config) -> RunnerContext:
    base = {"api-token": "mul_test", "workspace-id": "ws-1", "agent-id": "agent-1"}
    base.update(config)
    return RunnerContext(
        run_id="run-1",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="evt-1", event_type="message.received", source="test"),
        input=AgentInput(text=text),
        delivery=DeliveryContext(surface="test"),
        resources=AgentResources(),
        state=AgentRunState(conversation=state or {}),
        runtime=AgentRuntimeContext(),
        config=base,
    )


def run(runner, ctx):
    async def collect():
        return [r async for r in runner.run(ctx)]

    return asyncio.run(collect())


def kinds(results):
    return [str(getattr(r.type, "value", r.type)) for r in results]


def states(results):
    return {r.data["key"]: r.data["value"] for r in results if "state" in kinds([r])[0]}


def text_of(results):
    return next(r.data["message"]["content"] for r in results if kinds([r])[0] == "message.completed")


def test_first_message_creates_session_and_returns_agent_reply():
    fake = FakeMultica(reply_after_polls=3)
    results = run(make_runner(fake), make_ctx("hello"))

    assert text_of(results) == "echo:agent-1"
    assert kinds(results)[-1] == "run.completed"
    assert states(results) == {"multica.session_id": "session-1", "multica.session_agent_id": "agent-1"}
    assert ("POST", "/api/chat/sessions/session-1/messages", {"content": "hello"}) in fake.requests


def test_follow_up_reuses_stored_session():
    fake = FakeMultica()
    runner = make_runner(fake)
    first = run(runner, make_ctx("one"))
    second = run(runner, make_ctx("two", states(first)))

    assert text_of(second) == "echo:agent-1"
    assert states(second) == {}
    assert sum(1 for m, p, _ in fake.requests if m == "POST" and p == "/api/chat/sessions") == 1


def test_deleted_session_is_recreated_once():
    fake = FakeMultica()
    runner = make_runner(fake)
    first_state = states(run(runner, make_ctx("one")))
    fake.deleted.add(first_state["multica.session_id"])

    results = run(runner, make_ctx("two", first_state))
    assert text_of(results) == "echo:agent-1"
    assert states(results)["multica.session_id"] == "session-2"


def test_agent_failure_is_reported_as_run_failed():
    results = run(make_runner(FakeMultica(outcome="fail")), make_ctx("hi"))
    assert kinds(results)[-1] == "run.failed"
    assert results[-1].data["code"] == "multica.agent_failed"
    assert "runtime offline" in results[-1].data["error"]


def test_cancelled_task_without_reply_fails_cleanly():
    results = run(make_runner(FakeMultica(outcome="cancel")), make_ctx("hi"))
    assert results[-1].data["code"] == "multica.no_reply"


def test_timeout_when_agent_never_replies():
    results = run(make_runner(FakeMultica(reply_after_polls=10**9)), make_ctx("hi", timeout=10, **{"poll-interval": 1}))
    assert results[-1].data["code"] == "multica.timeout"
    assert results[-1].data["retryable"] is True


def test_agents_command_lists_unarchived_agents_and_marks_current():
    fake = FakeMultica()
    results = run(make_runner(fake), make_ctx("/multica agents"))
    reply = text_of(results)
    assert "Coder [agent-1] (current)" in reply
    assert "Writer [agent-2]" in reply
    assert "Old" not in reply
    assert not any(p.startswith("/api/chat") for _, p, _ in fake.requests)


def test_use_command_switches_agent_and_next_message_opens_new_session():
    fake = FakeMultica()
    runner = make_runner(fake)
    state = states(run(runner, make_ctx("one")))

    switched = run(runner, make_ctx("/multica use writer", state))
    assert "Writer" in text_of(switched)
    state.update(states(switched))
    assert state["multica.agent_id"] == "agent-2"

    reply = run(runner, make_ctx("two", state))
    assert text_of(reply) == "echo:agent-2"
    assert states(reply)["multica.session_agent_id"] == "agent-2"


def test_use_command_respects_disabled_switching():
    results = run(make_runner(FakeMultica()), make_ctx("/multica use writer", **{"allow-agent-switch": False}))
    assert "disabled" in text_of(results)
    assert "multica.agent_id" not in states(results)


def test_new_command_clears_session():
    results = run(make_runner(FakeMultica()), make_ctx("/multica new", {"multica.session_id": "s"}))
    assert states(results) == {"multica.session_id": "", "multica.session_agent_id": ""}


def test_prefix_must_be_a_whole_word():
    fake = FakeMultica()
    results = run(make_runner(fake), make_ctx("/multicaX hi"))
    assert text_of(results) == "echo:agent-1"


def test_missing_agent_and_token_are_config_errors():
    no_agent = run(make_runner(FakeMultica()), make_ctx("hi", **{"agent-id": ""}))
    assert no_agent[-1].data["code"] == "multica.config_invalid"
    no_token = run(make_runner(FakeMultica()), make_ctx("hi", **{"api-token": ""}))
    assert no_token[-1].data["code"] == "multica.config_invalid"


def test_unauthorized_token_surfaces_api_error():
    def deny(request):
        return httpx.Response(401, json={"error": "invalid token"})

    runner = object.__new__(runner_module.DefaultRunner)
    runner._make_client = lambda config: AsyncMulticaClient(
        config["server_url"], config["token"], config["workspace_id"], transport=httpx.MockTransport(deny)
    )
    results = run(runner, make_ctx("hi"))
    assert results[-1].data["code"] == "multica.unauthorized"
    assert "invalid token" in results[-1].data["error"]
