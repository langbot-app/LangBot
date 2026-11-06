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

    def __init__(self, *, reply_after_polls: int = 1, outcome: str = "reply", queued_polls: int = 0):
        self.sessions: dict[str, dict] = {}
        self.queued_polls = queued_polls
        self.reply_content: str | None = None
        self.status_polls = 0
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
                        {
                            "role": "assistant",
                            "content": self.reply_content or f"echo:{session['agent_id']}",
                            "task_id": task_id,
                        }
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
            self.status_polls += 1
            status = "queued" if self.status_polls <= self.queued_polls else "running"
            return httpx.Response(200, json={"task_id": session["pending"][0], "status": status})
        return httpx.Response(405)


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch):
    clock = {"now": 1000.0}

    async def advance(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(runner_module, "_sleep", advance)
    monkeypatch.setattr(runner_module, "_monotonic", lambda: clock["now"])


class FakePlugin:
    """Stands in for MulticaAgentPlugin: the plugin-level language comes from installation config."""

    def __init__(self, language: str | None):
        self.language = language

    def get_language(self) -> str:
        return self.language or "en_US"


def make_runner(fake: FakeMultica, language: str | None = None):
    runner = object.__new__(runner_module.DefaultRunner)
    if language is not None:
        runner.plugin = FakePlugin(language)
    transport = httpx.MockTransport(fake.handler)

    def make_client(config):
        return AsyncMulticaClient(config["server_url"], config["token"], config["workspace_id"], transport=transport)

    runner._make_client = make_client
    return runner


def make_ctx(text: str, state: dict | None = None, **config) -> RunnerContext:
    base = {"api-token": "mul_test", "workspace-id": "ws-1", "agent-id": "agent-1", "progress-mode": "off"}
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


# ------------------------------------------------------------ 0.2.0: agent by name


def completed_texts(results):
    return [r.data["message"]["content"] for r in results if kinds([r])[0] == "message.completed"]


def agent_list_calls(fake):
    return sum(1 for m, p, _ in fake.requests if m == "GET" and p == "/api/agents")


def test_agent_name_is_resolved_and_cached_in_state():
    fake = FakeMultica()
    runner = make_runner(fake)
    first = run(runner, make_ctx("hi", **{"agent-id": "", "agent": "coder"}))
    assert text_of(first) == "echo:agent-1"
    assert states(first)["multica.agent_resolved"] == {"query": "coder", "id": "agent-1", "name": "Coder"}

    second = run(runner, make_ctx("again", states(first), **{"agent-id": "", "agent": "coder"}))
    assert text_of(second) == "echo:agent-1"
    assert agent_list_calls(fake) == 1  # later turns reuse the resolved id


def test_agent_uuid_skips_agent_lookup():
    agent_uuid = "f181e798-3a0c-4fff-a62e-263291b5529b"
    fake = FakeMultica()
    results = run(make_runner(fake), make_ctx("hi", **{"agent-id": "", "agent": agent_uuid}))
    assert text_of(results) == f"echo:{agent_uuid}"
    assert agent_list_calls(fake) == 0


def test_agent_field_wins_over_deprecated_agent_id():
    results = run(make_runner(FakeMultica()), make_ctx("hi", **{"agent-id": "agent-1", "agent": "writer"}))
    assert text_of(results) == "echo:agent-2"


def test_ambiguous_agent_name_fails_with_numbered_candidates():
    fake = FakeMultica()
    results = run(make_runner(fake, "zh_Hans"), make_ctx("hi", **{"agent-id": "", "agent": "er"}))
    assert results[-1].data["code"] == "multica.agent_ambiguous"
    error = results[-1].data["error"]
    assert "1) Coder [agent-1]" in error and "2) Writer [agent-2]" in error
    assert "/multica use <序号>" in error
    assert [i["id"] for i in states(results)["multica.agent_choices"]["items"]] == ["agent-1", "agent-2"]
    assert not any(p.startswith("/api/chat") for _, p, _ in fake.requests)  # never picks one silently


def test_unknown_agent_name_lists_visible_agents():
    results = run(make_runner(FakeMultica()), make_ctx("hi", **{"agent-id": "", "agent": "nobody"}))
    assert results[-1].data["code"] == "multica.agent_not_found"
    assert "Coder, Writer" in results[-1].data["error"]
    assert "Old" not in results[-1].data["error"]


def test_use_number_picks_from_last_ambiguous_candidates():
    runner = make_runner(FakeMultica())
    failed = run(runner, make_ctx("hi", **{"agent-id": "", "agent": "er"}))
    state = states(failed)

    switched = run(runner, make_ctx("/multica use 2", state, **{"agent-id": "", "agent": "er"}))
    assert "Writer" in text_of(switched)
    state.update(states(switched))
    assert state["multica.agent_id"] == "agent-2"
    assert text_of(run(runner, make_ctx("hello", state, **{"agent-id": "", "agent": "er"}))) == "echo:agent-2"


def test_use_number_from_agents_listing():
    runner = make_runner(FakeMultica())
    listed = run(runner, make_ctx("/multica agents"))
    assert "1) Coder [agent-1] (current)" in text_of(listed)
    switched = run(runner, make_ctx("/multica use 2", states(listed)))
    assert states(switched)["multica.agent_id"] == "agent-2"
    assert states(switched)["multica.agent_name"] == "Writer"


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"multica.agent_choices": {"items": [{"id": "agent-2", "name": "Writer"}], "expires_at": 0}},
        {"multica.agent_choices": {"items": [{"id": "agent-2", "name": "Writer"}], "expires_at": 10**12}},
    ],
    ids=["no-list", "expired", "out-of-range"],
)
def test_invalid_use_number_never_switches(state):
    number = "3" if state and state["multica.agent_choices"]["expires_at"] else "1"
    results = run(make_runner(FakeMultica(), "zh_Hans"), make_ctx(f"/multica use {number}", state))
    assert "无效或已过期" in text_of(results)
    assert "multica.agent_id" not in states(results)


