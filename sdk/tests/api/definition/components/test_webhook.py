from __future__ import annotations

import base64
import json

import pytest

from langbot_plugin.api.definition.components.webhook import (
    WEBHOOK_MAX_RESPONSE_BYTES,
    Webhook,
    WebhookRequest,
    WebhookResponse,
)


def test_webhook_kind():
    assert Webhook.__kind__ == "Webhook"


def test_webhook_request_round_trips_raw_body():
    body = b'{"event":"paid","amount":3}'
    request = WebhookRequest(
        method="post",
        path="/orders",
        query={"a": "1"},
        headers={"x-signature": "abc"},
        body=body,
        remote_addr="1.2.3.4",
    )
    wire = request.to_wire()
    assert wire["body_base64"] == base64.b64encode(body).decode()
    restored = WebhookRequest.from_wire(json.loads(json.dumps(wire)))
    assert restored.method == "POST"
    assert restored.body == body
    assert restored.json_body() == {"event": "paid", "amount": 3}
    assert restored.text() == body.decode()
    assert restored.headers == {"x-signature": "abc"}


def test_webhook_request_from_empty_wire():
    restored = WebhookRequest.from_wire({})
    assert restored.method == "POST"
    assert restored.body == b""
    assert restored.json_body() is None


@pytest.mark.parametrize(
    ("value", "status", "content_type", "body"),
    [
        (None, 204, None, b""),
        ("ok", 200, "text/plain; charset=utf-8", b"ok"),
        (b"\x00", 200, "application/octet-stream", b"\x00"),
        ({"ok": True}, 200, "application/json", b'{"ok": true}'),
    ],
)
def test_webhook_response_coerce(value, status, content_type, body):
    response = WebhookResponse.coerce(value)
    assert response.status == status
    assert response.headers.get("content-type") == content_type
    assert response.body == body


def test_webhook_response_to_wire_limits():
    with pytest.raises(ValueError):
        WebhookResponse(body=b"x" * (WEBHOOK_MAX_RESPONSE_BYTES + 1)).to_wire()
    with pytest.raises(ValueError):
        WebhookResponse(status=42).to_wire()
    wire = WebhookResponse.json({"a": 1}, status=201).to_wire()
    assert wire["status"] == 201
    assert base64.b64decode(wire["body_base64"]) == b'{"a": 1}'


async def test_default_handle_is_not_implemented():
    response = await Webhook().handle(WebhookRequest(method="GET"))
    assert response.status == 501
