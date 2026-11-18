from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import pytest

from langbot_plugin.entities.io.actions.enums import (
    CommonAction,
    PluginToRuntimeAction,
    RuntimeToPluginAction,
)
from langbot_plugin.entities.io.context import InstallationBinding


def _binding(name: str, workspace: str) -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=workspace,
        placement_generation=1,
        installation_uuid=name,
        runtime_revision=1,
        artifact_digest="a" * 64,
    )


async def _send(process, seq_id, action, data, binding=None, callbacks=None):
    assert process.stdin is not None
    assert process.stdout is not None
    request = {"seq_id": seq_id, "action": action, "data": data}
    if binding is not None:
        request["context"] = binding.model_dump()
    process.stdin.write((json.dumps(request) + "\n").encode())
    await process.stdin.drain()
    while True:
        message = json.loads(
            await asyncio.wait_for(process.stdout.readline(), timeout=3)
        )
        if "action" not in message:
            return message
        if callbacks is not None:
            callbacks.append(message)
        process.stdin.write(
            (
                json.dumps(
                    {
                        "seq_id": message["seq_id"],
                        "code": 0,
                        "message": "ok",
                        "data": {"bots": ["bot"]},
                    }
                )
                + "\n"
            ).encode()
        )
        await process.stdin.drain()


