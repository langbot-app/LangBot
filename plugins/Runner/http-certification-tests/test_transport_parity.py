"""Existing parity assertions adapted to the new process-transport boundary.

Provider replies are fixtures. Real child/SDK behavior is tested separately.
"""

import asyncio
import json
import sys
from contextlib import ExitStack
from pathlib import Path

import pytest
from test_isolation import load

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_native_parity_reasoning_output import collect, context, event_type, messages

TEXT_LIMIT = 1024 * 1024


@pytest.fixture
def parity_module_loader():
    with ExitStack() as stack:
        yield lambda name: stack.enter_context(load(name))[0]


def mock_vendor(module, call, monkeypatch):
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


@pytest.mark.parametrize("mode", ["agent", "workflow"])
@pytest.mark.parametrize("finished", [False, True])
def test_dashscope_rendered_citations_are_bounded(parity_module_loader, monkeypatch, mode, finished):
    module = parity_module_loader("dashscope")
    client_module = sys.modules["pkg.dashscope_client"]
    output = {"text": "<ref>[1]</ref>" * 3, "doc_references": [{"index_id": "1", "doc_name": "x" * (TEXT_LIMIT // 2)}]}
    if finished:
        output["finish_reason"] = "stop"
    mock_vendor(client_module, lambda **kwargs: iter([{"status_code": 200, "output": output}]), monkeypatch)
    events = asyncio.run(
        collect(
            object.__new__(module.DefaultRunner).run(context({"api-key": "fixture", "app-id": "app", "app-type": mode}))
        )
    )
    assert event_type(events[-1]) == "run.failed"
    assert events[-1].data["code"] == "dashscope.response_limit"
    assert not messages(events)
