"""Credential-bearing request targets never reach httpx's INFO request log."""

import asyncio
import logging

import httpx
import pkg.dify_client as dify_client
from pkg.dify_client import AsyncDifyClient

FORM_TOKEN = "form-secret-token"
SIGNED_URL = "https://files.example/media/signed-path/image.png?sig=secret-signature&rkey=abc"


def _mock(monkeypatch, handler):
    real = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(dify_client.httpx, "AsyncClient", lambda **kwargs: real(transport=transport, **kwargs))


async def _collect(stream):
    return [item async for item in stream]


def _httpx_messages(caplog):
    return [record.getMessage() for record in caplog.records if record.name == "httpx"]


def test_form_token_is_redacted_in_httpx_log(monkeypatch, caplog):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"event": "workflow_finished", "data": {"outputs": {"answer": "ok"}}}\n\n',
            )
        raise AssertionError("unexpected request")

    _mock(monkeypatch, handler)
    caplog.set_level(logging.INFO, logger="httpx")
    client = AsyncDifyClient(api_key="key", base_url="https://dify.example/v1")
    events = asyncio.run(_collect(client.workflow_submit(FORM_TOKEN, "run-1", {}, "user-1", "approve")))

    assert events[0]["event"] == "workflow_finished"
    messages = _httpx_messages(caplog)
    assert messages == ['HTTP Request: POST https://dify.example/v1/form/human_input/[redacted] "HTTP/1.1 200 OK"']
    assert all(FORM_TOKEN not in record.getMessage() for record in caplog.records)


def test_signed_input_url_is_redacted_in_httpx_log(monkeypatch, caplog):
    _mock(monkeypatch, lambda request: httpx.Response(200, headers={"content-type": "image/png"}, content=b"png"))
    caplog.set_level(logging.INFO, logger="httpx")
    client = AsyncDifyClient(api_key="key", base_url="https://dify.example/v1")
    body, mime = asyncio.run(client.download_file(SIGNED_URL))

    assert (body, mime) == (b"png", "image/png")
    assert _httpx_messages(caplog) == ['HTTP Request: GET https://files.example/[redacted] "HTTP/1.1 200 OK"']
    assert all("secret-signature" not in r.getMessage() and "signed-path" not in r.getMessage() for r in caplog.records)


def test_other_requests_keep_their_normal_log_line(monkeypatch, caplog):
    """The filter is inert outside a redacted block, including after one."""

    _mock(monkeypatch, lambda request: httpx.Response(200, content=b"ok"))
    caplog.set_level(logging.INFO, logger="httpx")

    async def plain_request():
        async with httpx.AsyncClient() as client:
            await client.get("https://other.example/path?q=1")

    asyncio.run(AsyncDifyClient(api_key="key").download_file(SIGNED_URL))
    asyncio.run(plain_request())

    assert _httpx_messages(caplog)[-1] == 'HTTP Request: GET https://other.example/path?q=1 "HTTP/1.1 200 OK"'