async def _read_json_line(process):
    assert process.stdout is not None
    while True:
        line = await asyncio.wait_for(process.stdout.readline(), timeout=10)
        if not line:
            stderr = await process.stderr.read() if process.stderr is not None else b""
            raise AssertionError(
                f"worker exited before protocol message: {stderr.decode()}"
            )
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="shared worker slots require the Linux nsjail pool",
)
async def test_real_subprocess_shared_slots_are_isolated_and_dedicated_is_separate(
    tmp_path,
):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    (plugin / "manifest.yaml").write_text(
        """apiVersion: v1
kind: Plugin
metadata:
  author: tester
  name: sharedprobe
  version: 1.0.0
  label: {en_US: Shared Probe}
spec:
  components:
    Tool:
      fromFiles: [components/probe.yaml]
execution:
  python: {path: main.py, attr: SharedProbe}
  sharedRuntime: shared-runtime-v1
  componentModel: stateless-v1
""",
        encoding="utf-8",
    )
    (plugin / "main.py").write_text(
        """import os
from langbot_plugin.api.definition.plugin import BasePlugin
class SharedProbe(BasePlugin):
    async def initialize(self):
        marker = os.environ.get("SHARED_PROBE_MARKER")
        if marker:
            with open(marker, "a", encoding="utf-8") as handle:
                handle.write(f"init:{os.getpid()}:{id(self)}\\n")

    async def observe(self):
        await self.get_bots()
        marker = os.environ.get("SHARED_PROBE_MARKER")
        if marker:
            with open(marker, "a", encoding="utf-8") as handle:
                handle.write(f"call:{os.getpid()}:{self.config['tenant']}:{id(self)}\\n")
""",
        encoding="utf-8",
    )
    (plugin / "components").mkdir()
    (plugin / "components" / "probe.yaml").write_text(
        """apiVersion: v1
kind: Tool
metadata:
  name: probe
  label: {en_US: Probe}
spec: {}
execution:
  python: {path: probe.py, attr: ProbeTool}
""",
        encoding="utf-8",
    )
    (plugin / "components" / "probe.py").write_text(
        """import os
from langbot_plugin.api.definition.components.tool.tool import Tool
class ProbeTool(Tool):
    async def initialize(self):
        marker = os.environ.get("SHARED_PROBE_MARKER")
        if marker:
            with open(marker, "a", encoding="utf-8") as handle:
                handle.write(f"component-init:{os.getpid()}:{id(self)}\\n")
    async def call(self, params, session, query_id):
        marker = os.environ.get("SHARED_PROBE_MARKER")
        if marker:
            with open(marker, "a", encoding="utf-8") as handle:
                handle.write(f"call:{os.getpid()}:{self.get_plugin_config()['tenant']}:{id(self)}\\n")
        await self.plugin.get_bots()
        return self.get_plugin_config()["tenant"]
""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    transfer_root = tmp_path / "rpc-transfer"
    env.update(
        {
            "PYTHONPATH": str(Path(__file__).parents[3] / "src"),
            "LANGBOT_PLUGIN_REGISTRATION_CAPABILITY": "x" * 40,
            "LANGBOT_PLUGIN_RUNTIME_PROFILE": "shared",
            "LANGBOT_PLUGIN_FILE_STORAGE_DIR": str(transfer_root),
            "PYTHONUNBUFFERED": "1",
            "SHARED_PROBE_MARKER": str(tmp_path / "markers.log"),
        }
    )

    async def launch():
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "langbot_plugin.cli.__init__",
            "run",
            "-s",
            "--prod",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=plugin,
            env=env,
        )

    shared = await launch()
    replacement = None
    dedicated = None
    try:
        assert shared.pid is not None
        registered = await _read_json_line(shared)
        assert registered["action"] == PluginToRuntimeAction.REGISTER_PLUGIN.value
        shared.stdin.write(
            (
                json.dumps(
                    {
                        "seq_id": registered["seq_id"],
                        "code": 0,
                        "message": "ok",
                        "data": {},
                    }
                )
                + "\n"
            ).encode()
        )
        await shared.stdin.drain()

        binding_a = _binding("installation-a", "workspace-a")
        binding_b = _binding("installation-b", "workspace-b")
        callbacks = []
        attached_a = await _send(
            shared,
            101,
            RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
            {
                "plugin_settings": {
                    "enabled": True,
                    "priority": 1,
                    "plugin_config": {"tenant": "a"},
                }
            },
            binding_a,
            callbacks,
        )
        attached_b = await _send(
            shared,
            102,
            RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
            {
                "plugin_settings": {
                    "enabled": True,
                    "priority": 2,
                    "plugin_config": {"tenant": "b"},
                }
            },
            binding_b,
            callbacks,
        )
        assert attached_a["code"] == attached_b["code"] == 0, (
            attached_a,
            attached_b,
        )
        slot_a = await _send(
            shared,
            103,
            RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER.value,
            {},
            binding_a,
        )
        slot_b = await _send(
            shared,
            104,
            RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER.value,
            {},
            binding_b,
        )
        assert slot_a["data"]["plugin_config"] == {"tenant": "a"}
        assert slot_b["data"]["plugin_config"] == {"tenant": "b"}
        assert callbacks == []
        call_payload = {
            "tool_name": "probe",
            "tool_parameters": {},
            "session": {
                "launcher_type": "person",
                "launcher_id": "launcher",
                "sender_id": "sender",
            },
            "query_id": 1,
        }
        called_a = await _send(
            shared,
            107,
            RuntimeToPluginAction.CALL_TOOL.value,
            call_payload,
            binding_a,
            callbacks,
        )
        called_b = await _send(
            shared,
            108,
            RuntimeToPluginAction.CALL_TOOL.value,
            call_payload,
            binding_b,
            callbacks,
        )
        assert called_a["data"]["tool_response"] == "a"
        assert called_b["data"]["tool_response"] == "b"
        assert [callback["context"] for callback in callbacks] == [
            binding_a.model_dump(),
            binding_b.model_dump(),
        ]
        marker_lines = (tmp_path / "markers.log").read_text().splitlines()
        plugin_init = [line for line in marker_lines if line.startswith("init:")]
        component_init = [
            line for line in marker_lines if line.startswith("component-init:")
        ]
        calls = [line for line in marker_lines if line.startswith("call:")]
        assert len(plugin_init) == len(component_init) == 1
        assert {line.split(":", 3)[1] for line in marker_lines} == {str(shared.pid)}
        assert {line.split(":", 3)[2] for line in calls} == {"a", "b"}
        assert len({line.split(":", 3)[3] for line in calls}) == 1

        chunk = {
            "file_key": "private.bin",
            "chunk_base64": base64.b64encode(b"secret-a").decode(),
            "chunk_index": 0,
            "chunk_amount": 1,
        }
        assert (
            await _send(shared, 105, CommonAction.FILE_CHUNK.value, chunk, binding_a)
        )["code"] == 0
        denied = await _send(
            shared,
            106,
            RuntimeToPluginAction.PARSE_DOCUMENT.value,
            {"context": {"file_key": "private.bin"}},
            binding_b,
        )
        assert denied["code"] == 1
        assert "FileNotFoundError" in denied["message"]

        first_pid = shared.pid
        shared.terminate()
        await shared.wait()
        replacement = await launch()
        registered = await _read_json_line(replacement)
        replacement.stdin.write(
            (
                json.dumps(
                    {
                        "seq_id": registered["seq_id"],
                        "code": 0,
                        "message": "ok",
                        "data": {},
                    }
                )
                + "\n"
            ).encode()
        )
        await replacement.stdin.drain()
        assert replacement.pid != first_pid
        replacement_callbacks = []
        assert (
            await _send(
                replacement,
                201,
                RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
                {
                    "plugin_settings": {
                        "enabled": True,
                        "priority": 1,
                        "plugin_config": {"tenant": "a"},
                    }
                },
                binding_a,
                replacement_callbacks,
            )
        )["code"] == 0
        assert (
            await _send(
                replacement,
                202,
                RuntimeToPluginAction.ATTACH_PLUGIN_SLOT.value,
                {
                    "plugin_settings": {
                        "enabled": True,
                        "priority": 2,
                        "plugin_config": {"tenant": "b"},
                    }
                },
                binding_b,
                replacement_callbacks,
            )
        )["code"] == 0
        assert replacement_callbacks == []

        assert (
            await _send(
                replacement,
                203,
                RuntimeToPluginAction.DETACH_PLUGIN_SLOT.value,
                {},
                binding_a,
            )
        )["code"] == 0
        assert (
            await _send(
                replacement,
                204,
                RuntimeToPluginAction.GET_PLUGIN_SLOT_CONTAINER.value,
                {},
                binding_b,
            )
        )["code"] == 0
        assert replacement.returncode is None

        dedicated = await launch()
        assert dedicated.pid != replacement.pid
    finally:
        for process in (dedicated, replacement, shared):
            if process is not None and process.returncode is None:
                process.terminate()
                await process.wait()
