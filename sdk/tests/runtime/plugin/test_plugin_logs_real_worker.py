"""Plugin logs captured from a real OSS dedicated worker subprocess."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import zipfile

import pytest

from langbot_plugin.entities.io.actions.enums import RuntimeToPluginAction
from langbot_plugin.entities.io.context import InstallationBinding, PluginWorkerPolicy
from langbot_plugin.runtime.context import RuntimeContext
from langbot_plugin.runtime.io.handlers.plugin import PluginConnectionHandler
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    PluginDependencyEnvironment,
)
from langbot_plugin.runtime.plugin.worker_launcher import (
    PluginWorkerLauncher,
    PluginWorkerLaunchSpec,
)

MANIFEST = """
apiVersion: v1
kind: Plugin
metadata:
  author: tester
  name: logdemo
  version: 1.0.0
  label:
    en_US: LogDemo
spec:
  components: {}
execution:
  python:
    path: main.py
    attr: LogDemo
"""

MAIN = """
import logging
from langbot_plugin.api.definition.plugin import BasePlugin

logger = logging.getLogger(__name__)

class LogDemo(BasePlugin):
    async def initialize(self):
        logger.info("hello from plugin logger")
        logger.error("plugin error line")
"""


def _launch_spec(tmp_path) -> PluginWorkerLaunchSpec:
    package_io = io.BytesIO()
    with zipfile.ZipFile(package_io, "w") as archive:
        archive.writestr("manifest.yaml", MANIFEST)
        archive.writestr("main.py", MAIN)
    package = package_io.getvalue()
    digest = hashlib.sha256(package).hexdigest()
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest=digest,
    )
    store = PluginArtifactStore(tmp_path / "plugin-runtime")
    artifact = store.install_package(package, digest)
    dependency_root = tmp_path / "plugin-runtime" / "environment"
    dependency_path = dependency_root / "site-packages"
    dependency_path.mkdir(parents=True)
    return PluginWorkerLaunchSpec(
        binding=binding,
        artifact=artifact,
        paths=store.ensure_installation_paths(binding),
        registration_capability="e2e-only-capability",
        runtime_ws_url="ws://localhost:5401/plugin/ws",
        dependency_environment=PluginDependencyEnvironment(
            digest="b" * 64,
            artifact_digest=digest,
            requirements_digest="c" * 64,
            runtime_fingerprint="d" * 64,
            root_path=dependency_root,
            site_packages_path=dependency_path,
        ),
    )


@pytest.mark.asyncio
async def test_oss_dedicated_worker_logs_reach_plugin_log_buffer(tmp_path):
    launcher = PluginWorkerLauncher(
        nsjail_path="", cgroup_v2_available=False, platform="linux"
    )
    launcher.configure(
        PluginWorkerPolicy(
            max_cpus=1,
            max_memory_mb=512,
            max_pids=64,
            max_open_files=256,
            max_file_size_mb=16,
            require_hard_limits=False,
        ),
        "oss_dev",
    )
    controller = launcher.create_controller(_launch_spec(tmp_path))
    context = RuntimeContext()
    captured: dict[str, list] = {}

    async def on_connection(connection):
        registration = json.loads(await asyncio.wait_for(connection.receive(), 30))
        assert registration["action"] == "register_plugin"
        await connection.send(
            json.dumps(
                {
                    "seq_id": registration["seq_id"],
                    "code": 0,
                    "message": "ok",
                    "data": {},
                }
            )
        )
        handler = PluginConnectionHandler(
            connection,
            context,
            stdio_process=controller.process,
            file_storage_dir=str(tmp_path / "host-transfer"),
        )
        task = asyncio.create_task(handler.run())
        try:
            await handler.call_action(
                RuntimeToPluginAction.INITIALIZE_PLUGIN,
                {
                    "plugin_settings": {
                        "enabled": True,
                        "priority": 1,
                        "plugin_config": {},
                    }
                },
            )
            for _ in range(100):
                logs = handler.log_buffer.get_logs()
                if any("plugin error line" in e["text"] for e in logs):
                    break
                await asyncio.sleep(0.05)
            captured["logs"] = handler.log_buffer.get_logs()
        finally:
            handler.log_buffer.stop_reader()
            task.cancel()

    await asyncio.wait_for(controller.run(on_connection), 60)

    logs = captured["logs"]
    info = [e for e in logs if "hello from plugin logger" in e["text"]]
    error = [e for e in logs if "plugin error line" in e["text"]]
    assert info and info[0]["level"] == "INFO"
    assert error and error[0]["level"] == "ERROR"
