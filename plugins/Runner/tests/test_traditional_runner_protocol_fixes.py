from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import httpx
from langbot_plugin.api.entities.builtin.provider.message import ContentElement
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
    InteractionResult,
    InteractionSubmission,
    RunnerContext,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_runner_module(plugin_dir: str, stubs: dict[str, Any] | None = None):
    for module_name in list(sys.modules):
        if module_name == "pkg" or module_name.startswith("pkg."):
            del sys.modules[module_name]

    installed_stubs: dict[str, Any] = {}
    for name, value in (stubs or {}).items():
        if name not in sys.modules:
            installed_stubs[name] = value
            sys.modules[name] = value

    plugin_root = ROOT / plugin_dir
    sys.path.insert(0, str(plugin_root))
    try:
        module_path = plugin_root / "components" / "runner" / "default.py"
        spec = importlib.util.spec_from_file_location(
            f"test_traditional_{plugin_dir.replace('-', '_')}_runner",
            module_path,
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(plugin_root))
        for name in installed_stubs:
            sys.modules.pop(name, None)


async def _collect_async(generator):
    return [item async for item in generator]


def _type(result) -> str:
    return getattr(result.type, "value", str(result.type))


def _ctx(
    *,
    config: dict[str, Any] | None = None,
    text: str = "hello",
    contents: list[ContentElement] | None = None,
    conversation_state: dict[str, Any] | None = None,
    event_type: str = "message.received",
    interaction: InteractionSubmission | None = None,
) -> RunnerContext:
    return RunnerContext(
        run_id="run_traditional",
        trigger=AgentTrigger(type=event_type),
        event=AgentEventContext(event_id="evt_1", event_type=event_type, source="test"),
        conversation=ConversationContext(
            conversation_id="langbot-conv-1",
            session_id="langbot-session-1",
        ),
        input=AgentInput(text=text, contents=contents or [], interaction=interaction),
        delivery=DeliveryContext(surface="test", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(conversation=conversation_state or {}),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="traditional-sender"),
        config=config or {},
    )


def _dify_interaction_ctx():
    ctx = _ctx()
    requests = []

    async def request_interaction(request, **kwargs):
        requests.append(request)
        return InteractionResult(
            status="submitted",
            submission=InteractionSubmission(
                interaction_id=request.interaction_id,
                action_id=request.actions[0].id if request.actions else None,
                values={field.id: ("action_1" if field.id == "_dify_action" else "high") for field in request.fields},
            ),
        )

    ctx._api = types.SimpleNamespace(request_interaction=request_interaction)
    return ctx, requests


def _text_and_image_ctx(config: dict[str, Any]) -> RunnerContext:
    return _ctx(
        config=config,
        text="describe this",
        contents=[ContentElement.from_image_base64("data:image/png;base64,aGVsbG8=")],
    )


def test_coze_does_not_reuse_langbot_conversation_id_as_external_id() -> None:
    module = _load_runner_module("coze-agent")
    runner = object.__new__(module.DefaultRunner)

    assert runner._get_external_conversation_id(_ctx()) is None

    ctx = _ctx(conversation_state={"external.conversation_id": "coze-conv-1"})
    assert runner._get_external_conversation_id(ctx) == "coze-conv-1"


def test_n8n_uses_runner_owned_conversation_and_session_ids() -> None:
    module = _load_runner_module("n8n-agent")
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx()

    conversation_id, conversation_created = runner._get_or_create_state_id(
        ctx,
        "external.conversation_id",
        "n8n_conversation",
    )
    session_id, session_created = runner._get_or_create_state_id(
        ctx,
        "external.session_id",
        "n8n_session",
    )
    payload = runner._build_payload(ctx, "hello", conversation_id, session_id)

    assert conversation_created is True
    assert session_created is True
    assert payload["conversation_id"].startswith("n8n_conversation_")
    assert payload["session_id"].startswith("n8n_session_")
    assert payload["conversation_id"] != "langbot-conv-1"
    assert payload["session_id"] != "langbot-session-1"


