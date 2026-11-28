"""Control FILE_CHUNK admission against real legacy registration state."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import pytest

from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.io.handlers.control import ControlConnectionHandler
from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from langbot_plugin.runtime.plugin.mgr import PluginManager
from tests.helpers.protocol import ProtocolConnection, ProtocolSession
from tests.runtime.io.handlers.test_control_handler import (
    TEST_INSTALLATION_BINDING,
    TEST_RUNTIME_CONFIG,
    _handler,
)
from tests.runtime.plugin.test_manager import _plugin

LEGACY_CONTEXT = ActionContext(
    instance_uuid="instance-1",
    workspace_uuid="workspace-a",
    placement_generation=4,
    installation_uuid="legacy-installation",
)
FILE_KEY = "knowledge-file"
FILE_BYTES = b"legacy knowledge document\x00\xff"


def _chunk(data=FILE_BYTES, index=0, amount=1):
    return {
        "file_key": FILE_KEY,
        "chunk_base64": base64.b64encode(data).decode(),
        "chunk_index": index,
        "chunk_amount": amount,
    }


@pytest.fixture
async def legacy_runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    context = RuntimeContext()
    manager = PluginManager(context)
    context.plugin_mgr = manager
    control = ControlConnectionHandler(ProtocolConnection(), context)
    context.activate_control_handler(control)
    control.configure_runtime(TEST_RUNTIME_CONFIG)
    context.bind_workspace(LEGACY_CONTEXT.without_installation())
    worker = PluginConnectionHandler(ProtocolConnection(), context)
    manager.plugin_handlers.append(worker)
    plugin = _plugin()
    # Only external RPC peers are stubbed; registration and revocation are real.
    monkeypatch.setattr(
        control,
        "call_action",
        AsyncMock(
            return_value={
                "installation_uuid": LEGACY_CONTEXT.installation_uuid,
            }
        ),
    )
    monkeypatch.setattr(worker, "initialize_plugin", AsyncMock(return_value={}))
    monkeypatch.setattr(
        worker, "get_plugin_container", AsyncMock(return_value=plugin.model_dump())
    )
    capability = manager._issue_registration_capability(
        plugin_author="tester",
        plugin_name="demo",
        plugin_path=str(tmp_path / "tester__demo"),
    )
    await manager.register_plugin(
        worker, plugin.model_dump(), registration_capability=capability
    )
    assert not manager.is_registration_capability_pending(capability)
    assert worker.bound_action_context == LEGACY_CONTEXT
    yield control, manager, worker
    await worker.close()
    await control.close()


async def test_registered_legacy_file_chunk_receives_real_bytes(legacy_runtime):
    control, _manager, _worker = legacy_runtime
    async with ProtocolSession(control) as session:
        response = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(),
            action_context=LEGACY_CONTEXT,
        )
        assert response["code"] == 0, response
        assert (
            await control.read_local_file(FILE_KEY, action_context=LEGACY_CONTEXT)
            == FILE_BYTES
        )
        assert not control.context._installation_bindings
        assert control.bound_action_context is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("context", None),
        ("workspace_uuid", "workspace-b"),
        ("instance_uuid", "instance-2"),
        ("placement_generation", 5),
        ("installation_uuid", None),
        ("installation_uuid", "forged-installation"),
    ],
)
async def test_legacy_file_chunk_rejects_wrong_scope(legacy_runtime, field, value):
    control, _manager, _worker = legacy_runtime
    binding = (
        None if field == "context" else LEGACY_CONTEXT.model_copy(update={field: value})
    )
    async with ProtocolSession(control) as session:
        response = await session.request(
            CommonAction.FILE_CHUNK.value,
            {**_chunk(), **LEGACY_CONTEXT.model_dump()},
            action_context=binding,
        )
        assert response["code"] != 0
        assert FILE_KEY not in control._owned_transfer_files


@pytest.mark.parametrize(
    "state",
    [
        "removed",
        "disconnected",
        "closed",
        "no-container",
        "no-handler",
        "unbound-worker",
        "no-workspace",
        "no-handshake",
        "superseded",
        "shared",
    ],
)
async def test_legacy_file_chunk_requires_live_registration(legacy_runtime, state):
    control, manager, worker = legacy_runtime
    if state == "removed":
        await manager.remove_plugin_container(manager.plugins[0])
    elif state == "disconnected":
        await manager.remove_plugin_handler(worker)
    elif state == "closed":
        await worker.close()
    elif state == "no-container":
        manager.plugins.clear()
    elif state == "no-handler":
        manager.plugin_handlers.clear()
    elif state == "unbound-worker":
        worker._bound_action_context = None
    elif state == "no-workspace":
        control.context._legacy_workspace_binding = None
    elif state == "no-handshake":
        control._runtime_configured = False
    elif state == "superseded":
        control.context.activate_control_handler(
            ControlConnectionHandler(ProtocolConnection(), control.context)
        )
    elif state == "shared":
        control.context.runtime_profile = "shared"
    async with ProtocolSession(control) as session:
        response = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(),
            action_context=LEGACY_CONTEXT,
        )
        assert response["code"] != 0
        assert FILE_KEY not in control._owned_transfer_files


async def test_legacy_registration_revocation_rejects_later_chunk(legacy_runtime):
    control, manager, worker = legacy_runtime
    async with ProtocolSession(control) as session:
        first = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(b"first", 0, 2),
            action_context=LEGACY_CONTEXT,
        )
        assert first["code"] == 0, first
        await manager.remove_plugin_handler(worker)
        second = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(b"second", 1, 2),
            seq_id=2,
            action_context=LEGACY_CONTEXT,
        )
        assert second["code"] != 0
        with pytest.raises(FileNotFoundError):
            await control.read_local_file(FILE_KEY, action_context=LEGACY_CONTEXT)


@pytest.mark.parametrize("profile", ["oss_dev", "shared"])
@pytest.mark.parametrize("active", [False, True])
async def test_complete_file_chunk_preserves_candidate_staging(
    tmp_path, monkeypatch, profile, active
):
    monkeypatch.chdir(tmp_path)
    control, _manager = _handler(
        runtime_config=TEST_RUNTIME_CONFIG.model_copy(
            update={"runtime_profile": profile},
        )
    )
    binding = TEST_INSTALLATION_BINDING
    if active:
        control.context.activate_installation_binding(binding)
    async with ProtocolSession(control) as session:
        response = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(),
            action_context=binding,
        )
        assert response["code"] == 0, response
        assert (
            await control.read_local_file(FILE_KEY, action_context=binding)
            == FILE_BYTES
        )
        await control.delete_local_file(FILE_KEY, action_context=binding)
        assert control.context.is_current_installation_binding(binding) is active
        # Candidate upgrade bytes must not activate a new revision.
        candidate = binding.model_copy(
            update={"runtime_revision": 3, "artifact_digest": "b" * 64}
        )
        response = await session.request(
            CommonAction.FILE_CHUNK.value,
            _chunk(b"candidate package"),
            seq_id=2,
            action_context=candidate,
        )
        assert response["code"] == 0, response
        assert (
            await control.read_local_file(FILE_KEY, action_context=candidate)
            == b"candidate package"
        )
        assert not control.context.is_current_installation_binding(candidate)
        assert control.context.is_current_installation_binding(binding) is active


@pytest.mark.parametrize(
    "field",
    ["instance_uuid", "workspace_uuid", "placement_generation", "installation_uuid"],
)
async def test_legacy_file_chunk_rejects_missing_wire_scope(legacy_runtime, field):
    control, _manager, _worker = legacy_runtime
    binding = LEGACY_CONTEXT.model_dump()
    del binding[field]
    async with ProtocolSession(control):
        # Bypass the test peer's model validation to exercise raw envelope receive.
        await control.conn.incoming.put(
            json.dumps(
                {
                    "seq_id": 1,
                    "action": CommonAction.FILE_CHUNK.value,
                    "data": _chunk(),
                    "context": binding,
                }
            )
        )
        response = (await control.conn.sent_messages())[0]
        assert response["code"] != 0
        assert FILE_KEY not in control._owned_transfer_files
