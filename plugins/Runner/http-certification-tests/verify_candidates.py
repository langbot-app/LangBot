"""Build once; real SDK artifact/dependency admission and extracted RPC fixtures.

Uses the SDK's direct/OSS dependency installer into isolated target directories.
This is not a claim of nsjail enforcement, Cloud installation or live vendor use.
"""

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
from langbot_plugin.cli.commands.buildplugin import build_plugin_process
from langbot_plugin.cli.utils.page_components import discover_plugin_components, populate_plugin_pages
from langbot_plugin.entities.io.context import PluginWorkerPolicy
from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore
from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV
from langbot_plugin.utils.discover.engine import ComponentDiscoveryEngine

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ["coze", "dashscope", "deerflow", "dify", "langflow", "n8n", "tbox", "weknora"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


async def main(destination):
    destination.mkdir(parents=True, exist_ok=False)
    packages = destination / "packages"
    packages.mkdir()
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True), (
        "Commit final source first"
    )
    distribution = importlib.metadata.distribution("langbot-plugin")
    assert distribution.version == "0.7.4"
    checked = 0
    for entry in distribution.files:
        if str(entry).startswith("langbot_plugin/") and str(entry).endswith(".py") and entry.hash:
            actual = (
                base64.urlsafe_b64encode(hashlib.sha256(distribution.locate_file(entry).read_bytes()).digest())
                .rstrip(b"=")
                .decode()
            )
            assert entry.hash.mode == "sha256" and actual == entry.hash.value, str(entry)
            checked += 1
    report = {
        "source_commit": source_commit,
        "sdk": distribution.version,
        "sdk_record_verified_python_files": checked,
        "evidence_scope": "real SDK; direct installer and local vendor fixtures; not nsjail/Cloud/live vendor",
        "plugins": [],
    }
    store = PluginArtifactStore(destination / "runtime")
    deps = PluginDependencyEnvironmentStore(destination / "runtime")
    launcher = PluginWorkerLauncher()
    launcher.configure(
        PluginWorkerPolicy(
            max_cpus=1,
            max_memory_mb=512,
            max_pids=64,
            max_open_files=256,
            max_file_size_mb=32,
            require_hard_limits=False,
        ),
        "oss_dev",
    )
    runtime_fingerprint = launcher.dependency_runtime_fingerprint()
    views = destination / "extracted"
    views.mkdir()
    for short in PLUGINS:
        folder = short + "-agent"
        source = ROOT / folder
        os.chdir(source)
        package = Path(build_plugin_process(str(packages)))
        raw = package.read_bytes()
        sha = digest(raw)
        package.chmod(0o444)
        # Official generated-manifest proof plus exact committed payload proof.
        discovery = ComponentDiscoveryEngine()
        manifest = discovery.load_component_manifest("manifest.yaml", owner="builtin", no_save=True)
        populate_plugin_pages(manifest, discover_plugin_components(manifest, discovery))
        expected_manifest = yaml.safe_dump(manifest.manifest, allow_unicode=True, sort_keys=False).encode()
        entries = {}
        with zipfile.ZipFile(package) as archive:
            for entry in archive.namelist():
                payload = archive.read(entry)
                assert payload == (expected_manifest if entry == "manifest.yaml" else (source / entry).read_bytes()), (
                    entry
                )
                entries[entry] = digest(payload)
        artifact = store.install_package(raw, sha)
        assert store.require_verified(sha) == artifact
        environment = await launcher.prepare_dependency_environment(deps, artifact)
        assert deps.get_ready(environment.digest) is not None
        assert not (environment.site_packages_path / "langbot_plugin").exists()
        (views / folder).symlink_to(artifact.code_path, target_is_directory=True)
        env = {
            k: v for k, v in os.environ.items() if not any(x in k.upper() for x in ["TOKEN", "KEY", "SECRET", "PROXY"])
        }
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env[PLUGIN_FILE_STORAGE_DIR_ENV] = str(destination / "rpc-files" / folder)
        env["PYTHONPATH"] = str(environment.site_packages_path)
        output = destination / (folder + "-rpc.json")
        run = subprocess.run(
            [
                sys.executable,
                str(ROOT / "http-certification-tests/fixtures/real_sdk_runtime_probe.py"),
                str(output),
                folder,
            ],
            cwd=artifact.code_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
        )
        (destination / (folder + "-rpc.log")).write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stderr
        rpc = json.loads(output.read_text())
        assert rpc["fixture_results"][-1]["type"] == "run.completed", rpc["fixture_results"]
        assert "FIXTURE_OK" in json.dumps(rpc["fixture_results"])
        assert not rpc["external_live_connectivity_tested"]
        report["plugins"].append(
            {
                "folder": folder,
                "author": artifact.plugin_author,
                "name": artifact.plugin_name,
                "version": artifact.plugin_version,
                "archive": str(package),
                "sha256": sha,
                "size": len(raw),
                "entries": entries,
                "dependency_environment": environment.digest,
                "dependency_site_packages": str(environment.site_packages_path),
                "dependency_runtime_fingerprint": runtime_fingerprint,
                "dependency_admission": "passed-direct-installer",
                "runtime_fixture": "passed-real-sdk-extracted-artifact",
                "artifact_code_path": str(artifact.code_path),
            }
        )
        (destination / "inventory.json").write_text(json.dumps(report, indent=2) + "\n")
    assert len(report["plugins"]) == 8
    print(json.dumps({"count": len(report["plugins"]), "inventory": str(destination / "inventory.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.evidence.resolve()))
