from __future__ import annotations

from types import SimpleNamespace

import pytest

from components.event_listener.context_bridge import ContextBridge


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def prepare_context(self, **_kwargs):
        self.calls.append("prepare")
        return SimpleNamespace(
            data={
                "status": "ready",
                "content": "Remembered project decision",
                "content_bytes": 27,
            },
            request_id="req-prepare",
        )

    async def capture_content(self, **kwargs):
        self.calls.append("capture")
        assert kwargs["content"].endswith("hello")
        return SimpleNamespace(data={"status": "accepted"}, request_id="req-capture")


class FakeSettings:
    scope_mode = "session"
    auto_recall = True
    capture_user_messages = True
    max_context_bytes = 4000

    def __init__(self, client: "FakeClient") -> None:
        self._client = client

    def new_client(self) -> "FakeClient":
        return self._client


class FakePlugin:
    def __init__(self) -> None:
        self.client = FakeClient()

    def settings(self) -> FakeSettings:
        return FakeSettings(self.client)

    async def resolve_identity(self, **_kwargs):
        return SimpleNamespace(scope_id="scope-1", request_id="req-scope")

    @staticmethod
    def source_id(**_kwargs) -> str:
        return "langbot-source-1"


class FakeEventContext:
    query_id = 9
    query_uuid = "query-uuid"

    def __init__(self) -> None:
        self.event = SimpleNamespace(session_name="person_1", prompt=[])
        self.state = None

    async def get_query_vars(self):
        return {"user_message_text": "hello", "sender_id": "u1", "sender_name": "Alice"}

    async def get_bot_uuid(self):
        return "bot-1"

    async def set_query_var(self, key, value):
        assert key == "_powercontext_context"
        self.state = value


@pytest.mark.asyncio
async def test_bridge_prepares_before_capture_and_injects_bounded_context() -> None:
    bridge = ContextBridge()
    bridge.plugin = FakePlugin()
    event_context = FakeEventContext()

    await bridge._process_turn(event_context)

    assert bridge.plugin.client.calls == ["prepare", "capture"]
    assert len(event_context.event.prompt) == 1
    injected = event_context.event.prompt[0].content
    assert "untrusted historical context" in injected
    assert "Remembered project decision" in injected
    assert event_context.state["injected"] is True
    assert event_context.state["source_capture"] == "accepted"


@pytest.mark.asyncio
async def test_bridge_fails_open_when_scope_is_unavailable() -> None:
    plugin = FakePlugin()

    async def fail(**_kwargs):
        raise RuntimeError("unscoped")

    plugin.resolve_identity = fail
    bridge = ContextBridge()
    bridge.plugin = plugin
    event_context = FakeEventContext()

    await bridge._process_turn(event_context)

    assert event_context.event.prompt == []
    assert event_context.state["status"] == "unavailable"
    assert plugin.client.calls == []
