"""Native parity against real Runner/SDK types; provider I/O stays local."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from contextlib import contextmanager
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


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    import httpx

    async def denied(*args, **kwargs):
        raise AssertionError("Provider network is forbidden in parity tests")

    original_send = httpx.AsyncClient.send

    async def guarded(client, *args, **kwargs):
        if isinstance(client._transport, httpx.MockTransport):
            return await original_send(client, *args, **kwargs)
        return await denied()

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded)


@contextmanager
def load_runner(plugin):
    saved = {k: v for k, v in sys.modules.items() if k == "pkg" or k.startswith("pkg.")}
    for k in saved:
        del sys.modules[k]
    path = ROOT / plugin
    sys.path.insert(0, str(path))
    try:
        spec = importlib.util.spec_from_file_location(
            "external_parity_" + plugin.replace("-", "_"), path / "components/runner/default.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module, object.__new__(module.DefaultRunner)
    finally:
        sys.path.remove(str(path))
        for k in list(sys.modules):
            if k == "pkg" or k.startswith("pkg."):
                del sys.modules[k]
        sys.modules.update(saved)


def ctx(config=None, state=None, text="hello"):
    return RunnerContext(
        run_id="external-parity-run",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(event_id="fixture-event", event_type="message.received", source="test"),
        conversation=ConversationContext(conversation_id="local-conversation", session_id="local-session"),
        input=AgentInput(text=text),
        delivery=DeliveryContext(surface="test", supports_streaming=True),
        resources=AgentResources(),
        state=AgentRunState(conversation=state or {}),
        runtime=AgentRuntimeContext(),
        actor=ActorContext(actor_type="user", actor_id="parity-sender"),
        config=config or {},
    )


def collect(generator):
    async def run():
        return [result async for result in generator]

    return asyncio.run(run())


def kind(result):
    return getattr(result.type, "value", str(result.type))


def contents(results):
    messages = [
        r.data.get("message", r.data.get("chunk", {}))
        for r in results
        if kind(r) in {"message.delta", "message.completed"}
    ]
    return [message["content"] for message in messages if message.get("content")]


@pytest.mark.parametrize("value", ["false", 0, 1, None, [], {}])
def test_dify_remove_think_rejects_non_boolean(value):
    with load_runner("dify-agent") as (m, runner):
        with pytest.raises(m.DifyConfigError, match="remove-think must be a boolean"):
            runner._validate_config(ctx({"api-key": "fixture", "remove-think": value}))


@pytest.mark.parametrize("app", ["chat", "chatflow", "agent", "workflow"])
@pytest.mark.parametrize("remove", [False, True])
def test_dify_remove_think_is_applied_by_actual_run(monkeypatch, app, remove):
    with load_runner("dify-agent") as (m, runner):

        class Client:
            def __init__(self, **kwargs):
                pass

            async def chat_messages(self, **kwargs):
                yield {"event": "message", "answer": "<think>private reasoning</think>public answer"}
                yield {"event": "message_end"}

            async def workflow_run(self, **kwargs):
                yield {
                    "event": "workflow_finished",
                    "data": {"outputs": {"summary": "<think>private reasoning</think>public answer"}},
                }

        monkeypatch.setattr(m, "AsyncDifyClient", Client)
        results = collect(runner.run(ctx({"api-key": "fixture", "app-type": app, "remove-think": remove})))
        assert kind(results[-1]) == "run.completed"
        visible = json.dumps(contents(results))
        assert "public answer" in visible
        assert ("private reasoning" in visible) is (not remove)


def test_dify_native_cumulative_chat_chunks_do_not_duplicate():
    with load_runner("dify-agent") as (m, runner):

        class Client:
            async def chat_messages(self, **kwargs):
                for text in ["hel", "hello", " world"]:
                    yield {"event": "message", "answer": text}
                yield {"event": "message_end"}

        results = collect(runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], "chat", False))
        assert contents(results)[-1] == "hello world"


def test_dify_unclosed_think_never_visible_on_pause():
    with load_runner("dify-agent") as (m, runner):

        class Client:
            async def chat_messages(self, **kwargs):
                yield {"event": "message", "answer": "safe<think>private reasoning"}
                yield {"event": "message_end"}

        results = collect(runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], "chat", True))
        assert contents(results) == ["safe"]


@pytest.mark.parametrize("key", ["api-key", "auth-header"])
def test_deerflow_auth_bytes_and_precedence_survive_validator(key):
    with load_runner("deerflow-agent") as (m, runner):
        opaque = "  fixture opaque\t"
        config = runner._validate_config(ctx({"api-base": "https://example.invalid/prefix/", key: opaque}))
        client = m.AsyncDeerFlowClient(
            api_base=config["api_base"], api_key=config["api_key"], auth_header=config["auth_header"]
        )
        assert client.headers["Authorization"] == (opaque if key == "auth-header" else "Bearer " + opaque)
        assert m.AsyncDeerFlowClient(api_key="ignored", auth_header=opaque).headers["Authorization"] == opaque


@pytest.mark.parametrize("assistant,model", [(" graph ", " model "), ("", ""), (" ", " ")])
def test_deerflow_explicit_options_are_not_replaced(assistant, model):
    with load_runner("deerflow-agent") as (m, runner):
        config = runner._validate_config(
            ctx(
                {
                    "api-base": "https://example.invalid",
                    "assistant-id": assistant,
                    "model-name": model,
                    "thinking-enabled": True,
                    "plan-mode": True,
                    "subagent-enabled": True,
                    "max-concurrent-subagents": 5,
                    "recursion-limit": 77,
                }
            )
        )
        payload = runner._build_payload(config, "remote-thread", "hello", [])
        assert payload["assistant_id"] == assistant
        configurable = payload["config"]["configurable"]
        assert configurable == payload["context"]
        assert configurable.get("model_name", "") == model
        assert configurable["thinking_enabled"] and configurable["is_plan_mode"] and configurable["subagent_enabled"]
        assert configurable["max_concurrent_subagents"] == 5
        assert payload["config"]["recursion_limit"] == 77


@pytest.mark.parametrize(
    "key,value",
    [
        ("api-key", None),
        ("auth-header", 123),
        ("assistant-id", None),
        ("model-name", []),
        ("thinking-enabled", "false"),
        ("plan-mode", 1),
        ("subagent-enabled", None),
        ("timeout", 1.5),
        ("recursion-limit", True),
    ],
)
def test_deerflow_invalid_options_fail_safely(key, value):
    with load_runner("deerflow-agent") as (m, runner):
        results = collect(runner.run(ctx({"api-base": "https://example.invalid", key: value})))
        assert len(results) == 1 and kind(results[0]) == "run.failed"
        assert results[0].data["code"] == "deerflow.config_invalid"
        assert key in results[0].data["error"]


@pytest.mark.parametrize("bad", ['{"credential":"fixture-private"', "[1]", '"text"', "false", "1", [], 3, False])
def test_langflow_invalid_tweaks_fail_without_logging_payload(bad, caplog):
    with load_runner("langflow-agent") as (m, runner):
        results = collect(runner.run(ctx({"api-key": "fixture", "flow-id": "flow", "tweaks": bad})))
        assert len(results) == 1 and kind(results[0]) == "run.failed"
        assert results[0].data["code"] == "langflow.config_invalid"
        assert "tweaks" in results[0].data["error"]
        assert "fixture-private" not in caplog.text + json.dumps(results[0].data)


@pytest.mark.parametrize(
    "config", [{}, {"tweaks": None}, {"tweaks": ""}, {"tweaks": "  \n"}, {"tweaks": "null"}, {"tweaks": "{}"}]
)
def test_langflow_empty_tweaks_and_new_persistent_history_are_retained(config):
    with load_runner("langflow-agent") as (m, runner):
        validated = runner._validate_config(ctx({"api-key": "fixture", "flow-id": "flow", **config}))
        assert validated["tweaks"] == {}
        assert runner._get_session_id(ctx(state={"external.session_id": "remote-session"})) == "remote-session"
        assert validated["langbot_assets_enabled"] is False


def test_langflow_nested_tweaks_and_io_reach_actual_run(monkeypatch):
    with load_runner("langflow-agent") as (m, runner):
        seen = []

        class Client:
            def __init__(self, **kwargs):
                pass

            async def run_flow(self, **kwargs):
                seen.append(kwargs)
                yield {"messages": [{"message": "ok"}]}

        monkeypatch.setattr(m, "AsyncLangflowClient", Client)
        tweaks = {"node": {"credential": " fixture ", "enabled": False, "count": 0, "nested": [None, "x"]}}
        config = {
            "api-key": "fixture",
            "flow-id": "flow",
            "input-type": "text",
            "output-type": "debug",
            "tweaks": json.dumps(tweaks),
            "streaming": False,
        }
        results = collect(runner.run(ctx(config)))
        state = {r.data["key"]: r.data["value"] for r in results if kind(r) == "state.updated"}
        second = collect(runner.run(ctx(config, state)))
        assert kind(second[-1]) == "run.completed"
        assert seen[0]["session_id"] == seen[1]["session_id"]
        assert seen[0]["tweaks"] == tweaks
        assert (seen[0]["input_type"], seen[0]["output_type"]) == ("text", "debug")


def test_langflow_nonstream_unknown_output_preserves_native_json_fallback(monkeypatch):
    with load_runner("langflow-agent") as (m, runner):

        class Client:
            def __init__(self, **kwargs):
                pass

            async def run_flow(self, **kwargs):
                yield {"result": {"value": 42}}

        monkeypatch.setattr(m, "AsyncLangflowClient", Client)
        results = collect(runner.run(ctx({"api-key": "fixture", "flow-id": "flow", "streaming": False})))
        assert kind(results[-1]) == "run.completed"
        assert json.loads(contents(results)[-1]) == {"result": {"value": 42}}


@pytest.mark.parametrize("app,expected", [("chat", "builtin-quick-answer"), ("agent", "builtin-smart-reasoning")])
@pytest.mark.parametrize("explicit", ["missing", "builtin-smart-reasoning", " custom ", "", None])
def test_weknora_agent_defaults_and_exact_remote_ids_reach_client(monkeypatch, app, expected, explicit):
    with load_runner("weknora-agent") as (m, runner):
        captured = []
        client = m.AsyncWeKnoraClient("fixture")

        async def stream(**kwargs):
            captured.append(kwargs)
            yield {"response_type": "answer", "content": "ok", "done": True}

        client._stream_json_lines = stream
        monkeypatch.setattr(m, "AsyncWeKnoraClient", lambda **kwargs: client)
        config = {
            "base-url": "https://example.invalid/api/v1",
            "api-key": "fixture",
            "app-type": app,
            "knowledge-base-ids": [" remote-kb ", "remote-kb", "remote-kb"],
            "web-search-enabled": True,
        }
        if explicit != "missing":
            config["agent-id"] = explicit
        results = collect(runner.run(ctx(config, {"external.session_id": "remote-session"})))
        assert kind(results[-1]) == "run.completed"
        payload = captured[0]["payload"]
        assert payload.get("agent_id") == (expected if explicit == "missing" else explicit or None)
        assert payload["knowledge_base_ids"] == config["knowledge-base-ids"]
        assert ("web_search_enabled" in payload) is (app == "agent")
        assert captured[0]["path"] == (
            "/knowledge-chat/remote-session" if app == "chat" else "/agent-chat/remote-session"
        )


@pytest.mark.parametrize("value", [[None], [5], [{}], [""], [" \t"], "remote-kb"])
def test_weknora_invalid_remote_ids_are_not_stringified_or_dropped(value):
    with load_runner("weknora-agent") as (m, runner):
        with pytest.raises(m.WeKnoraConfigError, match="knowledge-base-ids"):
            runner._validate_config(
                ctx({"base-url": "https://example.invalid", "api-key": "fixture", "knowledge-base-ids": value})
            )


# HTTPX itself encodes requests and iterates real Response streams. No provider
# socket is opened: every request is intercepted by an in-process MockTransport.
def http_fixture(monkeypatch, module, payload, status=200, headers=None):
    import httpx

    requests = []
    original = httpx.AsyncClient

    class Bytes(httpx.AsyncByteStream):
        async def __aiter__(self):
            for pos in range(0, len(payload), 8192):
                yield payload[pos : pos + 8192]

    def respond(request):
        requests.append(request)
        return httpx.Response(status, stream=Bytes(), request=request, headers=headers)

    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kw: original(transport=transport, **kw))
    return requests


def client_module(plugin):
    return sys.modules["pkg." + plugin.removesuffix("-agent") + "_client"]


def streamed_request(plugin, m):
    if plugin == "dify-agent":
        return m.AsyncDifyClient("fixture").chat_messages({}, "hi", "fixture-user")
    if plugin == "deerflow-agent":
        return m.AsyncDeerFlowClient().stream_run("fixture-thread", {})
    if plugin == "langflow-agent":
        return m.AsyncLangflowClient("fixture").run_flow("fixture-flow", "hi")
    return m.AsyncWeKnoraClient("fixture").knowledge_chat("fixture-session", "hi", "fixture-user")


@pytest.mark.parametrize("plugin", ["dify-agent", "deerflow-agent", "langflow-agent", "weknora-agent"])
@pytest.mark.parametrize("oversize", ["line", "total", "error_body"])
def test_native_client_limits_are_enforced_on_actual_http_stream(monkeypatch, plugin, oversize):
    with load_runner(plugin):
        m = client_module(plugin)
        if oversize == "line":
            payload = b'data: {"content":"' + b"x" * (1024 * 1024) + b'"}\n\n'
        elif oversize == "total":
            keepalive = b": " + b"x" * 8000 + b"\n\n"
            payload = keepalive * (16 * 1024 * 1024 // len(keepalive) + 1)
        else:
            payload = b"x" * (1024 * 1024 + 1)
        http_fixture(monkeypatch, m, payload, status=500 if oversize == "error_body" else 200)
        with pytest.raises(Exception, match="limit"):
            collect(streamed_request(plugin, m))


@pytest.mark.parametrize("status", [200, 201])
@pytest.mark.parametrize("wrapped", [False, True])
def test_dify_upload_native_success_shapes(monkeypatch, status, wrapped):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        payload = {"id": "fixture-upload"}
        if wrapped:
            payload = {"data": payload}
        http_fixture(monkeypatch, m, json.dumps(payload).encode(), status)
        result = asyncio.run(m.AsyncDifyClient("fixture").upload_file("file.txt", b"hi", "text/plain", "user"))
        assert result["id"] == "fixture-upload"


@pytest.mark.parametrize("payload", [b"null", b"[]", b'{"data":{}}', b'{"id":5}', b"bad fixture-private"])
def test_dify_invalid_upload_response_is_safe(monkeypatch, payload, caplog):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        http_fixture(monkeypatch, m, payload, 201)
        with pytest.raises(m.DifyAPIError) as error:
            asyncio.run(m.AsyncDifyClient("fixture").upload_file("file.txt", b"hi", "text/plain", "user"))
        assert "fixture-private" not in str(error.value) + caplog.text


def test_dify_upload_native_size_limit_prevents_http(monkeypatch):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        requests = http_fixture(monkeypatch, m, b'{"id":"file"}', 201)
        with pytest.raises(m.DifyAPIError, match="limit"):
            asyncio.run(
                m.AsyncDifyClient("fixture").upload_file("file", b"x" * (10 * 1024 * 1024 + 1), "text/plain", "user")
            )
        assert not requests


@pytest.mark.parametrize("plugin", ["dify-agent", "deerflow-agent", "langflow-agent", "weknora-agent"])
def test_native_nonstream_response_limit(monkeypatch, plugin):
    with load_runner(plugin):
        m = client_module(plugin)
        limit = (10 if plugin == "deerflow-agent" else 1) * 1024 * 1024
        payload = b'{"data":{"id":"' + b"x" * limit + b'"}}'
        http_fixture(monkeypatch, m, payload, 200)
        with pytest.raises(Exception, match="limit"):
            if plugin == "dify-agent":
                asyncio.run(m.AsyncDifyClient("fixture").upload_file("file", b"hi", "text/plain", "user"))
            elif plugin == "deerflow-agent":
                asyncio.run(m.AsyncDeerFlowClient().create_thread())
            elif plugin == "langflow-agent":
                collect(m.AsyncLangflowClient("fixture").run_flow("flow", "hi", stream=False))
            else:
                asyncio.run(m.AsyncWeKnoraClient("fixture").create_session())


@pytest.mark.parametrize("method", ["chat_messages", "workflow_run", "workflow_submit"])
def test_dify_sse_done_sentinel_and_object_validation(monkeypatch, method):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        payload = b'data: {"event":"message_end"}\n\ndata: [DONE]\n'
        http_fixture(monkeypatch, m, payload)
        client = m.AsyncDifyClient("fixture")
        if method == "chat_messages":
            stream = client.chat_messages({}, "hi", "user")
        elif method == "workflow_run":
            stream = client.workflow_run({}, "user")
        else:
            stream = client.workflow_submit("form", "workflow", {}, "user")
        assert collect(stream) == [{"event": "message_end"}]


@pytest.mark.parametrize("app", ["chat", "agent"])
def test_weknora_native_generated_answer_limit(app):
    with load_runner("weknora-agent") as (m, runner):

        class Client:
            async def agent_chat(self, **kwargs):
                yield {"response_type": "answer", "content": "x" * (1024 * 1024 + 1), "done": True}

            knowledge_chat = agent_chat

        config = runner._validate_config(
            ctx({"base-url": "https://example.invalid", "api-key": "fixture", "app-type": app})
        )
        fn = runner._run_runner_chat if app == "agent" else runner._run_knowledge_chat
        with pytest.raises(m.WeKnoraAPIError, match="limit"):
            collect(fn(ctx(), Client(), config, "session", "hello", "user"))


@pytest.mark.parametrize("plugin", ["dify-agent", "deerflow-agent", "langflow-agent", "weknora-agent"])
def test_bounded_nonstream_keeps_gzip_response_semantics(monkeypatch, plugin):
    import gzip

    with load_runner(plugin):
        m = client_module(plugin)
        data = {"id": "file", "thread_id": "thread", "data": {"id": "session"}}
        http_fixture(monkeypatch, m, gzip.compress(json.dumps(data).encode()), headers={"Content-Encoding": "gzip"})
        if plugin == "dify-agent":
            result = asyncio.run(m.AsyncDifyClient("fixture").upload_file("file", b"hi", "text/plain", "user"))
            assert result["id"] == "session"
        elif plugin == "deerflow-agent":
            assert asyncio.run(m.AsyncDeerFlowClient().create_thread()) == data
        elif plugin == "langflow-agent":
            assert collect(m.AsyncLangflowClient("fixture").run_flow("flow", "hi", stream=False)) == [data]
        else:
            assert asyncio.run(m.AsyncWeKnoraClient("fixture").create_session()) == "session"


@pytest.mark.parametrize("payload", [b"null", b"[]", b'"scalar"', b"not-json fixture-private"])
def test_dify_sse_nonobject_or_invalid_json_is_safe(monkeypatch, payload, caplog):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        http_fixture(monkeypatch, m, b"data: " + payload + b"\n")
        with pytest.raises(m.DifyAPIError) as error:
            collect(streamed_request("dify-agent", m))
        assert "fixture-private" not in str(error.value) + caplog.text


def test_weknora_native_skips_nonobject_sse(monkeypatch):
    with load_runner("weknora-agent"):
        m = client_module("weknora-agent")
        http_fixture(monkeypatch, m, b'data: []\ndata: null\ndata: {"response_type":"answer","content":"ok"}\n')
        assert collect(streamed_request("weknora-agent", m)) == [{"response_type": "answer", "content": "ok"}]


def test_dify_native_stream_emits_before_message_end():
    with load_runner("dify-agent") as (m, runner):
        reached_end = False

        class Client:
            async def chat_messages(self, **kwargs):
                nonlocal reached_end
                for _ in range(8):
                    yield {"event": "message", "answer": "x"}
                reached_end = True
                yield {"event": "message_end"}

        async def first():
            stream = runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], "chat", False)
            try:
                result = await anext(stream)
                assert not reached_end
                assert contents([result]) == ["xxxxxxxx"]
                assert result.data["chunk"]["is_final"] is False
            finally:
                await stream.aclose()

        asyncio.run(first())


def test_dify_answer_node_has_final_visible_response_without_message_events():
    with load_runner("dify-agent") as (m, runner):

        class Client:
            async def chat_messages(self, **kwargs):
                yield {"event": "node_finished", "data": {"node_type": "answer", "outputs": {"answer": "ok"}}}
                yield {"event": "workflow_finished", "data": {}}

        results = collect(runner._run_chat_or_agent(ctx(), Client(), {}, "hi", "user", "", [], "chatflow", False))
        assert kind(results[-1]) == "run.completed"
        finals = [r for r in results if kind(r) == "message.delta" and r.data["chunk"]["is_final"]]
        assert contents(finals) == ["ok"]


def test_dify_resume_actual_http_preserves_form_action_and_user(monkeypatch):
    with load_runner("dify-agent"):
        m = client_module("dify-agent")
        requests = http_fixture(monkeypatch, m, b'data: {"event":"workflow_finished","data":{}}\n')
        events = collect(
            m.AsyncDifyClient("fixture", "https://example.invalid/prefix/v1").workflow_submit(
                "form-fixture", "workflow-fixture", {"field": " exact "}, "group_fixture", "action-fixture"
            )
        )
        assert len(requests) == 2
        assert requests[0].method == "POST"
        assert requests[0].url.path == "/prefix/v1/form/human_input/form-fixture"
        assert json.loads(requests[0].content) == {
            "inputs": {"field": " exact "},
            "user": "group_fixture",
            "action": "action-fixture",
        }
        assert requests[1].method == "GET"
        assert requests[1].url.path == "/prefix/v1/workflow/workflow-fixture/events"
        assert requests[1].url.params["user"] == "group_fixture"
        assert events == [{"event": "workflow_finished", "data": {}}]


@pytest.mark.parametrize("plugin", ["dify-agent", "weknora-agent"])
def test_native_sse_line_limit_counts_utf8_bytes(monkeypatch, plugin):
    with load_runner(plugin):
        m = client_module(plugin)
        payload = b'data: {"content":"' + ("中" * (1024 * 1024 // 3 + 1)).encode() + b'"}\n'
        http_fixture(monkeypatch, m, payload)
        with pytest.raises(Exception, match="limit"):
            collect(streamed_request(plugin, m))


def test_deerflow_thread_response_keeps_native_10mib_budget(monkeypatch):
    with load_runner("deerflow-agent"):
        m = client_module("deerflow-agent")
        data = {"thread_id": "thread", "metadata": {"padding": "x" * (2 * 1024 * 1024)}}
        http_fixture(monkeypatch, m, json.dumps(data).encode())
        result = asyncio.run(m.AsyncDeerFlowClient().create_thread())
        assert result == data


def test_dify_native_file_url_is_downloaded_and_uploaded(monkeypatch):
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement

    with load_runner("dify-agent") as (m, runner):
        clientmod = client_module("dify-agent")
        requests = http_fixture(
            monkeypatch, clientmod, b"fixture document", headers={"content-type": "application/pdf"}
        )
        client = m.AsyncDifyClient("fixture")
        uploads = []

        async def upload(name, data, mime, user):
            uploads.append((name, data, mime, user))
            return {"id": "provider-upload"}

        client.upload_file = upload
        context = ctx()
        context.input.contents = [ContentElement.from_file_url("https://example.invalid/file.pdf", "report.pdf")]
        files = asyncio.run(runner._upload_input_files(context, client, "fixture-user"))
        assert len(requests) == 1 and requests[0].method == "GET"
        assert uploads == [("report.pdf", b"fixture document", "application/pdf", "fixture-user")]
        assert files == [{"type": "document", "transfer_method": "local_file", "upload_file_id": "provider-upload"}]


@pytest.mark.parametrize("url", ["file:///private/file", "ftp://example.invalid/file"])
def test_dify_file_url_does_not_gain_local_filesystem_access(url):
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement

    with load_runner("dify-agent") as (m, runner):
        context = ctx()
        context.input.contents = [ContentElement.from_file_url(url, "file")]
        with pytest.raises(m.DifyAPIError, match="HTTP"):
            asyncio.run(runner._upload_input_files(context, m.AsyncDifyClient("fixture"), "user"))


def test_dify_downloaded_file_keeps_native_upload_budget(monkeypatch):
    from langbot_plugin.api.entities.builtin.provider.message import ContentElement

    with load_runner("dify-agent") as (m, runner):
        clientmod = client_module("dify-agent")
        http_fixture(monkeypatch, clientmod, b"x" * (10 * 1024 * 1024 + 1))
        context = ctx()
        context.input.contents = [ContentElement.from_file_url("https://example.invalid/file", "file")]
        with pytest.raises(m.DifyAPIError, match="limit"):
            asyncio.run(runner._upload_input_files(context, m.AsyncDifyClient("fixture"), "user"))
