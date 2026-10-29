"""Native resource limits through real runners/clients; offline transports only."""

import asyncio
import base64
import json
import sys

import pytest
from test_native_parity_reasoning_output import (
    collect,
    context,
    drive,
    event_type,
    messages,
    mock_vendor,
)
from test_native_parity_reasoning_output import (
    parity_module_loader as _parity_module_loader,
)

parity_module_loader = _parity_module_loader

MEDIA_LIMIT = 10 * 1024 * 1024
TEXT_LIMIT = 1024 * 1024
SECRET = "fixture-upstream-credential-do-not-echo"


@pytest.mark.parametrize("name", ["coze", "tbox", "dify"])
@pytest.mark.parametrize("kind", ["encoded", "data-uri", "decoded", "bytes", "bytearray", "utf8"])
def test_base64_runner_rejects_before_upload(parity_module_loader, monkeypatch, name, kind):
    module = parity_module_loader(name)
    calls = []
    decode = base64.b64decode

    def tracked_decode(*args, **kwargs):
        calls.append("decode")
        return decode(*args, **kwargs)

    monkeypatch.setattr(module.base64, "b64decode", tracked_decode)
    if kind in {"encoded", "data-uri"}:
        value = "A" * (4 * ((MEDIA_LIMIT + 2) // 3) + 8)
        if kind == "data-uri":
            value = "data:image/png;base64," + value
    elif kind == "decoded":
        value = base64.b64encode(b"x" * (MEDIA_LIMIT + 1)).decode()
    elif kind == "utf8":
        value = "界" * (MEDIA_LIMIT // 3 + 1)
    else:
        value = b"x" * (MEDIA_LIMIT + 1)
        if kind == "bytearray":
            value = bytearray(value)

    async def upload(*args, **kwargs):
        calls.append("upload")
        raise AssertionError("oversized input reached upload")

    cls = getattr(module, {"coze": "AsyncCozeClient", "tbox": "AsyncTboxClient", "dify": "AsyncDifyClient"}[name])
    monkeypatch.setattr(cls, "upload_file", upload)
    ctx = context({"api-key": "fixture", "bot-id": "bot", "app-id": "app", "base-url": "https://fixture.invalid/v1"})
    # Validated SDK input shape, with an attachment object for bytes compatibility.
    from types import SimpleNamespace

    ctx.input.attachments = [SimpleNamespace(type="image", content=value, name="fixture.png", content_type="image/png")]
    events = asyncio.run(collect(object.__new__(module.DefaultRunner).run(ctx)))
    assert event_type(events[-1]) == "run.failed"
    assert events[-1].data["code"] == f"{name}.input_error"
    assert "upload" not in calls
    if kind in {"encoded", "data-uri"}:
        assert "decode" not in calls


@pytest.mark.parametrize("name", ["coze", "tbox", "dify"])
@pytest.mark.parametrize(
    "value,expected",
    [
        ("aGVsbG8=", b"hello"),
        ("data:text/plain;base64,aGVsbG8=", b"hello"),
        ("plain text!", b"plain text!"),
        ("界", "界".encode()),
        (b"file", b"file"),
        (bytearray(b"file"), b"file"),
    ],
)
def test_bounded_decoder_keeps_normal_inputs(parity_module_loader, name, value, expected):
    assert parity_module_loader(name)._decode_content(value) == expected


class Body:
    def __init__(self, chunks, failure=None):
        self.chunks = chunks
        self.failure = failure
        self.reads = 0
        self.sizes = []

    async def iter_chunked(self, size):
        self.sizes.append(size)
        for chunk in self.chunks:
            self.reads += 1
            yield chunk
        if self.failure:
            raise self.failure


class Response:
    def __init__(self, status=200, chunks=(), length=None, failure=None):
        self.status = status
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.content = Body(chunks, failure)
        self.closed = False
        self.buffered = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def text(self):
        self.buffered = True
        return b"".join(self.content.chunks).decode(errors="replace")

    async def json(self):
        return json.loads(await self.text())


def coze_client(loader, monkeypatch, response):
    loader("coze")
    module = sys.modules["pkg.coze_client"]

    class Session:
        closed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr(module.aiohttp, "ClientSession", lambda **kwargs: Session())
    client = module.AsyncCozeClient(api_key=SECRET)
    client._session = Session()
    return module, client


async def coze_request(client, operation):
    if operation == "upload":
        return await client.upload_file(b"file", "fixture.txt")
    return await collect(client.chat_messages(bot_id="bot", user_id="user"))


@pytest.mark.parametrize("operation,status", [("upload", 200), ("upload", 500), ("chat", 500)])
@pytest.mark.parametrize("mode", ["length", "body", "chunks"])
def test_coze_bounded_response_rejects_oversize(parity_module_loader, monkeypatch, operation, status, mode):
    chunks = [b"x" * (TEXT_LIMIT + 1)] if mode != "chunks" else [b"x" * 65536] * 18
    response = Response(status, chunks, TEXT_LIMIT + 1 if mode == "length" else None)
    module, client = coze_client(parity_module_loader, monkeypatch, response)
    with pytest.raises(module.CozeAPIError) as exc:
        asyncio.run(coze_request(client, operation))
    assert exc.value.code == "coze.response_limit"
    assert response.closed and not response.buffered
    if mode == "length":
        assert response.content.reads == 0
    if mode == "chunks":
        assert response.content.reads == 17
    assert SECRET not in str(exc.value)


@pytest.mark.parametrize("operation", ["upload", "chat"])
@pytest.mark.parametrize("failure_kind", ["http", "transport", "cancel"])
def test_coze_bounded_errors_are_safe_and_cancellable(parity_module_loader, monkeypatch, operation, failure_kind):
    failure = {"http": None, "transport": RuntimeError(SECRET), "cancel": asyncio.CancelledError()}[failure_kind]
    response = Response(500, [SECRET.encode()], failure=failure)
    module, client = coze_client(parity_module_loader, monkeypatch, response)
    expected = asyncio.CancelledError if failure_kind == "cancel" else module.CozeAPIError
    with pytest.raises(expected) as exc:
        asyncio.run(coze_request(client, operation))
    assert SECRET not in str(exc.value)
    assert response.closed and not response.buffered


@pytest.mark.parametrize("payload", [b"not-json-" + SECRET.encode(), json.dumps({"code": 1, "msg": SECRET}).encode()])
def test_coze_upload_parse_and_api_errors_do_not_echo_body(parity_module_loader, monkeypatch, payload):
    response = Response(200, [payload])
    module, client = coze_client(parity_module_loader, monkeypatch, response)
    with pytest.raises(module.CozeAPIError) as exc:
        asyncio.run(client.upload_file(b"file"))
    assert SECRET not in str(exc.value)
    assert response.closed and not response.buffered


def test_coze_upload_parses_incremental_normal_json(parity_module_loader, monkeypatch):
    response = Response(200, [b'{"code":0,', b'"data":{"id":"file-1"}}'])
    _, client = coze_client(parity_module_loader, monkeypatch, response)
    assert asyncio.run(client.upload_file(b"file")) == "file-1"
    assert response.closed and not response.buffered
    assert response.content.reads == 2


@pytest.mark.parametrize("mode", ["coze", "tbox", "tbox-blocking", "dashscope"])
def test_rendered_think_markers_cannot_exceed_output_limit(parity_module_loader, monkeypatch, mode):
    events, _ = drive(parity_module_loader, monkeypatch, mode, {}, ["a" * (TEXT_LIMIT - 1)], reasoning="r")
    assert event_type(events[-1]) == "run.failed"
    assert events[-1].data["code"] == f"{mode.split('-')[0]}.response_limit"
    assert all(len(chunk["content"]) <= TEXT_LIMIT for chunk in messages(events))


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