def test_dify_workflow_uses_runner_owned_state_ids() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    captured_inputs: dict[str, Any] = {}

    class FakeClient:
        async def workflow_run(self, *, inputs, user, files):
            captured_inputs.update(inputs)
            yield {
                "event": "workflow_finished",
                "data": {"outputs": {"summary": "workflow ok"}},
            }

    ctx = _ctx()
    results = asyncio.run(
        _collect_async(
            runner._run_workflow(
                ctx,
                FakeClient(),
                {},
                "hello",
                "user_1",
                [],
                False,
            )
        )
    )

    assert captured_inputs["langbot_session_id"].startswith("dify_session_")
    assert captured_inputs["langbot_conversation_id"].startswith("dify_conversation_")
    assert captured_inputs["langbot_session_id"] != "langbot-session-1"
    assert captured_inputs["langbot_conversation_id"] != "langbot-conv-1"
    assert ("state.updated", "external.workflow_session_id") in {
        (_type(item), item.data.get("key")) for item in results
    }
    assert ("state.updated", "external.workflow_conversation_id") in {
        (_type(item), item.data.get("key")) for item in results
    }
    assert _type(results[-1]) == "run.completed"


class _FakePluginStorage:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def set_plugin_storage(self, key: str, value: bytes) -> None:
        self.values[key] = value

    async def get_plugin_storage(self, key: str) -> bytes:
        return self.values[key]

    async def delete_plugin_storage(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)


def test_dify_workflow_pause_requests_host_interaction_and_hides_provider_tokens() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage

    class FakeClient:
        async def workflow_run(self, *, inputs, user, files):
            yield {"event": "workflow_started", "data": {"workflow_run_id": "workflow-private"}}
            yield {
                "event": "node_started",
                "data": {
                    "node_id": "human-input-node",
                    "node_type": "human-input",
                    "title": "Manual review",
                },
            }
            yield {
                "event": "workflow_paused",
                "data": {
                    "reasons": [
                        {
                            "TYPE": "human_input_required",
                            "form_token": "form-private",
                            "node_title": "Manual review",
                            "form_content": "Choose a priority\n{{#$output.priority#}}",
                            "inputs": [
                                {
                                    "output_variable_name": "priority",
                                    "type": "select",
                                    "option_source": {"type": "constant", "value": ["high", "low"]},
                                }
                            ],
                            "actions": [{"id": "approve-private", "title": "Approve"}],
                        }
                    ],
                },
            }

        async def workflow_submit(self, **kwargs):
            assert kwargs["form_token"] == "form-private"
            assert kwargs["workflow_run_id"] == "workflow-private"
            assert kwargs["inputs"]["priority"] == "high"
            assert kwargs["action"] == "approve-private"
            yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "Approved"}}}
            yield {"event": "workflow_finished", "data": {"outputs": {}}}

    ctx, requests = _dify_interaction_ctx()
    results = asyncio.run(_collect_async(runner._run_workflow(ctx, FakeClient(), {}, "hello", "user_1", [], False)))

    assert _type(results[0]) == "tool.call.started"
    assert results[0].data["tool_name"] == "Manual review"
    assert requests[0].fields[0].options[0].value == "high"
    assert len(requests) == 1
    assert requests[0].actions == []
    assert "form-private" not in str(requests)
    assert "workflow-private" not in str(requests)
    assert storage.values == {}
    assert _type(results[-1]) == "run.completed"


