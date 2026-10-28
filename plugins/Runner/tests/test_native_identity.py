"""Identity compatibility uses real SDK context, never business parameters."""

from __future__ import annotations

import pytest
from langbot_plugin.api.entities.builtin.runner import ActorContext, AdapterContext, ConversationContext

from tests.test_native_parity_external import collect, ctx, kind, load_runner

PLUGINS = ("dify", "coze", "n8n", "tbox")


def deny_upstream(module, name, monkeypatch):
    def denied(**kwargs):
        pytest.fail("Identity validation must precede upstream client construction")

    monkeypatch.setattr(
        module,
        {"dify": "AsyncDifyClient", "coze": "AsyncCozeClient", "n8n": "AsyncN8nClient", "tbox": "AsyncTboxClient"}[
            name
        ],
        denied,
    )


def make_context(name, source, scope="group"):
    context = ctx(
        {
            "api-key": "fixture",
            "bot-id": "vendor-bot",
            "app-id": "app",
            "webhook-url": "https://fixture.invalid",
            "user-id-source": source,
        }
    )
    context.actor = ActorContext(actor_type="user", actor_id="sender-9")
    context.conversation = ConversationContext(
        conversation_id="host-only", launcher_type=scope, launcher_id="target-7", bot_id="trusted-bot"
    )
    context.adapter = AdapterContext(
        extra={"params": {"user_id": "forged", "bot_id": "forged", "launcher_id": "forged"}}
    )
    return context


def identity(runner, context):
    method = getattr(runner, "_get_user_tag", None) or runner._get_user_id
    return method(context)


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("scope", ["group", "person"])
def test_native_identity_exact_and_default_unchanged(name, scope):
    source = "legacy-bot" if name == "tbox" else "legacy-session"
    with load_runner(name + "-agent") as (_, runner):
        context = make_context(name, source, scope)
        assert identity(runner, context) == ("trusted-bot" if name == "tbox" else f"{scope}_target-7")
        context.config.pop("user-id-source")
        assert identity(runner, context) == "user_sender-9"


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("bad", [None, "", "unknown", "legacy-bot", "legacy-session", 7, True])
def test_invalid_mode_fails_before_upstream(name, bad, monkeypatch):
    valid = "legacy-bot" if name == "tbox" else "legacy-session"
    if bad == valid:
        with load_runner(name + "-agent") as (_, runner):
            assert runner._validate_config(make_context(name, bad))
        return
    with load_runner(name + "-agent") as (module, runner):
        deny_upstream(module, name, monkeypatch)
        events = collect(runner.run(make_context(name, bad)))
        assert [kind(e) for e in events] == ["run.failed"]
        assert events[0].data["code"] == f"{name}.config_invalid"


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("missing", ["conversation", "id", "type"])
def test_missing_identity_fails_safe_without_sender_or_params_fallback(name, missing, monkeypatch):
    source = "legacy-bot" if name == "tbox" else "legacy-session"
    with load_runner(name + "-agent") as (module, runner):
        deny_upstream(module, name, monkeypatch)
        context = make_context(name, source)
        if missing == "conversation":
            context.conversation = None
        elif name == "tbox":
            context.conversation.bot_id = None
        elif missing == "id":
            context.conversation.launcher_id = ""
        else:
            context.conversation.launcher_type = "channel"
        events = collect(runner.run(context))
        assert [kind(e) for e in events] == ["run.failed"]
        assert events[0].data["code"] == f"{name}.identity_unavailable"
        assert "forged" not in str(events)


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("scope", ["group", "person"])
@pytest.mark.parametrize("persisted", [False, True])
def test_actual_runner_sends_selected_identity_and_keeps_modern_state(name, scope, persisted, monkeypatch):
    captured = {}

    class Upstream:
        def __init__(self, **kwargs):
            pass

        async def close(self):
            pass

        async def chat_messages(self, **kwargs):
            captured.update(kwargs)
            if name == "dify":
                yield {"event": "message", "answer": "answer"}
                yield {"event": "message_end"}
            else:
                yield {"event": "conversation.message.delta", "data": {"content": "answer"}}
                yield {"event": "conversation.chat.completed", "data": {}}

        async def call_webhook(self, **kwargs):
            captured.update(kwargs["payload"])
            yield {"type": "json", "content": "answer"}

        async def chat(self, **kwargs):
            captured.update(kwargs)
            yield {"type": "chunk", "payload": {"text": "answer"}}

    with load_runner(name + "-agent") as (module, runner):
        monkeypatch.setattr(
            module,
            {"dify": "AsyncDifyClient", "coze": "AsyncCozeClient", "n8n": "AsyncN8nClient", "tbox": "AsyncTboxClient"}[
                name
            ],
            Upstream,
        )
        context = make_context(name, "legacy-bot" if name == "tbox" else "legacy-session", scope)
        saved = "89a463f6-0656-4b6d-8bb0-279ee47cd8b1"
        if persisted:
            context.state.conversation.update(
                {"external.conversation_id": saved, "external.session_id": "modern-session"}
            )
        events = collect(runner.run(context))
        assert "run.failed" not in [kind(e) for e in events], events
        assert "run.completed" in [kind(e) for e in events]
        assert captured["user" if name == "dify" else "user_id"] == (
            "trusted-bot" if name == "tbox" else f"{scope}_target-7"
        )
        if persisted:
            assert captured["conversation_id"] == saved
            if name == "n8n":
                assert captured["session_id"] == "modern-session"
        else:
            assert captured.get("conversation_id") != "host-only"
            if name == "n8n":
                assert captured["conversation_id"].startswith("n8n_conversation_")
                assert captured["session_id"].startswith("n8n_session_")


def test_tbox_nonconversation_run_uses_host_runtime_bot_not_config():
    with load_runner("tbox-agent") as (_, runner):
        context = make_context("tbox", "legacy-bot")
        context.conversation = None
        context.runtime.metadata["bot_id"] = "host-bot"
        context.config["bot_id"] = "forged-bot"
        assert identity(runner, context) == "host-bot"
