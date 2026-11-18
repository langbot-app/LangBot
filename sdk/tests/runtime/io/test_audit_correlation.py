import asyncio
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.api.proxies.invocation import (
    AUDIT_CORRELATION_FIELD,
    audit_correlation_scope,
    current_audit_correlation,
    relay_audit_correlation,
)
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.entities.io.req import ActionRequest
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.handler import Handler
from tests.helpers.protocol import ProtocolConnection


@pytest.mark.asyncio
async def test_internal_metadata_relays_across_runtime_and_worker_without_changing_binding():
    binding = InstallationBinding(
        instance_uuid="instance",
        workspace_uuid="workspace",
        placement_generation=1,
        installation_uuid="target",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    runtime = Handler(ProtocolConnection())
    worker = Handler(ProtocolConnection())
    host_connection = Handler(ProtocolConnection())
    received = []

    async def host_request(request, *args, **kwargs):
        received.append(request)
        return {"version": "test"}

    host_connection._call_action_request = host_request

    async def nested(data):
        assert data == {"tool_name": "target-tool"}
        assert current_audit_correlation() == "core-issued-id"
        await host_connection.call_action(
            PluginToRuntimeAction.GET_LANGBOT_VERSION, {}, action_context=binding
        )
        return ActionResponse.success({})

    worker.actions["call_tool"] = nested

    async def dispatch_worker(request, *args, **kwargs):
        await worker._handle_action(request.model_dump(mode="json"))
        return {}

    runtime._call_action_request = dispatch_worker

    async def forward(data):
        assert AUDIT_CORRELATION_FIELD not in data
        await runtime.call_action(PluginToRuntimeAction.CALL_TOOL, data)
        return ActionResponse.success({})

    runtime.actions["call_tool"] = forward
    request = ActionRequest.make_request(
        1,
        "call_tool",
        {
            "tool_name": "target-tool",
            AUDIT_CORRELATION_FIELD: "core-issued-id",
        },
        binding,
    )
    await runtime._handle_action(request.model_dump(mode="json"))
    assert len(received) == 1
    assert received[0].data == {AUDIT_CORRELATION_FIELD: "core-issued-id"}
    assert received[0].context == binding
    assert request.context == binding
    assert current_audit_correlation() is None


@pytest.mark.asyncio
async def test_unary_and_stream_requests_relay_metadata_and_keep_payload_unchanged():
    handler = Handler(ProtocolConnection())
    captured = []

    async def capture(request, *args, **kwargs):
        captured.append(request)
        return {}

    handler._call_action_request = capture
    original = {"key": "value"}
    with audit_correlation_scope("issued"):
        await handler.call_action(PluginToRuntimeAction.GET_LANGBOT_VERSION, original)
        stream = handler.call_action_generator(
            PluginToRuntimeAction.INVOKE_LLM_STREAM, original
        )
        handler._send_message = AsyncMock(
            side_effect=RuntimeError("stop after capture")
        )
        with pytest.raises(RuntimeError, match="stop after capture"):
            await anext(stream)
        stream_request = handler._send_message.await_args.args[0]
        assert stream_request.data[AUDIT_CORRELATION_FIELD] == "issued"
    assert captured[0].data[AUDIT_CORRELATION_FIELD] == "issued"
    assert original == {"key": "value"}


@pytest.mark.asyncio
async def test_escaped_task_cannot_relay_revoked_metadata():
    release = asyncio.Event()

    async def escaped():
        await release.wait()
        return relay_audit_correlation({})

    with audit_correlation_scope("issued"):
        task = asyncio.create_task(escaped())
    release.set()
    with pytest.raises(RuntimeError, match="invocation has ended"):
        await task


def test_new_core_id_replaces_parent_without_mutating_data():
    explicit = {AUDIT_CORRELATION_FIELD: "child"}
    with audit_correlation_scope("parent"):
        assert relay_audit_correlation(explicit) == explicit
    assert relay_audit_correlation({}) == {}


@pytest.mark.asyncio
async def test_uncorrelated_background_work_keeps_legacy_behavior():
    release = asyncio.Event()

    async def detached():
        await release.wait()
        return relay_audit_correlation({})

    with audit_correlation_scope(None):
        task = asyncio.create_task(detached())
    release.set()
    assert await task == {}