def test_ambiguous_use_name_replies_with_numbered_candidates():
    results = run(make_runner(FakeMultica()), make_ctx("/multica use er"))
    reply = text_of(results)
    assert "1) Coder [agent-1]" in reply and "2) Writer [agent-2]" in reply
    assert "multica.agent_id" not in states(results)
    assert "multica.agent_choices" in states(results)


@pytest.mark.parametrize("verb", ["agents", "find"])
def test_agents_keyword_filters_by_name(verb):
    results = run(make_runner(FakeMultica()), make_ctx(f"/multica {verb} WRIT"))
    reply = text_of(results)
    assert "1) Writer [agent-2]" in reply
    assert "Coder" not in reply
    assert [i["id"] for i in states(results)["multica.agent_choices"]["items"]] == ["agent-2"]


def test_agents_keyword_without_match_suggests_names():
    results = run(make_runner(FakeMultica()), make_ctx("/multica find zzz"))
    assert "Available: Coder, Writer" in text_of(results)
    assert "multica.agent_choices" not in states(results)


def test_help_shows_new_commands_and_progress_mode():
    reply = text_of(run(make_runner(FakeMultica()), make_ctx("/multica", **{"progress-mode": "stream"})))
    assert "Progress mode: stream" in reply
    assert "/multica find <keyword>" in reply
    assert "/multica use <number, name or id>" in reply


# ------------------------------------------------------------ 0.2.0: progress


def test_messages_mode_reports_lifecycle_then_answer_last():
    fake = FakeMultica(reply_after_polls=20, queued_polls=2)
    ctx = make_ctx("hi", **{"progress-mode": "messages", "poll-interval": 2, "progress-interval": 15})
    results = run(make_runner(fake, "zh_Hans"), ctx)

    texts = completed_texts(results)
    assert texts == [
        "⏳ 已提交给 agent-1（任务 task-2）",
        "▶️ agent-1 开始执行",
        "⏱ 仍在执行 · 已等待 22s",
        "⏱ 仍在执行 · 已等待 38s",
        "echo:agent-1",
    ]
    assert kinds(results)[-1] == "run.completed"
    assert "message.delta" not in kinds(results)


def test_messages_mode_uses_resolved_agent_name():
    ctx = make_ctx("hi", **{"agent-id": "", "agent": "coder", "progress-mode": "messages"})
    texts = completed_texts(run(make_runner(FakeMultica(reply_after_polls=3), "zh_Hans"), ctx))
    assert texts[0].startswith("⏳ 已提交给 Coder（任务 ")
    assert texts[1] == "▶️ Coder 开始执行"
    assert texts[-1] == "echo:agent-1"


def test_messages_mode_is_the_default():
    ctx = make_ctx("hi")
    ctx.config.pop("progress-mode")
    assert len(completed_texts(run(make_runner(FakeMultica(reply_after_polls=3)), ctx))) == 3