def test_dify_current_human_input_event_requests_host_interaction() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage

    class FakeClient:
        async def workflow_run(self, *, inputs, user, files):
            yield {
                "event": "human_input_required",
                "workflow_run_id": "workflow-private",
                "data": {
                    "form_token": "form-private",
                    "node_title": "Manual review",
                    "form_content": "Choose a priority\n{{#$output.priority#}}",
                    "inputs": [
                        {
                            "output_variable_name": "priority",
                            "type": "select",
                            "option_source": {"type": "constant", "value": ["high", "low"]},
                        }
                    ],
                    "actions": [{"id": "approve-private", "title": "Approve"}],
                },
            }

        async def workflow_submit(self, **kwargs):
            assert kwargs["inputs"]["priority"] == "high"
            yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "Approved"}}}
            yield {"event": "workflow_finished", "data": {"outputs": {}}}

    ctx, requests = _dify_interaction_ctx()
    results = asyncio.run(_collect_async(runner._run_workflow(ctx, FakeClient(), {}, "hello", "user_1", [], False)))

    assert _type(results[-1]) == "run.completed"
    assert requests[0].title == "Manual review"
    assert requests[0].fields[0].options[0].value == "high"
    assert "form-private" not in str(requests)
    assert "workflow-private" not in str(requests)
    assert storage.values == {}


def test_dify_pause_accepts_single_reason_and_camel_case_fields() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    event = {
        "event": "workflow_paused",
        "data": {
            "workflowRunId": "workflow-private",
            "reason": {
                "type": "human-input-required",
                "formToken": "form-private",
                "nodeTitle": "Manual review",
                "formContent": "Choose a priority\n{{#$output.priority#}}",
                "resolvedDefaultValues": {"priority": "low"},
                "fields": [
                    {
                        "outputVariableName": "priority",
                        "type": "select",
                        "optionSource": {"type": "constant", "value": [{"label": "High", "value": "high"}]},
                    }
                ],
                "userActions": [{"actionId": "approve-private", "label": "Approve"}],
            },
        },
    }

    request, continuation = runner._build_interaction_request(event["data"]["reason"], "workflow-private", "user_1")

    assert request.title == "Manual review"
    assert request.fields[0].default == "low"
    assert request.fields[0].options[0].value == "high"
    assert request.fields[0].options[0].label == "high"
    assert continuation["action_map"] == {"action_1": "approve-private"}
    assert "form-private" not in str(request)
    assert "workflow-private" not in str(request)
    assert storage.values == {}


def test_dify_interaction_resume_submits_mapped_values_in_same_run() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    interaction_id = "dify-test"
    continuation = {
        "interaction_id": interaction_id,
        "form_token": "form-private",
        "workflow_run_id": "workflow-private",
        "user": "user_1",
        "field_map": {"field_1": "priority"},
        "action_map": {"action_1": "approve-private"},
        "default_inputs": {"comment": "default"},
    }
    captured: dict[str, Any] = {}

    class FakeClient:
        async def workflow_submit(self, **kwargs):
            captured.update(kwargs)
            yield {
                "event": "workflow_finished",
                "data": {"error": None, "outputs": {"summary": "Approved"}},
            }

    submission = InteractionSubmission(
        interaction_id=interaction_id,
        action_id="action_1",
        values={"field_1": "high"},
    )
    results = asyncio.run(
        _collect_async(runner._resume_workflow_once(_ctx(), FakeClient(), submission, False, continuation))
    )

    assert captured == {
        "form_token": "form-private",
        "workflow_run_id": "workflow-private",
        "inputs": {"comment": "default", "priority": "high"},
        "user": "user_1",
        "action": "approve-private",
    }
    assert [_type(result) for result in results] == ["message.delta", "run.completed"]


def test_dify_multi_field_form_is_requested_once() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    request, continuation = runner._build_interaction_request(
        {
            "form_token": "form-private",
            "node_title": "Manual review",
            "inputs": [
                {"output_variable_name": "first", "type": "text"},
                {"output_variable_name": "second", "type": "text"},
            ],
            "actions": [{"id": "approve", "title": "Approve"}, {"id": "reject", "title": "Reject"}],
        },
        "workflow-private",
        "user_1",
    )

    assert [field.id for field in request.fields] == ["field_1", "field_2", "_dify_action"]
    assert [option.value for option in request.fields[-1].options] == ["action_1", "action_2"]
    assert request.actions == []
    assert continuation["field_map"] == {"field_1": "first", "field_2": "second"}


