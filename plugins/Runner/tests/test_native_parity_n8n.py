"""Native 9b7ba0d6 n8n contracts through the real SDK Runner + HTTPX.

Only HTTP transport is replaced: no stub Runner, SDK, client or response parser.
Synthetic credentials and provider responses; no external requests or paid calls.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import logging
import sys
from pathlib import Path

import httpx
import jwt
import pytest
from langbot_plugin.api.entities.builtin.runner import RunnerContext

ROOT = Path(__file__).resolve().parents[1] / "n8n-agent"
LIMIT = 1024 * 1024  # Native _MAX_N8N_RESPONSE_CHARS, not a user setting.


@pytest.fixture
def runner_module():
    saved = {k: v for k, v in sys.modules.items() if k == "pkg" or k.startswith("pkg.")}
    for name in saved:
        del sys.modules[name]
    sys.path.insert(0, str(ROOT))
    try:
        spec = importlib.util.spec_from_file_location("native_parity_n8n_runner", ROOT / "components/runner/default.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.path.remove(str(ROOT))
        for name in list(sys.modules):
            if name == "pkg" or name.startswith("pkg."):
                del sys.modules[name]
        sys.modules.update(saved)


class Body(httpx.AsyncByteStream):
    def __init__(self, chunks=(), *, blocked=False):
        self.chunks = chunks
        self.blocked = blocked
        self.reads = 0
        self.closed = False

    async def __aiter__(self):
        self.reads += 1
        if self.blocked:
            await asyncio.Event().wait()
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def context(config=None, *, state=None, params=None, streaming=True):
    return RunnerContext.model_validate(
        {
            "run_id": "n8n-parity-run",
            "trigger": {"type": "message.received"},
            "event": {"event_id": "event", "event_type": "message.received", "source": "test"},
            "conversation": {"conversation_id": "host-conversation", "session_id": "host-session"},
            "actor": {"actor_type": "user", "actor_id": "synthetic-sender"},
            "input": {"text": "hello 世界"},
            "delivery": {"surface": "test", "supports_streaming": streaming},
            "resources": {},
            "runtime": {},
            "state": {"conversation": state or {}},
            "adapter": {"extra": {"params": params or {}}},
            "config": {"webhook-url": "https://n8n.invalid/webhook/test", **(config or {})},
        }
    )


def wire(monkeypatch, body, status=200, *, delay: float = 0, error=None):
    requests = []
    original = httpx.AsyncClient

    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        if error:
            raise error
        return httpx.Response(status, stream=body)

    def client(**kwargs):
        kwargs["trust_env"] = False
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(httpx, "AsyncClient", client)
    return requests


async def collect(runner_module, ctx):
    runner = runner_module.DefaultRunner()
    results = await asyncio.wait_for(_collect(runner.run(ctx)), timeout=1)
    return [r.model_dump(mode="json") for r in results]


async def _collect(generator):
    return [r async for r in generator]


def messages(results):
    return [r["data"]["chunk"] for r in results if r["type"] == "message.delta"]


def assert_success(results):
    assert results[-1]["type"] == "run.completed", results
    assert not any(r["type"] == "run.failed" for r in results), results


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 201, 202, 204, 206, 299])
@pytest.mark.parametrize("content", [b'{"response":"must not be sent"}', b"", b"plain acknowledgement"])
async def test_ignore_success_never_reads_body(runner_module, monkeypatch, status, content):
    body = Body([content])
    requests = wire(monkeypatch, body, status)
    results = await collect(runner_module, context({"response-handling": "ignore"}))
    assert_success(results)
    assert messages(results) == []
    assert body.reads == 0
    assert body.closed
    assert len(requests) == 1
    assert len([r for r in results if r["type"] == "state.updated"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 202, 204])
async def test_ignore_does_not_wait_for_blocked_body(runner_module, monkeypatch, status):
    body = Body(blocked=True)
    wire(monkeypatch, body, status)
    results = await collect(runner_module, context({"response-handling": "ignore"}))
    assert_success(results)
    assert messages(results) == []
    assert body.reads == 0
    assert body.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,status", [("reply", 201), ("reply", 202), ("reply", 204), ("ignore", 300), ("ignore", 401), ("ignore", 500)]
)
async def test_error_status_fails_without_echoing_remote_secrets(runner_module, monkeypatch, mode, status, caplog):
    secret = "synthetic-remote-credential"
    body = Body([secret.encode()])
    wire(monkeypatch, body, status)
    with caplog.at_level(logging.DEBUG, logger="pkg.n8n_client"):
        results = await collect(runner_module, context({"response-handling": mode}))
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.http_error"
    assert str(status) in results[0]["data"]["error"]
    assert secret not in json.dumps(results) + caplog.text
    assert body.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["invalid", "", None, False, []])
async def test_invalid_response_mode_fails_before_request(runner_module, monkeypatch, mode):
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    results = await collect(runner_module, context({"response-handling": mode}))
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.config_invalid"
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config,body,expected",
    [
        ({}, b'{"response":"hello"}', "hello"),
        ({"response-handling": "reply", "output-key": "answer"}, b'{"answer":"custom"}', "custom"),
        ({}, b'{"other":"hello"}', '{"other": "hello"}'),
        ({}, b'["hello"]', '["hello"]'),
        ({}, b"plain text", "plain text"),
    ],
)
@pytest.mark.parametrize("streaming", [True, False])
async def test_reply_mapping_and_default(runner_module, monkeypatch, config, body, expected, streaming):
    wire(monkeypatch, Body([body]))
    results = await collect(runner_module, context(config, streaming=streaming))
    assert_success(results)
    assert messages(results)[-1]["content"] == expected
    assert messages(results)[-1]["is_final"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("content,expected", [("hello", "hello"), (123, "123"), (None, "None")])
async def test_reply_stream_item_content_matches_native_string_conversion(
    runner_module, monkeypatch, content, expected
):
    chunks = [json.dumps({"type": "item", "content": content}).encode(), b'{"type":"item","content":"!"}{"type":"end"}']
    wire(monkeypatch, Body(chunks))
    results = await collect(runner_module, context())
    assert_success(results)
    assert messages(results)[-1]["content"] == expected + "!"
    assert messages(results)[-1]["is_final"] is True


@pytest.mark.asyncio
async def test_reply_split_utf8_preserves_text(runner_module, monkeypatch):
    content = '{"response":"你好"}'.encode()
    chunks = [bytes([b]) for b in content]
    wire(monkeypatch, Body(chunks))
    results = await collect(runner_module, context())
    assert_success(results)
    assert messages(results)[-1]["content"] == "你好"


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_reply_response_size_is_bounded(runner_module, monkeypatch, streaming):
    chunks = [b'{"type":"item","content":"' + b"x" * 1024 + b'"}'] * 1024 if streaming else [b"x" * (LIMIT + 1)]
    body = Body(chunks)
    wire(monkeypatch, body)
    results = await collect(runner_module, context())
    assert results[-1]["type"] == "run.failed"
    assert results[-1]["data"]["code"] == "n8n.response_too_large"
    assert "runtime limit" in results[-1]["data"]["error"]
    assert not any(r["type"] == "run.completed" for r in results)
    assert body.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("auth", ["none", "basic", "jwt", "header", "header-empty"])
@pytest.mark.parametrize("mode", ["reply", "ignore"])
async def test_request_auth_shapes_no_credential_logging(runner_module, monkeypatch, caplog, auth, mode):
    config = {
        "response-handling": mode,
        "auth-type": "header" if auth == "header-empty" else auth,
        "basic-username": "synthetic-private-user",
        "basic-password": "synthetic-password",
        "jwt-secret": "synthetic-jwt-secret-32-characters-long",
        "jwt-algorithm": "HS256",
        "header-name": "X-Workflow-Auth",
        "header-value": "" if auth == "header-empty" else "synthetic-header-secret",
    }
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    with caplog.at_level(logging.DEBUG, logger="pkg.n8n_client"):
        results = await collect(runner_module, context(config))
    assert_success(results)
    request = requests[0]
    assert request.method == "POST"
    assert request.url == "https://n8n.invalid/webhook/test"
    assert request.headers["content-type"] == "application/json"
    if auth == "none":
        assert "authorization" not in request.headers
    elif auth == "basic":
        expected = base64.b64encode(b"synthetic-private-user:synthetic-password").decode()
        assert request.headers["authorization"] == "Basic " + expected
    elif auth == "jwt":
        token = request.headers["authorization"].removeprefix("Bearer ")
        claims = jwt.decode(token, config["jwt-secret"], algorithms=["HS256"])
        assert claims["sub"] == "n8n-webhook"
        assert claims["exp"] - claims["iat"] == 3600
    else:
        assert request.headers["X-Workflow-Auth"] == config["header-value"]
    for key in ("basic-username", "basic-password", "jwt-secret", "header-value"):
        if config[key]:
            assert config[key] not in caplog.text


@pytest.mark.asyncio
async def test_request_fields_and_runner_owned_state_survive_ignore(runner_module, monkeypatch):
    requests = wire(monkeypatch, Body(), 204)
    state = {"external.conversation_id": "persisted-conversation", "external.session_id": "persisted-session"}
    ctx = context(
        {"response-handling": "ignore"},
        state=state,
        params={"custom": "value", "conversation_id": "stale", "session_id": "stale", "user_id": "stale"},
    )
    results = await collect(runner_module, ctx)
    assert_success(results)
    assert not any(r["type"] == "state.updated" for r in results)
    payload = json.loads(requests[0].content)
    assert payload == {
        "chatInput": "hello 世界",
        "message": "hello 世界",
        "user_message_text": "hello 世界",
        "conversation_id": "persisted-conversation",
        "session_id": "persisted-session",
        "user_id": "user_synthetic-sender",
        "msg_create_time": "",
        "custom": "value",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["reply", "ignore"])
async def test_timeout_includes_waiting_for_response_headers(runner_module, monkeypatch, mode):
    wire(monkeypatch, Body([b'{"response":"ok"}']), delay=0.1)
    results = await collect(runner_module, context({"response-handling": mode, "timeout": 0.03}))
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.timeout"


@pytest.mark.asyncio
async def test_reply_timeout_is_total_not_only_per_chunk(runner_module, monkeypatch):
    class SlowBody(Body):
        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(0.01)
                yield b'{"type":"item","content":"x"}'

    body = SlowBody()
    wire(monkeypatch, body)
    results = await collect(runner_module, context({"timeout": 0.04}))
    assert results[-1]["type"] == "run.failed"
    assert results[-1]["data"]["code"] == "n8n.timeout"
    assert body.closed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [httpx.ConnectError("synthetic-sensitive-url"), ValueError("synthetic-sensitive-url")]
)
async def test_transport_failures_do_not_expose_sensitive_exception_text(runner_module, monkeypatch, caplog, error):
    wire(monkeypatch, Body(), error=error)
    with caplog.at_level(logging.DEBUG):
        results = await collect(runner_module, context({"response-handling": "ignore"}))
    assert [r["type"] for r in results] == ["run.failed"]
    assert "synthetic-sensitive-url" not in json.dumps(results) + caplog.text


@pytest.mark.asyncio
async def test_header_auth_without_name_does_not_send_unauthenticated_request(runner_module, monkeypatch):
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    results = await collect(
        runner_module, context({"auth-type": "header", "header-name": "", "header-value": "synthetic-secret"})
    )
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.config_invalid"
    assert requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize("timestamp", [0, None, "", 1700000000])
async def test_timestamp_parameter_keeps_exact_value(runner_module, monkeypatch, timestamp):
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    results = await collect(runner_module, context(params={"msg_create_time": timestamp}))
    assert_success(results)
    assert json.loads(requests[0].content)["msg_create_time"] == timestamp


@pytest.mark.asyncio
@pytest.mark.parametrize("encoding", [None, "utf-8", "latin1"])
async def test_basic_auth_encoding_supports_native_latin1_without_changing_utf8_default(
    runner_module, monkeypatch, encoding
):
    config = {"auth-type": "basic", "basic-username": "tést", "basic-password": "synthetic-päss"}
    if encoding is not None:
        config["basic-encoding"] = encoding
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    results = await collect(runner_module, context(config))
    assert_success(results)
    expected = base64.b64encode("tést:synthetic-päss".encode(encoding or "utf-8")).decode()
    assert requests[0].headers["authorization"] == "Basic " + expected


@pytest.mark.asyncio
async def test_invalid_basic_encoding_fails_before_http(runner_module, monkeypatch):
    requests = wire(monkeypatch, Body([b'{"response":"ok"}']))
    results = await collect(runner_module, context({"auth-type": "basic", "basic-encoding": "invalid"}))
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.config_invalid"
    assert requests == []


@pytest.mark.asyncio
async def test_reply_empty_output_remains_explicit_failure(runner_module, monkeypatch):
    wire(monkeypatch, Body([b'{"response":""}']))
    results = await collect(runner_module, context())
    assert [r["type"] for r in results] == ["run.failed"]
    assert results[0]["data"]["code"] == "n8n.empty_response"


@pytest.mark.asyncio
async def test_reply_accepts_native_character_limit_inclusive(runner_module, monkeypatch):
    wire(monkeypatch, Body([b"x" * LIMIT]))
    results = await collect(runner_module, context())
    assert_success(results)
    assert len(messages(results)[-1]["content"]) == LIMIT


@pytest.mark.asyncio
async def test_ignore_two_turns_reuse_state_updates(runner_module, monkeypatch):
    requests = wire(monkeypatch, Body(), 202)
    first = await collect(runner_module, context({"response-handling": "ignore"}))
    assert_success(first)
    state = {r["data"]["key"]: r["data"]["value"] for r in first if r["type"] == "state.updated"}
    second = await collect(runner_module, context({"response-handling": "ignore"}, state=state))
    assert_success(second)
    assert json.loads(requests[0].content) == json.loads(requests[1].content)
    assert not any(r["type"] == "state.updated" for r in second)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 204, 500])
async def test_ignore_real_http_socket_closes_without_body(runner_module, monkeypatch, status):
    # No mocked HTTP client/transport: send headers but withhold the body.
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    closed = asyncio.Event()
    captured = []

    async def serve(reader, writer):
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            size = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            captured.append(json.loads(await reader.readexactly(size)))
            writer.write(f"HTTP/1.1 {status} Fixture\r\nContent-Length: 1000000\r\nConnection: close\r\n\r\n".encode())
            await writer.drain()
            await reader.read()  # The real client must close instead of waiting for a body.
        finally:
            writer.close()
            await writer.wait_closed()
            closed.set()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    async with server:
        port = server.sockets[0].getsockname()[1]
        ctx = context({"response-handling": "ignore", "webhook-url": f"http://127.0.0.1:{port}/webhook"})
        results = await collect(runner_module, ctx)
        await asyncio.wait_for(closed.wait(), timeout=1)
    assert captured[0]["message"] == "hello 世界"
    assert messages(results) == []
    if status == 500:
        assert [r["type"] for r in results] == ["run.failed"]
        assert results[0]["data"]["code"] == "n8n.http_error"
    else:
        assert_success(results)
