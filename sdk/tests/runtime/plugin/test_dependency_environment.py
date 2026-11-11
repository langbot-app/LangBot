from __future__ import annotations

import asyncio
import hashlib
import io
import pathlib
import stat
import zipfile

import pytest

from langbot_plugin.runtime.plugin import (
    dependency_environment as dependency_environment_module,
)
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentPreparationError,
    PluginDependencyEnvironmentStore,
)


def _package(requirements: str = "third-party-demo==1.0.0\n") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "manifest.yaml",
            """
kind: Plugin
metadata:
  author: tester
  name: dependency-demo
  version: 1.0.0
spec: {}
""",
        )
        archive.writestr("requirements.txt", requirements)
    return output.getvalue()


def _artifact(tmp_path, requirements: str = "third-party-demo==1.0.0\n"):
    package = _package(requirements)
    digest = hashlib.sha256(package).hexdigest()
    artifact_store = PluginArtifactStore(tmp_path / "plugin-runtime")
    return artifact_store.install_package(package, digest)


def _publish_fake_distribution(staging, requirements):
    assert requirements == ("third-party-demo==1.0.0",)
    (staging.site_packages_path / "third_party_demo.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    metadata_path = staging.site_packages_path / "third_party_demo-1.0.0.dist-info"
    metadata_path.mkdir()
    (metadata_path / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: third-party-demo\nVersion: 1.0.0\n",
        encoding="utf-8",
    )


async def test_missing_requirement_is_prepared_once_and_reused(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    install_count = 0
    original_rename = dependency_environment_module.os.rename

    def macos_rename(source, target):
        if not pathlib.Path(source).stat().st_mode & stat.S_IWUSR:
            raise PermissionError("macOS cannot rename a read-only directory")
        original_rename(source, target)
        assert store.get_ready(pathlib.Path(target).name) is None

    monkeypatch.setattr(dependency_environment_module.os, "rename", macos_rename)

    async def installer(staging, requirements):
        nonlocal install_count
        install_count += 1
        _publish_fake_distribution(staging, requirements)

    first = await store.prepare(
        artifact,
        runtime_fingerprint="runtime-v1",
        installer=installer,
    )
    second = await store.prepare(
        artifact,
        runtime_fingerprint="runtime-v1",
        installer=installer,
    )

    assert first == second
    assert install_count == 1
    assert first.site_packages_path.joinpath("third_party_demo.py").is_file()
    assert stat.S_IMODE(first.root_path.stat().st_mode) == 0o555
    assert stat.S_IMODE(first.site_packages_path.stat().st_mode) == 0o555
    assert (
        stat.S_IMODE(
            first.site_packages_path.joinpath("third_party_demo.py").stat().st_mode
        )
        & 0o222
        == 0
    )


async def test_concurrent_preparation_runs_installer_once(tmp_path):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    install_started = asyncio.Event()
    release_install = asyncio.Event()
    install_count = 0

    async def installer(staging, requirements):
        nonlocal install_count
        install_count += 1
        install_started.set()
        await release_install.wait()
        _publish_fake_distribution(staging, requirements)

    first_task = asyncio.create_task(
        store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )
    )
    await install_started.wait()
    second_task = asyncio.create_task(
        store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )
    )
    await asyncio.sleep(0)
    release_install.set()

    first, second = await asyncio.gather(first_task, second_task)

    assert first == second
    assert install_count == 1


async def test_failure_removes_staging_and_does_not_poison_digest(tmp_path):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")

    async def failing_installer(staging, requirements):
        (staging.site_packages_path / "half-installed.py").write_text(
            "BROKEN = True\n",
            encoding="utf-8",
        )
        raise DependencyEnvironmentPreparationError("dependency download failed")

    with pytest.raises(
        DependencyEnvironmentPreparationError,
        match="dependency download failed",
    ):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=failing_installer,
        )

    assert list(store.environments_path.iterdir()) == []

    async def successful_installer(staging, requirements):
        _publish_fake_distribution(staging, requirements)

    ready = await store.prepare(
        artifact,
        runtime_fingerprint="runtime-v1",
        installer=successful_installer,
    )
    assert ready.site_packages_path.is_dir()


async def test_cancellation_removes_dependency_staging(tmp_path):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    install_started = asyncio.Event()
    release_install = asyncio.Event()

    async def installer(staging, requirements):
        del requirements
        (staging.site_packages_path / "partial.py").write_text(
            "PARTIAL = True\n",
            encoding="utf-8",
        )
        install_started.set()
        await release_install.wait()

    prepare_task = asyncio.create_task(
        store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )
    )
    await install_started.wait()
    prepare_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await prepare_task
    assert list(store.environments_path.iterdir()) == []


async def test_artifact_requirements_reject_pip_control_options(tmp_path):
    artifact = _artifact(tmp_path, "--extra-index-url https://attacker.invalid\n")
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")

    async def installer(staging, requirements):  # pragma: no cover - must not run
        raise AssertionError("installer must not receive pip control options")

    with pytest.raises(
        DependencyEnvironmentPreparationError,
        match="cannot contain pip options",
    ):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )


