"""Real stdio worker smoke for exact DifyAgent; no vendor credentials used."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.entities.builtin.runner.trigger import AgentTrigger
from langbot_plugin.api.entities.builtin.runner.event import AgentEventContext
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.resources import AgentResources
from langbot_plugin.api.entities.builtin.runner.runtime import AgentRuntimeContext
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    _LEGACY_DEDICATED_SDK_061,
)


@pytest.mark.asyncio
async def test_exact_archive_real_worker_run_runner(tmp_path):
    archive = Path("/tmp/dify-legacy-exact.lbpkg")
    if not archive.is_file():
        pytest.skip("Exact archive unavailable")
    digest = _LEGACY_DEDICATED_SDK_061[("langbot-team", "DifyAgent", "0.1.10")]
    code = (
        PluginArtifactStore(tmp_path)
        .install_package(archive.read_bytes(), digest)
        .code_path
    )
    binding = InstallationBinding(
        instance_uuid="probe",
        workspace_uuid="workspace",
        placement_generation=1,
        installation_uuid="dify",
        runtime_revision=1,
        artifact_digest=digest,
    )
    env = dict(
        os.environ,
        LANGBOT_PLUGIN_REGISTRATION_CAPABILITY="x" * 40,
        LANGBOT_PLUGIN_RUNTIME_PROFILE="shared",
        LANGBOT_PLUGIN_FILE_STORAGE_DIR=str(tmp_path / "transfer"),
        PYTHONUNBUFFERED="1",
    )
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "langbot_plugin.cli.__init__",
        "run",
        "-s",
        "--prod",
        cwd=code,
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def read():
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), 25)
            if not line:
                raise AssertionError(
                    "Worker exited: " + (await proc.stderr.read()).decode()[-3000:]
                )
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    async def send(msg):
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    async def response():
        while True:
            result = await read()
            if "action" not in result:
                return result
            await send(
                dict(seq_id=result["seq_id"], code=0, message="ok", data={"bots": []})
            )

    try:
        register = await read()
        assert register["action"] == "register_plugin"
        await send(dict(seq_id=register["seq_id"], code=0, message="ok", data={}))
        await send(
            dict(
                seq_id=100,
                action="initialize_plugin",
                data={
                    "plugin_settings": {
                        "enabled": True,
                        "priority": 1,
                        "plugin_config": {},
                    }
                },
                context=binding.model_dump(),
            )
        )
        initialized = await response()
        assert initialized["code"] == 0, initialized
        context = RunnerContext(
            run_id="exact_dify_probe",
            trigger=AgentTrigger(type="message.received"),
            event=AgentEventContext(
                event_id="probe", event_type="message.received", source="probe"
            ),
            input=AgentInput(text="Hello"),
            delivery=DeliveryContext(surface="test"),
            resources=AgentResources(),
            runtime=AgentRuntimeContext(),
        )
        await send(
            dict(
                seq_id=101,
                action="run_runner",
                data={
                    "runner_name": "default",
                    "context": context.model_dump(mode="json"),
                },
                context=binding.model_dump(),
            )
        )
        result = await response()
        assert result["code"] == 0, result
        assert result["data"]["type"] == "run.failed", result
        assert result["data"]["data"]["code"] == "dify.config_invalid", result
        print(
            "REAL_RUNNER_RESULT", result["data"]["type"], result["data"]["data"]["code"]
        )
    finally:
        if proc.returncode is None:
            proc.terminate()
            await proc.wait()
