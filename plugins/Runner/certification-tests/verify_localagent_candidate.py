"""Verify an already-built LocalAgent archive. Never rebuild or sign it.

Real SDK artifact/dependency stores and direct OSS dependency installer; this
is NOT shared-worker nsjail or live Core/model acceptance. All packaged tests
run from the read-only extraction in a fresh process.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml
from langbot_plugin.cli.utils.page_components import discover_plugin_components, populate_plugin_pages
from langbot_plugin.entities.io.context import PluginWorkerPolicy
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore
from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify_sdk():
    dist = importlib.metadata.distribution("langbot-plugin")
    from inspect import signature

    from langbot_plugin.api.entities.builtin.runner.context import RunnerContext

    assert "paths" in signature(RunnerContext.export_box_files).parameters
    checked = {}
    for entry in dist.files or []:
        if entry.hash is None:
            continue
        data = dist.locate_file(entry).read_bytes()
        digest = hashlib.new(entry.hash.mode, data).digest()
        assert base64.urlsafe_b64encode(digest).decode().rstrip("=") == entry.hash.value, str(entry)
        checked[str(entry)] = sha(data)
    assert checked
    return {"version": dist.version, "record_checked_files": checked, "python": sys.version}


async def verify(args):
    source = args.source.resolve()
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    package = args.package.resolve()
    raw = package.read_bytes()
    digest = sha(raw)

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(source), *arguments])

    commit = git("rev-parse", "HEAD").decode().strip()
    assert not git("status", "--porcelain", "--", "."), "Candidate source must be clean"
    prefix = git("rev-parse", "--show-prefix").decode().strip()
    tracked = git("ls-tree", "-r", "--name-only", "HEAD", "--", ".").decode().splitlines()
    entries = {}
    with zipfile.ZipFile(package) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        # Compare every payload byte with the commit; SDK only rewrites manifest.
        assert set(archive.namelist()) == set(tracked)
        for name in tracked:
            payload = archive.read(name)
            if name != "manifest.yaml":
                assert payload == git("show", f"HEAD:{prefix}{name}"), name
            entries[name] = sha(payload)
        os.chdir(source)
        discovery = ComponentDiscoveryEngine()
        manifest = discovery.load_component_manifest("manifest.yaml", owner="builtin", no_save=True)
        populate_plugin_pages(manifest, discover_plugin_components(manifest, discovery))
        generated = yaml.safe_dump(manifest.manifest, allow_unicode=True, sort_keys=False).encode()
        assert archive.read("manifest.yaml") == generated
        assert manifest.manifest["execution"]["sharedRuntime"] == "shared-runtime-v1"
    sdk = verify_sdk()
    artifact_store = PluginArtifactStore(evidence / "runtime")
    artifact = artifact_store.install_package(raw, digest)
    assert artifact_store.require_verified(digest) == artifact
    store = PluginDependencyEnvironmentStore(evidence / "runtime")
    launcher = PluginWorkerLauncher()
    launcher.configure(
        PluginWorkerPolicy(max_cpus=1, max_memory_mb=512, max_pids=32, max_open_files=128, max_file_size_mb=32),
        "oss_dev",
    )
    ready = await launcher.prepare_dependency_environment(store, artifact)
    assert store.get_ready(ready.digest) == ready
    assert await launcher.prepare_dependency_environment(store, artifact) == ready
    assert not (ready.site_packages_path / "langbot_plugin").exists()
    assert (ready.site_packages_path / "pydantic").is_dir()
    (evidence / "sdk-record.json").write_text(json.dumps(sdk, indent=2) + "\n")
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": os.pathsep.join(
            (str(launcher.runtime_import_root), str(ready.site_packages_path), str(artifact.code_path))
        ),
    }
    commands = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-q",
        "-p",
        "no:cacheprovider",
        "--junitxml=" + str(evidence / "tests.xml"),
    ]
    result = subprocess.run(
        commands,
        cwd=artifact.code_path,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    (evidence / "packaged-tests.log").write_text(result.stdout)
    report = {
        "source_commit": commit,
        "package": str(package),
        "sha256": digest,
        "size": len(raw),
        "entry_sha256": entries,
        "artifact_code": str(artifact.code_path),
        "sdk_version": sdk["version"],
        "sdk_record_checked_count": len(sdk["record_checked_files"]),
        "dependency_environment": str(ready.root_path),
        "dependency_environment_digest": ready.digest,
        "dependency_admission": True,
        "cache_readback": True,
        "sdk_shadow_installed": False,
        "packaged_tests_exit": result.returncode,
        "command": commands,
        "limitations": "Direct OSS dependency installer and one in-process real SDK component over loopback RPC; simulated Host/model/storage/credentials/Box only. No supervisor/nsjail, live Core DB, signer, upstream model, or live Workspace admission.",
    }
    (evidence / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "entry_sha256"}, indent=2))
    assert result.returncode == 0, result.stdout
    assert sha(package.read_bytes()) == digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True, help="New directory, must not already exist")
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "LocalAgent")
    asyncio.run(verify(parser.parse_args()))
