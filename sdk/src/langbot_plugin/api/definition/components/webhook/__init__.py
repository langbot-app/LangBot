"""Webhook component: a public HTTP ingress owned by one plugin installation.

LangBot exposes every ``Webhook`` component of an installed plugin at::

    {webhook_prefix}/plugins/webhooks/{installation_uuid}/{webhook_name}[/{sub_path}]

The URL is unauthenticated, exactly like a Bot's platform webhook, so the
component is responsible for verifying the caller (shared secret, HMAC
signature over :attr:`WebhookRequest.body`, ...). Inside :meth:`Webhook.handle`
the installation is bound, so Host APIs such as ``send_message``, plugin
storage and ``invoke_llm`` work the same way they do in event listeners.
"""

from __future__ import annotations

import base64
import json
import typing

import pydantic

from langbot_plugin.api.definition.components.base import BaseComponent

WEBHOOK_MAX_BODY_BYTES = 1024 * 1024
"""Largest request body LangBot forwards to a Webhook component (1 MiB)."""

WEBHOOK_MAX_RESPONSE_BYTES = 1024 * 1024
"""Largest response body a Webhook component may return (1 MiB)."""


class WebhookRequest(pydantic.BaseModel):
    """One inbound HTTP request delivered to a Webhook component."""

    method: str
    """Upper-case HTTP method."""

    path: str = ""
    """Sub-path after the webhook name, ``""`` or starting with ``/``."""

    query: dict[str, str] = pydantic.Field(default_factory=dict)
    """Query parameters (last value wins for repeated keys)."""

    headers: dict[str, str] = pydantic.Field(default_factory=dict)
    """Request headers with lower-case names. ``Cookie`` is never forwarded."""

    body: bytes = b""
    """Raw request body, suitable for signature verification."""

    remote_addr: str | None = None
    """Client address as seen by LangBot (may be a proxy)."""

    def text(self, encoding: str = "utf-8") -> str:
        """Decode the body as text."""
        return self.body.decode(encoding, errors="replace")

    def json_body(self) -> typing.Any:
        """Parse the body as JSON. Raises ``ValueError`` when it is not JSON."""
        if not self.body:
            return None
        return json.loads(self.body)

    def to_wire(self) -> dict[str, typing.Any]:
        return {
            "method": self.method,
            "path": self.path,
            "query": dict(self.query),
            "headers": dict(self.headers),
            "body_base64": base64.b64encode(self.body).decode("ascii"),
            "remote_addr": self.remote_addr,
        }

    @classmethod
    def from_wire(cls, data: dict[str, typing.Any]) -> WebhookRequest:
        raw = data.get("body_base64") or ""
        return cls(
            method=str(data.get("method") or "POST").upper(),
            path=str(data.get("path") or ""),
            query=dict(data.get("query") or {}),
            headers=dict(data.get("headers") or {}),
            body=base64.b64decode(raw) if raw else b"",
            remote_addr=data.get("remote_addr"),
        )


class WebhookResponse(pydantic.BaseModel):
    """HTTP response returned by a Webhook component."""

    status: int = 200
    headers: dict[str, str] = pydantic.Field(default_factory=dict)
    body: bytes = b""

    @classmethod
    def json(cls, data: typing.Any, status: int = 200) -> WebhookResponse:  # type: ignore[override]
        return cls(
            status=status,
            headers={"content-type": "application/json"},
            body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        )

    @classmethod
    def text(cls, text: str, status: int = 200) -> WebhookResponse:
        return cls(
            status=status,
            headers={"content-type": "text/plain; charset=utf-8"},
            body=text.encode("utf-8"),
        )

    @classmethod
    def empty(cls, status: int = 204) -> WebhookResponse:
        return cls(status=status)

    @classmethod
    def coerce(cls, value: typing.Any) -> WebhookResponse:
        """Accept convenient return values from :meth:`Webhook.handle`."""
        if isinstance(value, WebhookResponse):
            return value
        if value is None:
            return cls.empty(204)
        if isinstance(value, bytes):
            return cls(body=value, headers={"content-type": "application/octet-stream"})
        if isinstance(value, str):
            return cls.text(value)
        return cls.json(value)

    def to_wire(self) -> dict[str, typing.Any]:
        if len(self.body) > WEBHOOK_MAX_RESPONSE_BYTES:
            raise ValueError("Webhook response body exceeds the 1 MiB limit")
        if not 100 <= self.status <= 599:
            raise ValueError("Webhook response status must be between 100 and 599")
        return {
            "status": self.status,
            "headers": {str(k): str(v) for k, v in self.headers.items()},
            "body_base64": base64.b64encode(self.body).decode("ascii"),
        }


class Webhook(BaseComponent):
    """The webhook component.

    Override :meth:`handle` to receive pushes from external systems and, for
    example, proactively message users with ``self.plugin.send_message``.
    """

    __kind__ = "Webhook"

    async def handle(self, request: WebhookRequest) -> WebhookResponse:
        """Handle one inbound HTTP request.

        Return a :class:`WebhookResponse`; ``None``, ``str``, ``bytes`` and
        JSON-serializable values are converted automatically.
        """
        return WebhookResponse.text("Not implemented", status=501)


__all__ = [
    "WEBHOOK_MAX_BODY_BYTES",
    "WEBHOOK_MAX_RESPONSE_BYTES",
    "Webhook",
    "WebhookRequest",
    "WebhookResponse",
]
