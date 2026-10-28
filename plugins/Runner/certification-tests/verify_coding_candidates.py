"""Freeze unsigned official-SDK builds; genuine b5 dependency + RPC gates.

Run with an absolute evidence directory OUTSIDE the repository after committing.
Direct launcher/loopback fixtures are not nsjail or vendor/live certification.
"""

import argparse
import asyncio
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from langbot_plugin.entities.io.context import PluginWorkerPolicy
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore
from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher

ROOT = Path(__file__).resolve().parents[2]
FOLDERS = ("acp-agent-runner", "claude-code-agent", "codex-agent")


async def verify(out):
    assert not out.exists(), "Use a fresh evidence directory; never overwrite frozen candidates"
    assert importlib.metadata.version("langbot-plugin") == "0.7.4"
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip(), "Commit before freezing"
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    out.mkdir(parents=True)
    dist = importlib.metadata.distribution("langbot-plugin")
    verified = []
    for name, encoded, _ in csv.reader(io.StringIO(dist.read_text("RECORD"))):
        if name.startswith("langbot_plugin/") and name.endswith(".py"):
            digest = hashlib.sha256(Path(dist.locate_file(name)).read_bytes()).digest()
            assert encoded == "sha256=" + base64.urlsafe_b64encode(digest).decode().rstrip("=")
            verified.append(name)
    (out / "sdk-record.json").write_text(
        json.dumps(
            dict(sdk=dist.version, verified_python_files=len(verified), python=sys.version, source_commit=commit),
            indent=2,
        )
    )
    artifacts = PluginArtifactStore(out / "runtime")
    deps = PluginDependencyEnvironmentStore(out / "runtime")
    launcher = PluginWorkerLauncher()
    launcher.configure(
        PluginWorkerPolicy(
            max_cpus=1,
            max_memory_mb=512,
            max_pids=128,
            max_open_files=256,
            max_file_size_mb=512,
            require_hard_limits=False,
        ),
        "oss_dev",
    )
    inventory = []
    for folder in FOLDERS:
        stage = out / "build-source"
        stage.mkdir(exist_ok=True)
        archive = subprocess.check_output(["git", "archive", commit, "Runner/" + folder], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(stage, filter="data")
        destination = out / "packages" / folder
        destination.mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, "-m", "langbot_plugin.cli.__init__", "build", "-o", str(destination)],
            cwd=stage / "Runner" / folder,
            text=True,
            capture_output=True,
            timeout=60,
        )
        (out / (folder + "-build.log")).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        packages = list(destination.glob("*.lbpkg"))
        assert len(packages) == 1
        package = packages[0]
        data = package.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(package) as z:
            assert not z.comment
            files = {p: hashlib.sha256(z.read(p)).hexdigest() for p in z.namelist() if not p.endswith("/")}
            for path in files:
                if path != "manifest.yaml":
                    assert z.read(path) == (stage / "Runner" / folder / path).read_bytes(), path
        artifact = artifacts.install_package(data, digest)
        assert artifacts.require_verified(digest) == artifact
        env = await launcher.prepare_dependency_environment(deps, artifact)
        assert deps.get_ready(env.digest) == env
        assert await launcher.prepare_dependency_environment(deps, artifact) == env
        assert not list(env.site_packages_path.glob("langbot_plugin*"))
        link = out / "extracted" / folder
        link.parent.mkdir(exist_ok=True)
        link.symlink_to(artifact.code_path, target_is_directory=True)
        row = dict(
            folder=folder,
            author=artifact.plugin_author,
            name=artifact.plugin_name,
            version=artifact.plugin_version,
            package=str(package),
            sha256=digest,
            bytes=len(data),
            source_commit=commit,
            files=files,
            unsigned=True,
            dependency_prepare_passed=True,
            dependency_cache_readback_passed=True,
            sdk_shadow_installed=False,
            code_path=str(artifact.code_path),
            dependency_path=str(env.site_packages_path),
        )
        inventory.append(row)
        (out / "candidate-inventory.json").write_text(json.dumps(inventory, indent=2))
        home = out / "fixture-homes" / folder
        home.mkdir(parents=True)
        child_env = {
            k: v
            for k, v in os.environ.items()
            if not any(s in k.upper() for s in ("TOKEN", "SECRET", "KEY", "PROXY", "DAEMON", "CODEX", "ANTHROPIC"))
        }
        child_env.update(
            HOME=str(home),
            LANGBOT_PLUGIN_FILE_STORAGE_DIR=str(home / "file-transfer"),
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=os.pathsep.join([str(dist.locate_file("")), str(env.site_packages_path)]),
        )
        probe = Path(__file__).with_name("coding_artifact_rpc_probe.py")
        result = subprocess.run(
            [sys.executable, str(probe), folder, str(out / (folder + "-rpc.json"))],
            cwd=artifact.code_path,
            env=child_env,
            text=True,
            capture_output=True,
            timeout=90,
        )
        (out / (folder + "-rpc.log")).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        evidence = json.loads((out / (folder + "-rpc.json")).read_text())
        assert evidence["status"] == "initialized"
        assert evidence["invalid_results"][0]["type"] == "run.failed"
        assert evidence["fixture_results"][-1]["type"] == "run.completed"
        assert "FIXTURE_OK" in json.dumps(evidence["fixture_results"])
        assert not any(e["type"] == "run.failed" for e in evidence["fixture_results"])
        row["real_sdk_discovery_rpc_fixture_passed"] = True
        (out / "candidate-inventory.json").write_text(json.dumps(inventory, indent=2))
        print(folder, artifact.plugin_version, digest, flush=True)
    assert len(inventory) == 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    asyncio.run(verify(parser.parse_args().evidence.resolve()))
