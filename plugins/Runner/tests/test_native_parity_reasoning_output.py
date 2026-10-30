"""Native output parity against real Runner/SDK, with offline vendor boundaries."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from langbot_plugin.api.entities.builtin.runner import (
    ActorContext,
    AgentEventContext,
    AgentInput,
    AgentResources,
    AgentRunState,
    AgentRuntimeContext,
    AgentTrigger,
    ConversationContext,
    DeliveryContext,
    RunnerContext,
)

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ("coze", "dashscope", "tbox")
MODES = ("coze", "dashscope", "dashscope-workflow", "tbox", "tbox-blocking")


@pytest.fixture
def parity_module_loader():
    """Plugins own separate pkg namespaces in production; restore test imports."""
    saved = {k: v for k, v in sys.modules.items() if k == "pkg" or k.startswith("pkg.")}

    def load(name):
        for k in list(sys.modules):
            if k == "pkg" or k.startswith("pkg."):
                del sys.modules[k]
        root = ROOT / f"{name}-agent"
        sys.path.insert(0, str(root))
        try:
            spec = importlib.util.spec_from_file_location(
                f"parity_output_{name}", root / "components/runner/default.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        finally:
            sys.path.remove(str(root))

    yield load
    for k in list(sys.modules):
        if k == "pkg" or k.startswith("pkg."):
            del sys.modules[k]
    sys.modules.update(saved)


def context(config, *, streaming=True):
    return RunnerContext(
        run_id="parity_output",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="fixture", event_type="message.received", source="test"),
        conversation=ConversationContext(conversation_id="local", session_id="local-session"),
        input=AgentInput(text="hello"),
        delivery=DeliveryContext(surface="test", supports_streaming=streaming),
        resources=AgentResources(),
        state=AgentRunState(conversation={"external.conversation_id": "remote"}),
        runtime=AgentRuntimeContext(metadata={"streaming_supported": streaming}),
        actor=ActorContext(actor_type="user", actor_id="parity-sender"),
        config=config,
    )


def event_type(event):
    return getattr(event.type, "value", str(event.type))


def messages(events):
    return [e.data["chunk"] for e in events if event_type(e) == "message.delta"]


async def collect(gen):
    return [e async for e in gen]


def drive(loader, monkeypatch, mode, config, pieces, reasoning="private-reasoning"):
    name = mode.split("-")[0]
    module = loader(name)
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.references_quote = kwargs.get("references_quote", "Source:")

        async def close(self):
            captured["closed"] = True

        async def chat_messages(self, **kwargs):
            captured["request"] = kwargs
            if reasoning:
                yield {"event": "conversation.message.delta", "data": {"reasoning_content": reasoning}}
            for piece in pieces:
                yield {"event": "conversation.message.delta", "data": {"content": piece}}
            yield {
                "event": "conversation.chat.completed",
                "data": {"conversation_id": "next", "usage": {"total_tokens": 9}},
            }

        async def iter_agent(self, **kwargs):
            captured["request"] = kwargs
            if reasoning:
                yield {"status_code": 200, "output": {"thoughts": [{"thought": reasoning}], "finish_reason": "null"}}
            for piece in pieces:
                yield {"status_code": 200, "output": {"text": piece, "finish_reason": "null"}}
            yield {
                "status_code": 200,
                "output": {"session_id": "next", "finish_reason": "stop"},
                "usage": {"total_tokens": 9},
            }

        async def iter_workflow(self, **kwargs):
            captured["request"] = kwargs
            for piece in pieces:
                yield {
                    "status_code": 200,
                    "output": {"workflow_message": {"message": {"content": piece}}, "finish_reason": "null"},
                }
            yield {
                "status_code": 200,
                "output": {"session_id": "next", "finish_reason": "stop"},
                "usage": {"total_tokens": 9},
            }

        async def chat(self, **kwargs):
            captured["request"] = kwargs
            if kwargs["stream"]:
                if reasoning:
                    yield {"type": "thinking", "payload": json.dumps({"ext_data": {"text": reasoning}})}
                for piece in pieces:
                    yield {"type": "chunk", "payload": {"text": piece, "conversationId": "next"}}
                yield {"type": "usage", "usage": {"total_tokens": 9}}
            else:
                yield {
                    "errorCode": "0",
                    "data": {
                        "conversationId": "next",
                        "reasoningContent": [{"text": reasoning}],
                        "result": [{"chunk": "".join(pieces)}],
                    },
                    "usage": {"total_tokens": 9},
                }

    attr = {"coze": "AsyncCozeClient", "dashscope": "DashScopeClient", "tbox": "AsyncTboxClient"}[name]
    monkeypatch.setattr(module, attr, Client)
    cfg = {"api-key": "fixture-only", "bot-id": "bot", "app-id": "app", **config}
    if mode == "dashscope-workflow":
        cfg["app-type"] = "workflow"
    if mode == "tbox-blocking":
        cfg["streaming"] = False
    events = asyncio.run(
        collect(object.__new__(module.DefaultRunner).run(context(cfg, streaming=not mode.endswith("blocking"))))
    )
    return events, captured


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("flag", [False, True, "absent"])
def test_output_split_think_boundaries_preserve_answer_and_tool_content(parity_module_loader, monkeypatch, mode, flag):
    pieces = [
        "prefix ",
        "<",
        "th",
        "ink",
        ">",
        "hidden-one",
        "</th",
        "ink>",
        "answer ",
        "<think/>",
        "hidden-two",
        "</think>",
        "<tool_call>keep-tool</tool_call>",
    ]
    cfg = {} if flag == "absent" else {"remove-think": flag}
    events, captured = drive(parity_module_loader, monkeypatch, mode, cfg, pieces)
    assert event_type(events[-1]) == "run.completed"
    chunks = messages(events)
    assert chunks and chunks[-1]["is_final"]
    text = chunks[-1]["content"]
    if flag is True:
        assert text == "prefix answer <tool_call>keep-tool</tool_call>"
        for chunk in chunks:
            assert not any(s in chunk["content"] for s in ("hidden", "private-reasoning", "<think", "🤔", "viewport"))
    else:
        assert "hidden-one" in text and "hidden-two" in text and "keep-tool" in text
        if mode != "dashscope-workflow":
            assert "private-reasoning" in text
    assert events[-1].usage.total_tokens == 9
    if mode == "dashscope":
        assert captured["request"]["enable_thinking"] is (flag is not True)
    key = "session_id" if mode.startswith("dashscope") else "conversation_id"
    assert captured["request"][key] == "remote"


@pytest.mark.parametrize("mode", MODES)
def test_remove_think_does_not_change_plain_text(parity_module_loader, monkeypatch, mode):
    pieces = ["  plain ", "<tool_call>keep</tool_call>", "<thi", "s is text ", "<"]
    events, _ = drive(parity_module_loader, monkeypatch, mode, {"remove-think": True}, pieces, reasoning="")
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["content"] == "".join(pieces)
    assert messages(events)[-1]["is_final"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("flag", [False, True])
def test_reasoning_only_is_successful_final_not_empty_error(parity_module_loader, monkeypatch, mode, flag):
    events, _ = drive(parity_module_loader, monkeypatch, mode, {"remove-think": flag}, ["<think>only-secret</think>"])
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["is_final"]
    assert (messages(events)[-1]["content"] == "") is flag


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("value", ["false", "true", 0, 1, None, [], {}])
def test_remove_think_rejects_non_boolean_before_vendor_call(parity_module_loader, monkeypatch, name, value):
    events, captured = drive(parity_module_loader, monkeypatch, name, {"remove-think": value}, ["answer"])
    assert [event_type(e) for e in events] == ["run.failed"]
    assert events[0].data["code"] == f"{name}.config_invalid"
    assert "remove-think" in events[0].data["error"]
    assert captured == {}


@pytest.mark.parametrize(
    "base", ["https://proxy.example/coze/v2", "http://127.0.0.1:18080/coze", "https://api.coze.com"]
)
def test_coze_custom_endpoint_config_preserves_exact_value(parity_module_loader, monkeypatch, base):
    events, captured = drive(parity_module_loader, monkeypatch, "coze", {"api-base": base}, ["ok"])
    assert event_type(events[-1]) == "run.completed"
    assert captured["init"]["api_base"] == base


@pytest.mark.parametrize(
    "base",
    [
        None,
        4,
        "",
        "file:///tmp/config",
        "https://user:password@proxy.example",
        "https://proxy.example?token=value",
        "https://proxy.example/#fragment",
        "https://proxy.example\n.evil",
    ],
)
def test_coze_invalid_endpoint_is_safe_config_failure(parity_module_loader, monkeypatch, base):
    events, captured = drive(parity_module_loader, monkeypatch, "coze", {"api-base": base}, ["ok"])
    assert [event_type(e) for e in events] == ["run.failed"]
    assert events[0].data["code"] == "coze.config_invalid"
    assert "password" not in events[0].data["error"] and "token=value" not in events[0].data["error"]
    assert captured == {}


@pytest.mark.parametrize("value", ["false", "true", 0, 1, None])
def test_coze_auto_save_history_rejects_non_boolean(parity_module_loader, monkeypatch, value):
    events, captured = drive(parity_module_loader, monkeypatch, "coze", {"auto-save-history": value}, ["ok"])
    assert [event_type(e) for e in events] == ["run.failed"]
    assert events[0].data["code"] == "coze.config_invalid"
    assert captured == {}


@pytest.mark.parametrize("name", PLUGINS)
@pytest.mark.parametrize("value", [None, True, 0, -1, "invalid", float("inf"), float("nan")])
def test_invalid_timeout_is_config_failure_not_crash(parity_module_loader, monkeypatch, name, value):
    events, captured = drive(parity_module_loader, monkeypatch, name, {"timeout": value}, ["ok"])
    assert [event_type(e) for e in events] == ["run.failed"]
    assert events[0].data["code"] == f"{name}.config_invalid"
    assert captured == {}


@pytest.mark.parametrize("mode", ["coze", "dashscope", "tbox", "tbox-blocking"])
@pytest.mark.parametrize("flag", [False, True])
def test_only_separate_reasoning_field_completes(parity_module_loader, monkeypatch, mode, flag):
    events, _ = drive(parity_module_loader, monkeypatch, mode, {"remove-think": flag}, [])
    assert event_type(events[-1]) == "run.completed"
    chunks = messages(events)
    assert chunks[-1]["is_final"]
    assert (chunks[-1]["content"] == "") is flag


@pytest.mark.parametrize("mode", MODES)
def test_unclosed_nested_thinking_never_leaks(parity_module_loader, monkeypatch, mode):
    events, _ = drive(
        parity_module_loader,
        monkeypatch,
        mode,
        {"remove-think": True},
        ["answer", "<think>hidden", "<think>nested-hidden</think>", "tail-hidden"],
    )
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["content"] == "answer"
    assert all("hidden" not in c["content"] for c in messages(events))


@pytest.mark.parametrize("mode", ["coze", "dashscope"])
def test_provider_specific_thinking_markup(parity_module_loader, monkeypatch, mode):
    start, end = ("🤔", "💬") if mode == "coze" else ("႑", "႐")
    events, _ = drive(
        parity_module_loader, monkeypatch, mode, {"remove-think": True}, [start, "hidden", end, "answer"], reasoning=""
    )
    assert messages(events)[-1]["content"] == "answer"


@pytest.mark.parametrize("name", PLUGINS)
def test_response_limit_counts_suppressed_reasoning(parity_module_loader, monkeypatch, name):
    events, _ = drive(
        parity_module_loader, monkeypatch, name, {"remove-think": True}, ["ok"], reasoning="x" * (1024 * 1024 + 1)
    )
    assert event_type(events[-1]) == "run.failed"
    assert events[-1].data["code"] == f"{name}.response_limit"


def mock_vendor(module, call, monkeypatch):
    """Substitute child transport, retaining real client parsing and runner logic."""

    async def stream(payload, **kwargs):
        result = call(**payload["kwargs"])
        if isinstance(result, dict):
            yield result
        else:
            for item in result:
                yield item

    monkeypatch.setattr(module, "vendor_stream", stream)


@pytest.mark.parametrize("name", ["coze", "tbox"])
def test_upload_rejects_native_oversize_before_network(parity_module_loader, monkeypatch, name):
    parity_module_loader(name)
    module = sys.modules[f"pkg.{name}_client"]
    cls = module.AsyncCozeClient if name == "coze" else module.AsyncTboxClient
    client = cls(api_key="fixture-only")

    def forbidden(*args, **kwargs):
        raise AssertionError("network must not be reached")

    if name == "coze":
        monkeypatch.setattr(module.aiohttp, "ClientSession", forbidden)
    else:
        monkeypatch.setattr(module, "vendor_stream", forbidden)
    with pytest.raises(Exception) as exc:
        asyncio.run(client.upload_file(b"x" * (10 * 1024 * 1024 + 1), "fixture.png"))
    assert getattr(exc.value, "code", None) == f"{name}.input_error"


def test_tbox_delivery_selects_nonstreaming(parity_module_loader):
    runner = object.__new__(parity_module_loader("tbox").DefaultRunner)
    ctx = context({"api-key": "fixture", "app-id": "app"}, streaming=False)
    ctx.runtime.metadata.clear()
    assert runner._should_stream(ctx) is False


@pytest.mark.parametrize("value", ["false", 0, None])
def test_tbox_streaming_flag_strict_boolean(parity_module_loader, monkeypatch, value):
    events, captured = drive(parity_module_loader, monkeypatch, "tbox", {"streaming": value}, ["ok"])
    assert [event_type(e) for e in events] == ["run.failed"]
    assert events[0].data["code"] == "tbox.config_invalid"
    assert captured == {}


def test_dashscope_native_workflow_text_fallback_and_client_inputs(parity_module_loader, monkeypatch):
    module = parity_module_loader("dashscope")
    client_module = sys.modules["pkg.dashscope_client"]
    captured = {}

    def call(**kwargs):
        captured.update(kwargs)
        return iter(
            [
                {
                    "status_code": 200,
                    "output": {"text": "<think>hidden</think>answer <ref>[1]</ref>", "finish_reason": "null"},
                },
                {
                    "status_code": 200,
                    "output": {
                        "doc_references": [{"index_id": "1", "doc_name": "manual"}],
                        "session_id": "next",
                        "finish_reason": "stop",
                    },
                },
            ]
        )

    mock_vendor(client_module, call, monkeypatch)
    ctx = context(
        {
            "api-key": "fixture",
            "app-id": "app",
            "app-type": "workflow",
            "remove-think": True,
            "references_quote": "Source:",
        }
    )
    # Use the real async client; only the process transport is substituted.
    events = asyncio.run(collect(object.__new__(module.DefaultRunner).run(ctx)))
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["content"] == "answer (Source: manual)"
    assert captured["stream"] is True and captured["incremental_output"] is True
    assert captured["flow_stream_mode"] == "message_format"
    assert captured["session_id"] == "remote" and captured["biz_params"] == {}


@pytest.mark.parametrize("flag", [False, True])
def test_dashscope_real_client_disable_request_thought_flags(parity_module_loader, monkeypatch, flag):
    module = parity_module_loader("dashscope")
    client_module = sys.modules["pkg.dashscope_client"]
    captured = {}

    def call(**kwargs):
        captured.update(kwargs)
        return iter([{"status_code": 200, "output": {"text": "answer", "finish_reason": "stop"}}])

    mock_vendor(client_module, call, monkeypatch)
    events = asyncio.run(
        collect(
            object.__new__(module.DefaultRunner).run(
                context({"api-key": "fixture", "app-id": "app", "remove-think": flag})
            )
        )
    )
    assert event_type(events[-1]) == "run.completed"
    assert captured["enable_thinking"] is (not flag)
    assert captured["has_thoughts"] is (not flag)


@pytest.mark.parametrize("flag", [False, True])
def test_coze_real_client_preserves_custom_path_and_history(parity_module_loader, monkeypatch, flag):
    module = parity_module_loader("coze")
    captured = {}

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def content(self):
            async def lines():
                yield b"event: conversation.message.delta\n"
                yield b'data: {"content":"<think>hidden</think>answer"}\n'
                yield b"\n"

            return lines()

    class Session:
        def post(self, url, **kwargs):
            captured.update(url=url, **kwargs)
            return Response()

    async def session(self):
        return Session()

    monkeypatch.setattr(module.AsyncCozeClient, "_get_session", session)
    cfg = {
        "api-key": "fixture",
        "bot-id": "exact-bot",
        "api-base": "https://proxy.example/coze/prefix",
        "auto-save-history": flag,
        "remove-think": True,
        "timeout": 37.5,
    }
    events = asyncio.run(collect(object.__new__(module.DefaultRunner).run(context(cfg))))
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["content"] == "answer"
    assert captured["url"] == "https://proxy.example/coze/prefix/v3/chat"
    assert captured["json"]["auto_save_history"] is flag
    assert captured["json"]["bot_id"] == "exact-bot"
    assert captured["params"] == {"conversation_id": "remote"}
    assert captured["timeout"].total == 37.5


@pytest.mark.parametrize("mode", MODES)
def test_text_limit_counts_chunks_before_filter(parity_module_loader, monkeypatch, mode):
    events, _ = drive(
        parity_module_loader,
        monkeypatch,
        mode,
        {"remove-think": True},
        ["<think>", "x" * (1024 * 1024), "</think>answer"],
        reasoning="",
    )
    name = mode.split("-")[0]
    assert event_type(events[-1]) == "run.failed"
    assert events[-1].data["code"] == f"{name}.response_limit"


def test_dashscope_reference_count_is_bounded(parity_module_loader):
    parity_module_loader("dashscope")
    module = sys.modules["pkg.dashscope_client"]
    refs = module.extract_references_from_chunk(
        {"doc_references": [{"index_id": str(i), "doc_name": "fixture"} for i in range(1025)]}
    )
    assert len(refs) == 1024


@pytest.mark.parametrize("mode", ["oversize-event", "oversize-total"])
def test_coze_sse_transport_limits(parity_module_loader, monkeypatch, mode):
    module = parity_module_loader("coze")

    class Response:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @property
        def content(self):
            async def lines():
                if mode == "oversize-event":
                    yield b":" + b"x" * (1024 * 1024) + b"\n"
                else:
                    for _ in range(18):
                        yield b":" + b"x" * (1024 * 1024 - 2) + b"\n"

            return lines()

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    async def session(self):
        return Session()

    monkeypatch.setattr(module.AsyncCozeClient, "_get_session", session)
    events = asyncio.run(
        collect(object.__new__(module.DefaultRunner).run(context({"api-key": "fixture", "bot-id": "bot"})))
    )
    assert events[-1].data["code"] == "coze.response_limit"


@pytest.mark.parametrize("streaming", [False, True])
def test_tbox_actual_client_request_fields(parity_module_loader, monkeypatch, streaming):
    module = parity_module_loader("tbox")
    captured = {}

    class SDKClient:
        def chat(self, **kwargs):
            captured.update(kwargs)
            response = {
                "errorCode": "0",
                "data": {
                    "result": [{"chunk": "answer"}],
                    "reasoningContent": [{"text": "hidden"}],
                    "conversationId": "next",
                },
            }
            if not kwargs["stream"]:
                return response
            return iter(
                [
                    {"type": "thinking", "payload": json.dumps({"ext_data": {"text": "hidden"}})},
                    {"type": "chunk", "payload": {"text": "answer", "conversationId": "next"}},
                ]
            )

    mock_vendor(sys.modules["pkg.tbox_client"], SDKClient().chat, monkeypatch)
    ctx = context({"api-key": "fixture", "app-id": "exact-app", "remove-think": True}, streaming=streaming)
    events = asyncio.run(collect(object.__new__(module.DefaultRunner).run(ctx)))
    assert event_type(events[-1]) == "run.completed"
    assert messages(events)[-1]["content"] == "answer"
    assert captured["app_id"] == "exact-app" and captured["query"] == "hello"
    assert captured["stream"] is streaming and captured["conversation_id"] == "remote"
    assert captured["files"] is None