def test_dify_form_content_is_sent_with_all_fields() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    request, continuation = runner._build_interaction_request(
        {
            "form_token": "form-private",
            "node_title": "人工介入",
            "form_content": ("1\n请输入你的问题\n{{#$output.us_input#}}\n\n请选择你的答案\n{{#$output.xiala#}}"),
            "inputs": [
                {"output_variable_name": "us_input", "type": "paragraph", "required": True},
                {
                    "output_variable_name": "xiala",
                    "type": "select",
                    "required": True,
                    "option_source": {"type": "constant", "value": ["1", "2"]},
                },
            ],
            "actions": [{"id": "or-private", "title": "or"}],
        },
        "workflow-private",
        "user-1",
    )

    assert request.description == "1\n请输入你的问题\n\n请选择你的答案"
    assert [field.label for field in request.fields] == ["us_input", "xiala"]
    assert request.actions == []
    assert continuation["action_map"] == {"action_1": "or-private"}


def test_dify_interaction_resume_can_pause_again() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    continuation = {
        "interaction_id": "dify-first",
        "form_token": "form-1",
        "workflow_run_id": "workflow-1",
        "user": "user_1",
        "field_map": {},
        "action_map": {"continue": ""},
        "default_inputs": {},
    }

    class FakeClient:
        async def workflow_submit(self, **kwargs):
            if kwargs["form_token"] == "form-1":
                yield {
                    "event": "workflow_paused",
                    "data": {
                        "workflow_run_id": "workflow-2",
                        "reasons": [
                            {
                                "TYPE": "human_input_required",
                                "form_token": "form-2",
                                "node_title": "Second review",
                                "inputs": [],
                                "actions": [{"id": "done", "title": "Done"}],
                            }
                        ],
                    },
                }
            else:
                yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "Done"}}}
                yield {"event": "workflow_finished", "data": {"outputs": {}}}

    ctx, requests = _dify_interaction_ctx()
    submission = InteractionSubmission(interaction_id="dify-first", action_id="continue")
    results = asyncio.run(
        _collect_async(runner._resume_workflow_once(ctx, FakeClient(), submission, False, continuation))
    )

    assert len(requests) == 1
    assert requests[0].title == "Second review"
    assert _type(results[-1]) == "run.completed"


def test_dify_client_submits_form_then_streams_resumed_events(monkeypatch) -> None:
    module = _load_runner_module("dify-agent")
    client_module = sys.modules["pkg.dify_client"]
    real_async_client = httpx.AsyncClient
    calls: list[httpx.Request] = []
    expected_event = {
        "event": "workflow_finished",
        "data": {"outputs": {"summary": "done", "note": "完成"}},
    }
    event_bytes = b"data: " + json.dumps(expected_event, ensure_ascii=False).encode("utf-8")
    # Split UTF-8 across the bounded reader's 8192-byte boundary as well as
    # transport chunks. Keep the original blank line and unterminated EOF event.
    padding = 8191 - len(b"\r\n:\r\n") - event_bytes.index("完".encode())
    wire = b"\r\n:" + b" " * padding + b"\r\n" + event_bytes
    assert wire[8191:8194] == "完".encode()

    class ChunkedBytes(httpx.AsyncByteStream):
        def __init__(self, chunks):
            self.chunks = chunks
            self.consumed = False
            self.closed = False

        async def __aiter__(self):
            for chunk in self.chunks:
                yield chunk
            self.consumed = True

        async def aclose(self):
            self.closed = True

    form_body = ChunkedBytes([b'{"res', b'ult":"success"}'])
    # CR/LF, SSE prefix, JSON and multibyte characters may all span chunks.
    event_body = ChunkedBytes([wire[:1], *[wire[i : i + 7] for i in range(1, len(wire), 7)]])

    def handle_request(request):
        calls.append(request)
        if len(calls) == 1:
            assert request.method == "POST"
            return httpx.Response(200, headers={"content-type": "application/json"}, stream=form_body)
        assert len(calls) == 2
        assert request.method == "GET"
        assert form_body.consumed and form_body.closed
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=event_body)

    transport = httpx.MockTransport(handle_request)
    monkeypatch.setattr(
        client_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )
    client = module.AsyncDifyClient(api_key="key", base_url="https://dify.example/v1")
    events = asyncio.run(
        _collect_async(
            client.workflow_submit(
                form_token="form-token",
                workflow_run_id="workflow-run",
                inputs={"priority": "high"},
                user="user-1",
                action="approve",
            )
        )
    )

    assert events[0]["event"] == "workflow_finished"
    assert events == [expected_event]
    assert [(request.method, request.url.path) for request in calls] == [
        ("POST", "/v1/form/human_input/form-token"),
        ("GET", "/v1/workflow/workflow-run/events"),
    ]
    assert json.loads(calls[0].content) == {
        "inputs": {"priority": "high"},
        "user": "user-1",
        "action": "approve",
    }
    assert calls[0].headers["content-type"] == "application/json"
    assert dict(calls[1].url.params) == {"user": "user-1"}
    assert calls[1].content == b""
    for request in calls:
        assert request.url.host == "dify.example"
        assert request.headers["authorization"] == "Bearer key"
    assert form_body.consumed and form_body.closed
    assert event_body.consumed and event_body.closed