@pytest.mark.parametrize(
    "runtime_version",
    ["0.5.5", "0.6.0a1", "0.6.0b1", "0.6.0rc1", "0.6.0.dev1", "0.6.0"],
)
async def test_runtime_sdk_requirement_is_not_installed_into_plugin_environment(
    tmp_path,
    monkeypatch,
    runtime_version,
):
    artifact = _artifact(
        tmp_path,
        "langbot-plugin>=0.3.0\nthird-party-demo==1.0.0\n",
    )
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    captured_requirements = None

    monkeypatch.setattr(
        dependency_environment_module.importlib.metadata,
        "version",
        lambda name: runtime_version if name == "langbot-plugin" else "1.0.0",
    )

    async def installer(staging, requirements):
        nonlocal captured_requirements
        captured_requirements = requirements
        _publish_fake_distribution(staging, requirements)

    await store.prepare(
        artifact,
        runtime_fingerprint="runtime-v1",
        installer=installer,
    )

    assert captured_requirements == ("third-party-demo==1.0.0",)


@pytest.mark.parametrize("requirement", ["==0.6.0b5", "==0.6.1", "==0.6.2", "==0.6.3"])
async def test_runtime_sdk_legacy_06_exact_pin_accepts_newer_compatible_06_runtime(
    tmp_path,
    monkeypatch,
    requirement,
):
    artifact = _artifact(
        tmp_path,
        f"langbot-plugin{requirement}\nthird-party-demo==1.0.0\n",
    )
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    captured_requirements = None
    monkeypatch.setattr(
        dependency_environment_module.importlib.metadata,
        "version",
        lambda name: "0.6.3" if name == "langbot-plugin" else "1.0.0",
    )

    async def installer(staging, requirements):
        nonlocal captured_requirements
        captured_requirements = requirements
        _publish_fake_distribution(staging, requirements)

    await store.prepare(
        artifact,
        runtime_fingerprint="runtime-v1",
        installer=installer,
    )

    assert captured_requirements == ("third-party-demo==1.0.0",)


@pytest.mark.parametrize("requirement", ["==0.5.5", "==0.7.0", ">=0.7.0", "!=0.6.3"])
async def test_runtime_sdk_compatibility_does_not_relax_other_constraints(
    tmp_path,
    monkeypatch,
    requirement,
):
    artifact = _artifact(tmp_path, f"langbot-plugin{requirement}\n")
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    monkeypatch.setattr(
        dependency_environment_module.importlib.metadata,
        "version",
        lambda name: "0.6.3",
    )

    async def installer(staging, requirements):  # pragma: no cover - must not run
        raise AssertionError("installer must not run")

    with pytest.raises(DependencyEnvironmentPreparationError):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )


@pytest.mark.parametrize(
    ("runtime_version", "requirement"),
    [
        ("0.5.5", ">=9.0.0"),
        ("0.6.0b1", ">=0.6.0"),
        ("0.6.0b1", ">=0.7.0"),
        ("0.6.0b1", ">=0.3.0,<0.6.0"),
        ("0.6.0b1", ">=0.3.0,!=0.6.0b1"),
        ("0.6.0b1", "==0.5.5"),
    ],
)
async def test_runtime_sdk_requirement_rejects_incompatible_runtime_version(
    tmp_path,
    monkeypatch,
    runtime_version,
    requirement,
):
    artifact = _artifact(tmp_path, f"langbot-plugin{requirement}\n")
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    monkeypatch.setattr(
        dependency_environment_module.importlib.metadata,
        "version",
        lambda name: runtime_version,
    )

    async def installer(staging, requirements):  # pragma: no cover - must not run
        raise AssertionError("installer must not run")

    with pytest.raises(
        DependencyEnvironmentPreparationError,
        match=f"Runtime provides langbot-plugin=={runtime_version}",
    ):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )


async def test_dependency_environment_rejects_too_many_entries(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    monkeypatch.setattr(dependency_environment_module, "_MAX_ENVIRONMENT_ENTRIES", 2)

    async def installer(staging, requirements):
        del requirements
        for index in range(3):
            (staging.site_packages_path / f"entry-{index}.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )

    with pytest.raises(
        DependencyEnvironmentPreparationError,
        match="contains too many entries",
    ):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )

    assert list(store.environments_path.iterdir()) == []


async def test_dependency_environment_rejects_total_size_limit(tmp_path, monkeypatch):
    artifact = _artifact(tmp_path)
    store = PluginDependencyEnvironmentStore(tmp_path / "plugin-runtime")
    monkeypatch.setattr(
        dependency_environment_module,
        "_MAX_ENVIRONMENT_TOTAL_BYTES",
        8,
    )

    async def installer(staging, requirements):
        del requirements
        (staging.site_packages_path / "oversized.py").write_bytes(b"x" * 9)

    with pytest.raises(
        DependencyEnvironmentPreparationError,
        match="exceeds the total size limit",
    ):
        await store.prepare(
            artifact,
            runtime_fingerprint="runtime-v1",
            installer=installer,
        )

    assert list(store.environments_path.iterdir()) == []
