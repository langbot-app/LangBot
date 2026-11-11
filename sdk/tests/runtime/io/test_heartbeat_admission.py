"""Exercise heartbeat admission through the real JSON receive/dispatch loop."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from langbot_plugin.entities.io.actions.enums import (
    ActionType,
    CommonAction,
    LangBotToRuntimeAction,
)
from langbot_plugin.entities.io.context import (
    ActionContext,
    InstallationBinding,
    PluginWorkerPolicy,
    RuntimeConfig,
    RuntimeIdentity,
)
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.io.handler import Handler, MAX_INFLIGHT_ACTIONS
from langbot_plugin.runtime.io.handlers.control import ControlConnectionHandler
from langbot_plugin.runtime.plugin.mgr import PluginManager
from tests.helpers.protocol import ProtocolConnection, ProtocolSession


class GatedAction(ActionType):
    WORK = "test_work"


class ActionGate:
    """Hold real action tasks without blocking the receive loop or using sleeps."""

    def __init__(self, handler, action):
        self.started = asyncio.Queue()
        self.release = asyncio.Event()
        handler.actions[action.value] = self

    async def __call__(self, data):
        await self.started.put(asyncio.current_task())
        await self.release.wait()
        if data.get("fail"):
            raise ValueError("gated action failed")
        return ActionResponse.success({"message": "pong"})

    async def wait_started(self, count=1):
        return [
            await asyncio.wait_for(self.started.get(), timeout=1) for _ in range(count)
        ]


@pytest.fixture
def peer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    connection = ProtocolConnection()
    context = RuntimeContext()
    context.plugin_mgr = PluginManager(context)
    handler = ControlConnectionHandler(connection, context)
    context.activate_control_handler(handler)
    handler.configure_runtime(
        RuntimeConfig(
            runtime_identity=RuntimeIdentity(
                instance_uuid="instance-1", runtime_id="runtime-1"
            ),
            worker_policy=PluginWorkerPolicy(
                max_cpus=1.0,
                max_memory_mb=512,
                max_pids=128,
                max_open_files=256,
                max_file_size_mb=512,
            ),
        )
    )
    return handler, connection


async def saturate_business(handler, connection):
    gate = ActionGate(handler, GatedAction.WORK)
    for seq_id in range(MAX_INFLIGHT_ACTIONS):
        await connection.send_peer_request(GatedAction.WORK.value, seq_id=seq_id)
    tasks = await gate.wait_started(MAX_INFLIGHT_ACTIONS)
    return gate, tasks


async def test_ping_succeeds_with_all_business_slots_occupied(peer):
    handler, connection = peer
    async with ProtocolSession(handler) as session:
        gate, tasks = await saturate_business(handler, connection)
        response = await session.request(CommonAction.PING.value, seq_id=1000)
        assert response["seq_id"] == 1000
        assert response["code"] == 0, response
        assert response["data"] == {"message": "pong"}
        assert all(not task.done() for task in tasks)
        # The peer can observe PONG before its task's done callback runs.
        await asyncio.gather(*tuple(handler._reserved_action_tasks))
        await asyncio.sleep(0)
        assert len(handler._action_tasks) == MAX_INFLIGHT_ACTIONS

        gate.release.set()
        responses = await connection.sent_messages(MAX_INFLIGHT_ACTIONS + 1)
        assert {item["seq_id"] for item in responses} == {
            *range(MAX_INFLIGHT_ACTIONS),
            1000,
        }
        assert all(item["code"] == 0 for item in responses)


async def test_business_overflow_is_still_rejected(peer):
    handler, connection = peer
    async with ProtocolSession(handler) as session:
        await saturate_business(handler, connection)
        response = await session.request(GatedAction.WORK.value, seq_id=1000)
        assert response["seq_id"] == 1000
        assert response["code"] == 1
        assert f"max {MAX_INFLIGHT_ACTIONS} concurrent actions" in response["message"]


async def test_ping_flood_has_a_separate_four_task_budget(peer):
    handler, connection = peer
    ping_gate = ActionGate(handler, CommonAction.PING)
    async with ProtocolSession(handler) as session:
        for seq_id in range(4):
            await connection.send_peer_request(
                CommonAction.PING.value, seq_id=1000 + seq_id
            )
        ping_tasks = await ping_gate.wait_started(4)
        for seq_id in range(1004, 1024):
            overflow = await session.request(CommonAction.PING.value, seq_id=seq_id)
            assert overflow["seq_id"] == seq_id
            assert overflow["code"] == 1
            assert "max 4 concurrent" in overflow["message"]
        assert len(handler._action_tasks) == 4
        assert ping_gate.started.empty()

        # Even a full heartbeat lane must not take any business capacity.
        _, business_tasks = await saturate_business(handler, connection)
        assert all(not task.done() for task in [*ping_tasks, *business_tasks])
        assert len(handler._action_tasks) == MAX_INFLIGHT_ACTIONS + 4
        rejected = await session.request(GatedAction.WORK.value, seq_id=1005)
        assert rejected["code"] == 1
        assert f"max {MAX_INFLIGHT_ACTIONS} concurrent actions" in rejected["message"]


async def test_full_lanes_do_not_block_unary_or_stream_response_routing(peer):
    handler, connection = peer
    ping_gate = ActionGate(handler, CommonAction.PING)
    async with ProtocolSession(handler):
        await saturate_business(handler, connection)
        for seq_id in range(4):
            await connection.send_peer_request(
                CommonAction.PING.value, seq_id=1000 + seq_id
            )
        await ping_gate.wait_started(4)

        async def consume_stream():
            return [
                chunk
                async for chunk in handler.call_action_generator(
                    GatedAction.WORK, {}, timeout=1
                )
            ]

        unary = asyncio.create_task(
            handler.call_action(GatedAction.WORK, {}, timeout=1)
        )
        stream = asyncio.create_task(consume_stream())
        try:
            requests = await connection.sent_messages(2)
            await connection.send_peer_response(
                requests[0]["seq_id"], data={"unary": True}
            )
            await connection.send_peer_response(
                requests[1]["seq_id"], data={"chunk": 1}
            )
            await connection.send_peer_response(
                requests[1]["seq_id"], chunk_status="end"
            )
            assert await unary == {"unary": True}
            assert await stream == [{"chunk": 1}]
            assert not handler.resp_waiters
            assert not handler.resp_queues
        finally:
            unary.cancel()
            stream.cancel()
            await asyncio.gather(unary, stream, return_exceptions=True)


@pytest.mark.parametrize("outcome", ["success", "exception", "cancel"])
async def test_ping_admission_is_released_after_task_completion(peer, outcome):
    handler, connection = peer
    ping_gate = ActionGate(handler, CommonAction.PING)
    async with ProtocolSession(handler) as session:
        await saturate_business(handler, connection)
        for seq_id in range(4):
            await connection.send_peer_request(
                CommonAction.PING.value,
                {"fail": outcome == "exception"},
                seq_id=1000 + seq_id,
            )
        tasks = await ping_gate.wait_started(4)
        if outcome == "cancel":
            for task in tasks:
                task.cancel()
        else:
            ping_gate.release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        if outcome != "cancel":
            responses = await connection.sent_messages(4)
            assert all(item["code"] == (outcome == "exception") for item in responses)

        ping_gate.release.set()
        response = await session.request(CommonAction.PING.value, seq_id=1004)
        assert response["code"] == 0, response


@pytest.mark.parametrize("shutdown", ["close", "disconnect", "cancel_run", "fence"])
async def test_shutdown_cancels_both_lanes(peer, shutdown):
    handler, connection = peer
    ping_gate = ActionGate(handler, CommonAction.PING)
    business_gate = ActionGate(handler, GatedAction.WORK)
    run_task = asyncio.create_task(handler.run())
    try:
        await connection.send_peer_request(CommonAction.PING.value, seq_id=1000)
        await connection.send_peer_request(GatedAction.WORK.value, seq_id=1)
        tasks = [*await ping_gate.wait_started(), *await business_gate.wait_started()]
        if shutdown == "close":
            await handler.close()
        elif shutdown == "disconnect":
            await connection.close_peer()
            await run_task
        elif shutdown == "cancel_run":
            run_task.cancel()
            await asyncio.gather(run_task, return_exceptions=True)
        else:
            handler.cancel_inflight_messages()
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=1
        )
        assert all(task.cancelled() for task in tasks)
        assert not handler._action_tasks
    finally:
        run_task.cancel()
        await asyncio.gather(run_task, return_exceptions=True)
        await handler.close()


async def test_reconnect_cancels_old_actions_before_reusing_admission(peer):
    handler, connection = peer
    ping_gate = ActionGate(handler, CommonAction.PING)
    business_gate = ActionGate(handler, GatedAction.WORK)
    replacement = ProtocolConnection()
    reconnected = asyncio.Event()
    old_tasks_cancelled = []
    tasks = []

    async def reconnect(current_handler):
        old_tasks_cancelled.append(all(task.cancelled() for task in tasks))
        current_handler.conn = replacement
        reconnected.set()
        return True

    handler.set_disconnect_callback(reconnect)
    run_task = asyncio.create_task(handler.run())
    try:
        await connection.send_peer_request(CommonAction.PING.value, seq_id=1000)
        await connection.send_peer_request(GatedAction.WORK.value, seq_id=1)
        tasks = [*await ping_gate.wait_started(), *await business_gate.wait_started()]
        await connection.close_peer()
        await asyncio.wait_for(reconnected.wait(), timeout=1)
        assert old_tasks_cancelled == [True]
        assert not handler._action_tasks
        ping_gate.release.set()
        await replacement.send_peer_request(CommonAction.PING.value, seq_id=1001)
        [response] = await replacement.sent_messages(1)
        assert response["code"] == 0
        assert response["seq_id"] == 1001
        assert not connection.sent
    finally:
        run_task.cancel()
        await asyncio.gather(run_task, return_exceptions=True)


@pytest.mark.parametrize(
    ("invalid_fields", "expected_error"),
    [
        ({"data": []}, "ValidationError"),
        ({"context": {"workspace_uuid": "missing-binding-fields"}}, "ValidationError"),
        (
            {
                "context": ActionContext(
                    instance_uuid="instance-1",
                    workspace_uuid="workspace-a",
                    placement_generation=1,
                ).model_dump()
            },
            "PING does not accept tenant context",
        ),
    ],
)
async def test_reserved_ping_still_validates_request_and_tenant_context(
    peer, invalid_fields, expected_error
):
    handler, connection = peer
    async with ProtocolSession(handler) as session:
        await saturate_business(handler, connection)
        await connection.incoming.put(
            json.dumps(
                {
                    "seq_id": 1000,
                    "action": CommonAction.PING.value,
                    "data": {},
                    **invalid_fields,
                }
            )
        )
        [response] = await connection.sent_messages(1)
        assert response["seq_id"] == 1000
        assert response["code"] == 1
        assert expected_error in response["message"]
        valid = await session.request(CommonAction.PING.value, seq_id=1001)
        assert valid["code"] == 0


async def test_control_ping_retains_context_and_active_handler_authorization(peer):
    handler, connection = peer
    context = handler.context
    async with ProtocolSession(handler) as session:
        await saturate_business(handler, connection)
        rejected = await session.request(
            CommonAction.PING.value,
            action_context=ActionContext(
                instance_uuid="instance-1",
                workspace_uuid="workspace-a",
                placement_generation=1,
            ),
        )
        assert rejected["code"] == 1
        assert "PING does not accept tenant context" in rejected["message"]
        accepted = await session.request(CommonAction.PING.value, seq_id=2)
        assert accepted["code"] == 0
        assert accepted["data"] == {"message": "pong"}

        gate = ActionGate(handler, CommonAction.PING)
        await connection.send_peer_request(CommonAction.PING.value, seq_id=3)
        [task] = await gate.wait_started()
        context.activate_control_handler(
            ControlConnectionHandler(ProtocolConnection(), context)
        )
        # Identity fencing applies before explicit invalidation/cancellation.
        rejected = await session.request(CommonAction.PING.value, seq_id=5)
        assert rejected["code"] == 1
        assert "superseded" in rejected["message"]
        assert not task.done()
        handler.invalidate()
        await asyncio.gather(task, return_exceptions=True)
        assert task.cancelled()
        rejected = await session.request(CommonAction.PING.value, seq_id=4)
        assert rejected["code"] == 1
        assert "superseded" in rejected["message"]


async def test_non_control_handler_does_not_reserve_ping_capacity(tmp_path):
    connection = ProtocolConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    ActionGate(handler, CommonAction.PING)
    async with ProtocolSession(handler) as session:
        await saturate_business(handler, connection)
        response = await session.request(CommonAction.PING.value, seq_id=1000)
        assert response["code"] == 1
        assert "max 128 concurrent actions" in response["message"]
        assert len(handler._action_tasks) == 128


async def test_control_emit_event_saturation_and_recovery(peer, monkeypatch):
    """Real control dispatch and authorization; only worker execution is gated."""
    handler, connection = peer
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-1",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    handler.context.activate_installation_binding(binding)
    started = asyncio.Queue()
    release = asyncio.Event()
    healthy_calls = []

    async def emit_event(event_context, include_plugins):
        assert handler.current_action_context == binding
        assert event_context.workspace_uuid == binding.workspace_uuid
        if include_plugins == ["tester/blocked"]:
            await started.put(asyncio.current_task())
            await release.wait()
        else:
            assert include_plugins == ["tester/healthy"]
            healthy_calls.append(event_context.query_id)
        plugin = SimpleNamespace(model_dump=lambda: {"name": include_plugins[0]})
        return [plugin], event_context, []

    monkeypatch.setattr(handler.context.plugin_mgr, "emit_event", emit_event)

    def event_data(plugin):
        return {
            "include_plugins": [plugin],
            "event_context": {
                "query_id": 12,
                "event_name": "PersonCommandSent",
                "event": {
                    "event_name": "PersonCommandSent",
                    "launcher_type": "person",
                    "launcher_id": "launcher",
                    "sender_id": "sender",
                    "command": "demo",
                    "params": [],
                    "text_message": "/demo",
                    "is_admin": False,
                },
            },
        }

    async with ProtocolSession(handler) as session:
        assert MAX_INFLIGHT_ACTIONS == 128
        for seq_id in range(128):
            await connection.send_peer_request(
                LangBotToRuntimeAction.EMIT_EVENT.value,
                event_data("tester/blocked"),
                seq_id=seq_id,
                action_context=binding,
            )
        tasks = [await asyncio.wait_for(started.get(), 1) for _ in range(128)]
        pong = await session.request(CommonAction.PING.value, seq_id=1000)
        assert pong["seq_id"] == 1000
        assert pong["code"] == 0, pong
        assert pong["data"] == {"message": "pong"}
        assert all(not task.done() for task in tasks)
        await asyncio.gather(*tuple(handler._reserved_action_tasks))
        await asyncio.sleep(0)
        assert len(handler._action_tasks) == 128

        overflow = await session.request(
            LangBotToRuntimeAction.EMIT_EVENT.value,
            event_data("tester/healthy"),
            seq_id=1001,
            action_context=binding,
        )
        assert overflow["seq_id"] == 1001
        assert overflow["code"] == 1
        assert "max 128 concurrent actions" in overflow["message"]
        assert not healthy_calls

        release.set()
        await asyncio.wait_for(asyncio.gather(*tasks), 1)
        responses = await connection.sent_messages(130)
        completed = [item for item in responses if item["seq_id"] < 128]
        assert {item["seq_id"] for item in completed} == set(range(128))
        assert all(item["code"] == 0 for item in completed)
        assert all(
            item["data"]["emitted_plugins"] == [{"name": "tester/blocked"}]
            for item in completed
        )
        recovered = await session.request(
            LangBotToRuntimeAction.EMIT_EVENT.value,
            event_data("tester/healthy"),
            seq_id=1002,
            action_context=binding,
        )
        assert recovered["code"] == 0
        assert recovered["data"]["emitted_plugins"] == [{"name": "tester/healthy"}]
        assert healthy_calls == [12]
        assert (await session.request(CommonAction.PING.value, seq_id=1003))[
            "code"
        ] == 0
        await asyncio.gather(*tuple(handler._reserved_action_tasks))
        await asyncio.sleep(0)
        assert not handler._action_tasks
        assert handler.conn is connection
        assert handler.context.is_active_control_handler(handler)