def test_dify_client_consumes_sse_returned_by_form_submission(monkeypatch) -> None:
    module = _load_runner_module("dify-agent")
    client_module = sys.modules["pkg.dify_client"]
    real_async_client = httpx.AsyncClient
    calls: list[httpx.Request] = []
    expected_event = {"event": "workflow_finished", "data": {"outputs": {"summary": "done"}}}

    def handle_request(request):
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream; charset=utf-8"},
            content=b"data: " + json.dumps(expected_event).encode() + b"\n\n",
        )

    transport = httpx.MockTransport(handle_request)
    monkeypatch.setattr(
        client_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )
    client = module.AsyncDifyClient(api_key="key", base_url="https://dify.example/v1")

    events = asyncio.run(
        _collect_async(
            client.workflow_submit(
                form_token="form-token",
                workflow_run_id="workflow-run",
                inputs={"priority": "high"},
                user="user-1",
                action="approve",
            )
        )
    )

    assert events == [expected_event]
    assert [(request.method, request.url.path) for request in calls] == [("POST", "/v1/form/human_input/form-token")]


def test_dify_client_yields_submission_sse_before_stream_ends(monkeypatch) -> None:
    module = _load_runner_module("dify-agent")
    client_module = sys.modules["pkg.dify_client"]
    real_async_client = httpx.AsyncClient
    first_event = {"event": "text_chunk", "data": {"text": "ready"}}

    class FirstEventStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"data: " + json.dumps(first_event).encode() + b"\n\n"
            raise AssertionError("submission response was buffered before the first event")

    def handle_request(request):
        assert request.method == "POST"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=FirstEventStream())

    monkeypatch.setattr(
        client_module.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=httpx.MockTransport(handle_request), **kwargs),
    )
    client = module.AsyncDifyClient(api_key="key", base_url="https://dify.example/v1")

    async def read_first():
        stream = client.workflow_submit("form-token", "workflow-run", {}, "user-1", "approve")
        try:
            return await anext(stream)
        finally:
            await stream.aclose()

    assert asyncio.run(read_first()) == first_event


