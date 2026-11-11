"""Tests for reading current-event input attachments by ref."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.context_access import (
    ContextAccess,
    ContextAPICapabilities,
)
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.runner.input import (
    AgentInput,
    InputAttachment,
)
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.api.proxies.runner.common import PermissionDeniedError
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction

PAYLOAD = b"%PDF-1.7 test"


def _context(*, enabled: bool) -> RunnerContext:
    return RunnerContext(
        run_id="run-1",
        trigger=AgentTrigger(type="message.received"),
        event=AgentEventContext(
            event_id="event-1", event_type="message.received", source="test"
        ),
        input=AgentInput(
            text="see [attachment att-1: file report.pdf]",
            attachments=[
                InputAttachment(
                    ref="att-1", type="file", source="message", name="report.pdf"
                )
            ],
        ),
        delivery=DeliveryContext(surface="test"),
        context=ContextAccess(
            available_apis=ContextAPICapabilities(input_attachments=enabled)
        ),
        runtime=AgentRuntimeContext(deadline_at=None),
        resources=AgentResources(),
    )


def _handler():
    handler = MagicMock()
    handler.call_action = AsyncMock(
        return_value={
            "ref": "att-1",
            "name": "report.pdf",
            "mime_type": "application/pdf",
            "size": len(PAYLOAD),
            "content": base64.b64encode(PAYLOAD).decode(),
        }
    )
    return handler


@pytest.mark.anyio
async def test_proxy_reads_bytes_for_the_current_run():
    handler = _handler()
    proxy = RunnerAPIProxy(ctx=_context(enabled=True), plugin_runtime_handler=handler)

    data = await proxy.read_input_attachment("att-1")

    assert data.data == PAYLOAD
    assert data.size == len(PAYLOAD)
    assert (data.ref, data.name, data.mime_type) == (
        "att-1",
        "report.pdf",
        "application/pdf",
    )
    action, request, _ = handler.call_action.call_args[0]
    assert action == PluginToRuntimeAction.READ_INPUT_ATTACHMENT
    assert request == {"run_id": "run-1", "ref": "att-1"}


@pytest.mark.anyio
async def test_proxy_refuses_when_host_does_not_offer_the_api():
    handler = _handler()
    proxy = RunnerAPIProxy(ctx=_context(enabled=False), plugin_runtime_handler=handler)

    with pytest.raises(PermissionDeniedError):
        await proxy.read_input_attachment("att-1")
    handler.call_action.assert_not_called()


@pytest.mark.anyio
async def test_context_helper_returns_none_so_runners_can_fall_back():
    ctx = _context(enabled=False)
    ctx._api = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=_handler())

    assert await ctx.read_input_attachment(ctx.input.attachments[0]) is None
    assert await ctx.read_input_attachment(InputAttachment(type="image")) is None


@pytest.mark.anyio
async def test_context_helper_reads_attachment_or_ref():
    ctx = _context(enabled=True)
    ctx._api = RunnerAPIProxy(ctx=ctx, plugin_runtime_handler=_handler())

    assert (await ctx.read_input_attachment(ctx.input.attachments[0])).data == PAYLOAD
    assert (await ctx.read_input_attachment("att-1")).data == PAYLOAD


def test_older_host_context_without_the_flag_disables_the_api():
    access = ContextAccess.model_validate({"available_apis": {"box": True}})

    assert access.available_apis.input_attachments is False
