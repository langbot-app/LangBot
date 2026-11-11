"""Exercise every public event through typed and fallback processor handlers."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from langbot_plugin.api.definition.components.runner import Runner, RunnerContext
from langbot_plugin.api.entities.builtin.platform import events

EVENT_TYPES = tuple(events.EBAEvent.__subclasses__())


def run_context(*, run_id, event, config=None):
    return RunnerContext.model_validate(
        {
            "run_id": run_id,
            "trigger": {"type": event.data.get("type") or "invalid"},
            "event": {
                "event_id": run_id,
                "event_type": event.data.get("type") or "invalid",
                "source": "test",
                "data": event.data,
            },
            "input": {},
            "delivery": {"surface": "test"},
            "resources": {},
            "runtime": {},
            "config": config or {},
        }
    )


def payload(event_class, populated):
    data = {"type": event_class.model_fields["type"].default}
    if event_class is events.FeedbackReceivedEvent:
        data.update(feedback_id="feedback-1", feedback_type=1)
    if event_class is events.InteractionCallbackEvent:
        data["callback_token"] = "test-token"
    if populated:
        values = {
            "timestamp": 1788820000.25,
            "bot_uuid": "bot-test",
            "adapter_name": "test",
            "member": {"id": 42, "nickname": "成员 🧩"},
            "user": {"id": "user-1", "nickname": "User"},
            "sender": {"id": "sender", "nickname": "Sender"},
            "editor": {"id": "editor", "nickname": "Editor"},
            "operator": {"id": "operator"},
            "inviter": {"id": "inviter"},
            "group": {"id": 100, "name": "Group"},
            "message_id": "99",
            "chat_id": "100",
            "chat_type": "group",
            "message_chain": [
                {"type": "Plain", "text": "Unicode 你好 🧩"},
                {"type": "Image", "url": "https://example.com/a.png"},
            ],
            "new_content": [{"type": "Plain", "text": "Edited 🧩"}],
            "reaction": "🧩",
            "is_add": False,
            "is_kicked": True,
            "duration": 0,
            "join_type": "invite",
            "changed_fields": ["name"],
            "request_id": "request-1",
            "message": "Hello",
            "feedback_type": 3,
            "feedback_content": "Feedback",
            "inaccurate_reasons": ["other"],
            "action": "example.custom",
            "data": {"nested": {"items": [1, "你好", None]}},
        }
        data.update(
            {
                key: value
                for key, value in values.items()
                if key in event_class.model_fields
            }
        )
    return data


@pytest.mark.parametrize("event_class", EVENT_TYPES, ids=lambda cls: cls.__name__)
@pytest.mark.parametrize("populated", [False, True], ids=["minimal", "populated"])
@pytest.mark.parametrize("fallback", [False, True], ids=["typed", "fallback"])
async def test_every_event_runs_once_and_retains_public_payload(
    event_class, populated, fallback
):
    component = Runner()
    api = SimpleNamespace(call_tool=AsyncMock())
    component.get_run_api = Mock(return_value=api)
    data = payload(event_class, populated)
    received = []

    @component.handler(events.EBAEvent if fallback else event_class)
    async def handle(ctx):
        received.append(ctx.platform_event)
        await ctx.log(ctx.platform_event.type)

    ctx = run_context(run_id="matrix", config={}, event=SimpleNamespace(data=data))
    output = [item async for item in component.invoke(ctx)]
    assert len(received) == 1
    assert type(received[0]) is event_class
    restored = received[0].model_dump(mode="json")
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool, list)) and key not in {
            "message_chain",
            "new_content",
        }:
            assert restored[key] == value
    for field in ("message_chain", "new_content"):
        if field in data:
            assert getattr(received[0], field)[0].text == data[field][0]["text"]
    if "data" in data:
        assert restored["data"] == data["data"]
    assert [item.type for item in output] == ["processor.log", "run.completed"]
    assert all(item.run_id == "matrix" for item in output)
    api.call_tool.assert_not_called()


@pytest.mark.parametrize("event_class", EVENT_TYPES, ids=lambda cls: cls.__name__)
async def test_every_event_failure_preserves_logs_and_stops_later_handlers(event_class):
    component = Runner()
    component.get_run_api = Mock(return_value=SimpleNamespace(call_tool=AsyncMock()))
    later = AsyncMock()

    @component.handler(event_class)
    async def handle(ctx):
        await ctx.log("before failure", "error")
        raise RuntimeError("expected failure")

    component.handler(event_class)(later)
    ctx = run_context(
        run_id="failure",
        config={},
        event=SimpleNamespace(data=payload(event_class, True)),
    )
    output = []
    with pytest.raises(RuntimeError, match="expected failure"):
        async for item in component.invoke(ctx):
            output.append(item)
    assert [item.type for item in output] == ["processor.log"]
    later.assert_not_called()


async def test_specific_handlers_run_in_order_instead_of_fallback():
    component = Runner()
    component.get_run_api = Mock(return_value=SimpleNamespace())
    called = []

    @component.handler(events.EBAEvent)
    async def fallback(ctx):
        called.append("fallback")

    @component.handler(events.MemberJoinedEvent)
    async def first(ctx):
        called.append("first")

    @component.handler(events.MemberJoinedEvent)
    async def second(ctx):
        called.append("second")

    ctx = run_context(
        run_id="order",
        config={},
        event=SimpleNamespace(data={"type": "group.member_joined"}),
    )
    output = [item async for item in component.invoke(ctx)]
    assert called == ["first", "second"]
    assert [item.type for item in output] == ["run.completed"]


async def test_many_logs_drain_without_deadlock_or_loss():
    component = Runner()
    component.get_run_api = Mock(return_value=SimpleNamespace())

    @component.handler(events.EBAEvent)
    async def handle(ctx):
        for index in range(600):
            await ctx.log(str(index))

    ctx = run_context(
        run_id="logs", config={}, event=SimpleNamespace(data={"type": "friend.added"})
    )

    async def collect_results():
        return [item async for item in component.invoke(ctx)]

    output = await asyncio.wait_for(collect_results(), timeout=3)
    assert [item.data["text"] for item in output[:-1]] == list(map(str, range(600)))
    assert output[-1].type == "run.completed"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"type": None},
        {"type": "unknown.event"},
        {"type": "feedback.received"},
        {"type": "group.member_joined", "member": []},
    ],
)
async def test_invalid_event_fails_before_any_handler_or_api(data):
    component = Runner()
    component.get_run_api = Mock()
    handler = AsyncMock()
    component.handler(events.EBAEvent)(handler)
    ctx = run_context(run_id="invalid", config={}, event=SimpleNamespace(data=data))
    with pytest.raises((ValueError, ValidationError)):
        await anext(component.invoke(ctx))
    component.get_run_api.return_value.call_tool.assert_not_called()
    handler.assert_not_called()