def test_dify_text_image_upload_failure_is_input_error() -> None:
    module = _load_runner_module("dify-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def upload_file(self, *args, **kwargs):
            raise module.DifyAPIError("provider upload failed", code="dify.http_error")

    module.AsyncDifyClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _text_and_image_ctx(
        {
            "base-url": "https://api.dify.ai/v1",
            "api-key": "key",
            "app-type": "chat",
        }
    )

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data["code"] == "dify.input_error"
    assert results[0].data["retryable"] is False


def test_coze_text_image_upload_failure_is_input_error() -> None:
    module = _load_runner_module("coze-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def upload_file(self, *args, **kwargs):
            raise module.CozeAPIError("provider upload failed", code="coze.http_error")

        async def close(self):
            pass

    module.AsyncCozeClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _text_and_image_ctx({"api-key": "key", "bot-id": "bot"})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data["code"] == "coze.input_error"


def test_dashscope_timeout_maps_to_retryable_run_failed() -> None:
    dashscope_stub = types.SimpleNamespace(Application=types.SimpleNamespace(call=lambda **kwargs: iter(())))
    module = _load_runner_module("dashscope-agent", stubs={"dashscope": dashscope_stub})

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def iter_agent(self, **kwargs):
            raise module.DashScopeAPIError("timeout", code="dashscope.timeout", retryable=True)
            yield {}

    module.DashScopeClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx(config={"api-key": "key", "app-id": "app", "app-type": "agent"})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data == {"code": "dashscope.timeout", "error": "timeout", "retryable": True}


def test_dashscope_empty_output_fails_instead_of_completing() -> None:
    dashscope_stub = types.SimpleNamespace(Application=types.SimpleNamespace(call=lambda **kwargs: iter(())))
    module = _load_runner_module("dashscope-agent", stubs={"dashscope": dashscope_stub})

    class FakeClient:
        references_quote = "refs:"

        def __init__(self, **kwargs):
            pass

        async def iter_agent(self, **kwargs):
            if False:
                yield {}

    module.DashScopeClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx(config={"api-key": "key", "app-id": "app", "app-type": "agent"})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data["code"] == "dashscope.empty_response"


def test_tbox_timeout_maps_to_retryable_run_failed() -> None:
    module = _load_runner_module("tbox-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def chat(self, **kwargs):
            raise module.TboxAPIError("timeout", code="tbox.timeout", retryable=True)
            yield {}

    module.AsyncTboxClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx(config={"api-key": "key", "app-id": "app"})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data == {"code": "tbox.timeout", "error": "timeout", "retryable": True}


def test_deerflow_timeout_maps_to_retryable_run_failed() -> None:
    module = _load_runner_module("deerflow-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def stream_run(self, **kwargs):
            raise TimeoutError("provider timeout")
            yield {}

    module.AsyncDeerFlowClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    runner._ensure_thread_id = lambda ctx, client, timeout: _async_value(("thread-1", False))
    ctx = _ctx(config={"api-base": "http://127.0.0.1:2026", "streaming": True, "timeout": 1})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data["code"] == "deerflow.timeout"
    assert results[0].data["retryable"] is True


async def _async_value(value):
    return value


def test_weknora_timeout_maps_to_retryable_run_failed() -> None:
    module = _load_runner_module("weknora-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def create_session(self, **kwargs):
            raise module.WeKnoraAPIError("timeout", code="weknora.timeout", retryable=True)

    module.AsyncWeKnoraClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx(config={"base-url": "http://weknora/api/v1", "api-key": "key"})

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data == {"code": "weknora.timeout", "error": "timeout", "retryable": True}


def test_weknora_empty_answer_fails_instead_of_completing() -> None:
    module = _load_runner_module("weknora-agent")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def agent_chat(self, **kwargs) -> AsyncGenerator[dict[str, Any], None]:
            yield {"response_type": "answer", "content": "", "done": True}

    module.AsyncWeKnoraClient = FakeClient
    runner = object.__new__(module.DefaultRunner)
    ctx = _ctx(
        config={"base-url": "http://weknora/api/v1", "api-key": "key", "app-type": "agent"},
        conversation_state={"external.session_id": "weknora-session-1"},
    )

    results = asyncio.run(_collect_async(runner.run(ctx)))

    assert [_type(item) for item in results] == ["run.failed"]
    assert results[0].data["code"] == "weknora.empty_response"
