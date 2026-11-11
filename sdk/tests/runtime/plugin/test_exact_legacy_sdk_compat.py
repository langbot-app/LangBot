"""Exact, dedicated-only SDK pin admission for nine reviewed marketplace archives."""

import hashlib
import importlib.metadata
from pathlib import Path

import pytest

from langbot_plugin.runtime.plugin.artifact import PluginArtifact, PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import (
    DependencyEnvironmentPreparationError,
    PluginDependencyEnvironmentStore,
    _LEGACY_DEDICATED_SDK_061,
    _LEGACY_DEDICATED_SDK_RUNTIME_VERSIONS,
)


@pytest.fixture(params=sorted(_LEGACY_DEDICATED_SDK_RUNTIME_VERSIONS))
def reviewed_runtime(monkeypatch, request):
    monkeypatch.setattr(importlib.metadata, "version", lambda name: request.param)


@pytest.mark.parametrize("identity,digest", sorted(_LEGACY_DEDICATED_SDK_061.items()))
def test_only_exact_verified_identity_and_digest_in_dedicated_mode(
    tmp_path, reviewed_runtime, identity, digest
):
    code = tmp_path / "code"
    code.mkdir()
    (code / "requirements.txt").write_text("langbot-plugin==0.6.1\nhttpx>=0.28.1\n")

    def artifact(*, actual_digest=digest, actual_identity=identity):
        return PluginArtifact(actual_digest, tmp_path, code, *actual_identity)

    assert PluginDependencyEnvironmentStore._read_requirements(
        artifact(), execution_mode="dedicated"
    )[0] == ("httpx>=0.28.1",)
    for mode in (None, "shared-runtime-v1", "unexpected"):
        with pytest.raises(
            DependencyEnvironmentPreparationError, match="Runtime provides"
        ):
            PluginDependencyEnvironmentStore._read_requirements(
                artifact(), execution_mode=mode
            )
    with pytest.raises(DependencyEnvironmentPreparationError, match="Runtime provides"):
        PluginDependencyEnvironmentStore._read_requirements(
            artifact(actual_digest="0" * 64), execution_mode="dedicated"
        )
    with pytest.raises(DependencyEnvironmentPreparationError, match="Runtime provides"):
        PluginDependencyEnvironmentStore._read_requirements(
            artifact(actual_identity=("other-author", identity[1], identity[2])),
            execution_mode="dedicated",
        )
    (code / "requirements.txt").write_text("langbot-plugin==0.6.2\n")
    with pytest.raises(DependencyEnvironmentPreparationError, match="Runtime provides"):
        PluginDependencyEnvironmentStore._read_requirements(
            artifact(), execution_mode="dedicated"
        )


def test_runtime_version_and_downloaded_archive_are_exact(tmp_path, monkeypatch):
    archive = Path("/tmp/dify-legacy-exact.lbpkg")
    if not archive.is_file():
        pytest.skip("Exact downloaded DifyAgent archive unavailable")
    digest = _LEGACY_DEDICATED_SDK_061[("langbot-team", "DifyAgent", "0.1.10")]
    package = archive.read_bytes()
    assert hashlib.sha256(package).hexdigest() == digest
    store = PluginArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="digest mismatch"):
        store.install_package(package + b"tampered", digest)
    artifact = store.install_package(package, digest)
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.7.4")
    assert PluginDependencyEnvironmentStore._read_requirements(
        artifact, execution_mode="dedicated"
    )[0] == ("pydantic>=2.0.0", "httpx>=0.28.1")
    with pytest.raises(DependencyEnvironmentPreparationError, match="Runtime provides"):
        PluginDependencyEnvironmentStore._read_requirements(
            artifact, execution_mode="shared-runtime-v1"
        )
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.7.5")
    assert PluginDependencyEnvironmentStore._read_requirements(
        artifact, execution_mode="dedicated"
    )[0] == ("pydantic>=2.0.0", "httpx>=0.28.1")
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.7.6")
    assert PluginDependencyEnvironmentStore._read_requirements(
        artifact, execution_mode="dedicated"
    )[0] == ("pydantic>=2.0.0", "httpx>=0.28.1")
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.7.7")
    with pytest.raises(DependencyEnvironmentPreparationError, match="Runtime provides"):
        PluginDependencyEnvironmentStore._read_requirements(
            artifact, execution_mode="dedicated"
        )
