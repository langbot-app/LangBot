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

    results = asyncio.run(_collect_async(runner._run_workflow(_ctx(), FakeClient(), {}, "hello", "user_1", [], False)))

    interaction_result = results[-1]
    assert _type(results[0]) == "tool.call.started"
    assert results[0].data["tool_name"] == "Manual review"
    assert all(_type(result) != "message.delta" for result in results)
    assert _type(interaction_result) == "action.requested"
    assert interaction_result.data["action"] == "interaction.requested"
    request = interaction_result.data["payload"]
    assert request["fields"][0]["options"][0]["value"] == "high"
    assert request["actions"] == []
    assert "form-private" not in str(request)
    assert "workflow-private" not in str(request)
    assert len(storage.values) == 1
    continuation = json.loads(next(iter(storage.values.values())))
    assert continuation["form_token"] == "form-private"
    assert continuation["workflow_run_id"] == "workflow-private"
    assert continuation["interaction_actions"][0]["label"] == "Approve"
    assert all(_type(result) != "run.completed" for result in results)


def test_dify_interaction_resume_submits_mapped_values_and_clears_continuation() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-test"
    storage_key = module._interaction_storage_key(interaction_id)
    storage.values[storage_key] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-private",
            "workflow_run_id": "workflow-private",
            "user": "user_1",
            "field_map": {"field_1": "priority"},
            "action_map": {"action_1": "approve-private"},
            "default_inputs": {"comment": "default"},
        }
    ).encode()
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
    # Persist through the real contract: owner scope, expiry and pending status.
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), FakeClient(), submission, False)))

    assert captured == {
        "form_token": "form-private",
        "workflow_run_id": "workflow-private",
        "inputs": {"comment": "default", "priority": "high"},
        "user": "user_1",
        "action": "approve-private",
    }
    assert [_type(result) for result in results] == ["message.delta", "run.completed"]
    assert storage_key in storage.deleted
    assert storage_key not in storage.values


def test_dify_field_submission_advances_to_action_without_calling_provider() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-field"
    storage.values[module._interaction_storage_key(interaction_id)] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-private",
            "workflow_run_id": "workflow-private",
            "user": "user_1",
            "field_map": {"field_1": "priority"},
            "action_map": {"action_1": "approve-private"},
            "default_inputs": {},
            "title": "Manual review",
            "description": "Review it",
            "fallback_text": "Review it",
            "phase": "field",
            "current_fields": [
                {
                    "id": "field_1",
                    "label": "Priority",
                    "type": "select",
                    "required": True,
                    "options": [{"value": "high", "label": "High"}],
                }
            ],
            "remaining_fields": [],
            "interaction_actions": [{"id": "action_1", "label": "Approve", "style": "primary"}],
        }
    ).encode()

    class ProviderMustNotRun:
        def workflow_submit(self, **kwargs):
            raise AssertionError("provider must not resume before the action step")

    submission = InteractionSubmission(interaction_id=interaction_id, values={"field_1": "high"})
    # Persist through the real contract: owner scope, expiry and pending status.
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), ProviderMustNotRun(), submission, False)))

    assert [_type(result) for result in results] == ["action.requested"]
    request = results[0].data["payload"]
    assert request["fields"] == []
    assert request["actions"][0]["label"] == "Approve"
    continuation = json.loads(storage.values[module._interaction_storage_key(request["interaction_id"])])
    assert continuation["default_inputs"] == {"priority": "high"}


def test_dify_form_content_is_revealed_with_its_current_field() -> None:
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

    assert request.description == "1\n请输入你的问题"
    assert request.fields[0].label == "us_input"
    assert "请选择你的答案" not in request.description

    asyncio.run(runner._store_interaction_continuation(_ctx(), continuation))
    second_result = asyncio.run(
        runner._advance_field_interaction(
            _ctx(),
            continuation,
            InteractionSubmission(interaction_id=request.interaction_id, values={"field_1": "问题内容"}),
        )
    )
    second_request = second_result.data["payload"]
    assert second_request["description"] == "请选择你的答案"
    assert second_request["fields"][0]["label"] == "xiala"
    assert "请输入你的问题" not in second_request["description"]

    second_continuation = json.loads(storage.values[module._interaction_storage_key(second_request["interaction_id"])])
    final_result = asyncio.run(
        runner._advance_field_interaction(
            _ctx(),
            second_continuation,
            InteractionSubmission(
                interaction_id=second_request["interaction_id"],
                values={"field_2": "1"},
            ),
        )
    )
    final_request = final_result.data["payload"]
    assert final_request["description"] is None
    assert final_request["fields"] == []
    assert final_request["actions"][0]["label"] == "or"


def test_dify_interaction_resume_can_pause_again() -> None:
    module = _load_runner_module("dify-agent")
    runner = object.__new__(module.DefaultRunner)
    storage = _FakePluginStorage()
    runner.get_run_api = lambda ctx: storage
    interaction_id = "dify-first"
    old_key = module._interaction_storage_key(interaction_id)
    storage.values[old_key] = json.dumps(
        {
            "version": 1,
            "interaction_id": interaction_id,
            "form_token": "form-1",
            "workflow_run_id": "workflow-1",
            "user": "user_1",
            "field_map": {},
            "action_map": {"continue": ""},
            "default_inputs": {},
        }
    ).encode()

    class FakeClient:
        async def workflow_submit(self, **kwargs):
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

    submission = InteractionSubmission(interaction_id=interaction_id, action_id="continue")
    # Persist through the real contract: owner scope, expiry and pending status.
    asyncio.run(
        runner._store_interaction_continuation(
            _ctx(), json.loads(storage.values[module._interaction_storage_key(interaction_id)])
        )
    )
    results = asyncio.run(_collect_async(runner._resume_workflow(_ctx(), FakeClient(), submission, False)))

    assert [_type(result) for result in results] == ["action.requested"]
    new_interaction_id = results[0].data["payload"]["interaction_id"]
    assert new_interaction_id != interaction_id
    assert old_key in storage.deleted
    assert module._interaction_storage_key(new_interaction_id) in storage.values


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
