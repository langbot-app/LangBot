"""Shared-runtime release contract; run with the actual candidate SDK."""

from pathlib import Path

import pytest
from langbot_plugin.runtime.plugin.artifact import PluginArtifact
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_real_sdk_dependency_admission(tmp_path):
    from inspect import signature

    from langbot_plugin.api.proxies.runner.box import RunnerBoxAPIMixin

    assert "paths" in signature(RunnerBoxAPIMixin.export_box_files).parameters
    artifact = PluginArtifact("1" * 64, ROOT, ROOT, "langbot-team", "LocalAgent", "0.2.0")
    store = PluginDependencyEnvironmentStore(tmp_path)
    from langbot_plugin.entities.io.context import PluginWorkerPolicy
    from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher

    launcher = PluginWorkerLauncher()
    # Real SDK installer into a disposable target, not shared nsjail enforcement.
    launcher.configure(
        PluginWorkerPolicy(max_cpus=1, max_memory_mb=512, max_pids=32, max_open_files=128, max_file_size_mb=32),
        "oss_dev",
    )
    ready = await launcher.prepare_dependency_environment(store, artifact)
    assert store.get_ready(ready.digest) == ready
    assert not (ready.site_packages_path / "langbot_plugin").exists()
    assert (ready.site_packages_path / "pydantic").is_dir()
    assert await launcher.prepare_dependency_environment(store, artifact) == ready