def test_stream_mode_appends_to_one_message_and_ends_with_answer():
    fake = FakeMultica(reply_after_polls=20, queued_polls=2)
    ctx = make_ctx("hi", **{"progress-mode": "stream", "poll-interval": 2, "progress-interval": 15})
    results = run(make_runner(fake, "zh_Hans"), ctx)

    assert "message.completed" not in kinds(results)
    chunks = [r.data["chunk"] for r in results if kinds([r])[0] == "message.delta"]
    assert len(chunks) == 5
    accumulated = ""
    for chunk in chunks:
        accumulated += chunk["content"]
        assert chunk["all_content"] == accumulated
    assert [c["is_final"] for c in chunks] == [False, False, False, False, True]
    assert chunks[-1]["content"] == "\necho:agent-1"
    assert chunks[-1]["all_content"].startswith("⏳ 已提交给 agent-1")
    assert chunks[-1]["all_content"].endswith("\n\necho:agent-1")
    assert kinds(results)[-1] == "run.completed"


def test_off_mode_sends_only_the_answer():
    results = run(make_runner(FakeMultica(reply_after_polls=20)), make_ctx("hi", **{"progress-mode": "off"}))
    assert completed_texts(results) == ["echo:agent-1"]
    assert "message.delta" not in kinds(results)


@pytest.mark.parametrize(("timeout", "interval"), [(300, 30), (600, 5), (120, 60)])
def test_progress_interval_caps_message_count(timeout, interval):
    fake = FakeMultica(reply_after_polls=10**9)
    ctx = make_ctx(
        "hi", timeout=timeout, **{"progress-mode": "messages", "poll-interval": 1, "progress-interval": interval}
    )
    results = run(make_runner(fake), ctx)
    texts = completed_texts(results)
    heartbeats = [t for t in texts if t.startswith("⏱")]
    # submitted + started + heartbeats + final warning
    assert len(heartbeats) <= timeout // interval
    assert len(texts) <= 3 + timeout // interval
    assert len(heartbeats) >= timeout // interval - 2


def test_timeout_sends_closing_progress_before_failure():
    fake = FakeMultica(reply_after_polls=10**9)
    results = run(
        make_runner(fake, "zh_Hans"), make_ctx("hi", timeout=10, **{"progress-mode": "messages", "poll-interval": 1})
    )
    assert completed_texts(results)[-1] == "⚠️ 等待超时，任务仍在 Multica 中运行"
    assert results[-1].data["code"] == "multica.timeout"


def test_stream_mode_failure_closes_stream_before_run_failed():
    results = run(make_runner(FakeMultica(outcome="fail"), "zh_Hans"), make_ctx("hi", **{"progress-mode": "stream"}))
    chunk = [r.data["chunk"] for r in results if kinds([r])[0] == "message.delta"][-1]
    assert chunk["is_final"] is True
    assert chunk["all_content"].endswith("⚠️ agent-1 运行失败\n")
    assert results[-1].data["code"] == "multica.agent_failed"


def test_cancelled_task_closes_progress_before_failure():
    results = run(
        make_runner(FakeMultica(outcome="cancel"), "zh_Hans"), make_ctx("hi", **{"progress-mode": "messages"})
    )
    assert completed_texts(results)[-1].startswith("⚠️ 任务已结束但没有回复")
    assert results[-1].data["code"] == "multica.no_reply"


@pytest.mark.parametrize(("key", "value"), [("progress-mode", "loud"), ("progress-interval", 1)])
def test_invalid_progress_config_is_rejected(key, value):
    results = run(make_runner(FakeMultica()), make_ctx("hi", **{key: value}))
    assert results[-1].data["code"] == "multica.config_invalid"


# ------------------------------------------------------------ 0.2.0: plugin language

import yaml  # noqa: E402
from langbot_plugin.api.definition.plugin import NonePlugin  # noqa: E402
from pkg import i18n  # noqa: E402
from pkg.i18n import MESSAGES, SUPPORTED_LANGUAGES, get_text  # noqa: E402

LOCALES = list(SUPPORTED_LANGUAGES)
# Keys whose en_US and zh_Hans text may legitimately match (pure placeholders); none today.
SAME_IN_EN_AND_ZH: set[str] = set()


def test_manifest_language_option_matches_supported_locales():
    manifest = yaml.safe_load((PLUGIN_ROOT / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["metadata"]["version"] == "0.2.0"
    (language,) = [c for c in manifest["spec"]["config"] if c["name"] == "language"]
    assert language["type"] == "select" and language["default"] == "en_US"
    assert [o["name"] for o in language["options"]] == LOCALES
    assert "auto" not in [o["name"] for o in language["options"]]


def test_every_locale_defines_every_key():
    for locale in LOCALES:
        assert set(MESSAGES[locale]) == set(MESSAGES["en_US"]), locale


@pytest.mark.parametrize("locale", LOCALES)
def test_each_locale_renders_core_texts(locale):
    keys = ["progress.submitted", "use.ambiguous"] + [k for k in MESSAGES["en_US"] if k.startswith("help.")]
    args = {"agent": "A", "task_id": "t", "query": "q", "candidates": "1) A", "prefix": "/m", "session": "s"}
    args.update({"mode": "messages", "language": locale})
    for key in keys:
        text = get_text(locale, key, **args)
        assert text.strip() and text != key, (locale, key)
        assert "{" not in text, (locale, key)


def test_unknown_locale_falls_back_to_english():
    assert get_text("xx_XX", "new.ok") == MESSAGES["en_US"]["new.ok"]
    assert get_text(None, "progress.started", agent="A") == "▶️ A started"


def test_key_missing_in_locale_falls_back_to_english(monkeypatch):
    monkeypatch.delitem(i18n.MESSAGES["ja_JP"], "new.ok")
    assert get_text("ja_JP", "new.ok") == MESSAGES["en_US"]["new.ok"]
    assert get_text("ja_JP", "no.such.key") == "no.such.key"


def test_english_and_simplified_chinese_never_share_text():
    same = {k for k, v in MESSAGES["en_US"].items() if MESSAGES["zh_Hans"][k] == v}
    assert same == SAME_IN_EN_AND_ZH


@pytest.mark.parametrize("locale", LOCALES)
def test_agent_answer_passes_through_untranslated(locale):
    fake = FakeMultica(reply_after_polls=3)
    fake.reply_content = "Answer with {agent} braces, 中文 and progress.started"
    for mode in ("messages", "off"):
        texts = completed_texts(run(make_runner(fake, locale), make_ctx("hi", **{"progress-mode": mode})))
        assert texts[-1] == fake.reply_content


@pytest.mark.parametrize("locale", LOCALES)
def test_off_mode_is_unchanged_in_every_locale(locale):
    results = run(make_runner(FakeMultica(reply_after_polls=3), locale), make_ctx("hello"))
    assert kinds(results) == ["state.updated", "state.updated", "message.completed", "run.completed"]
    assert text_of(results) == "echo:agent-1"


@pytest.mark.parametrize("locale", LOCALES)
def test_progress_and_errors_follow_plugin_language(locale):
    ctx = make_ctx("hi", **{"progress-mode": "messages"})
    texts = completed_texts(run(make_runner(FakeMultica(reply_after_polls=3), locale), ctx))
    assert texts[0] == get_text(locale, "progress.submitted", agent="agent-1", task_id="task-2")

    failed = run(make_runner(FakeMultica(outcome="fail"), locale), make_ctx("hi"))
    # Localized shell, Multica's own failure text appended verbatim.
    assert failed[-1].data["error"] == get_text(locale, "error.agent_failed", detail="runtime offline")

    bad = run(make_runner(FakeMultica(), locale), make_ctx("hi", **{"api-token": ""}))
    assert bad[-1].data["error"] == get_text(locale, "config.api_token_required")


def test_help_reports_language():
    reply = text_of(run(make_runner(FakeMultica(), "ja_JP"), make_ctx("/multica")))
    assert "言語：ja_JP" in reply
    assert "進捗表示：off" in reply


def test_language_falls_back_to_installation_config_without_plugin_class():
    runner = make_runner(FakeMultica())
    runner.plugin = NonePlugin()
    runner.get_plugin_config = lambda: {"language": "ru_RU"}
    assert "Использование" in text_of(run(runner, make_ctx("/multica use")))

    runner.get_plugin_config = lambda: {"language": "xx_XX"}
    assert text_of(run(runner, make_ctx("/multica use"))) == "Usage: /multica use <number, name or id>"


def test_plugin_get_language_reads_invocation_config():
    spec = importlib.util.spec_from_file_location("multica_main", PLUGIN_ROOT / "main.py")
    main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_module)
    plugin = main_module.MulticaAgentPlugin()
    assert plugin.get_language() == "en_US"
    plugin.config = {"language": "vi_VN"}
    assert plugin.get_language() == "vi_VN"
    plugin.config = {"language": "auto"}
    assert plugin.get_language() == "en_US"


def test_find_without_keyword_shows_usage():
    assert (
        text_of(run(make_runner(FakeMultica(), "zh_Hans"), make_ctx("/multica find"))) == "用法：/multica find <关键词>"
    )
