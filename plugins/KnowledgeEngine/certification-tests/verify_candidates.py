"""Build exact unsigned archives and exercise genuine SDK 0.7.4 admission.

Uses SDK ArtifactStore, DependencyEnvironmentStore.prepare and its real direct
pip installer. This is NOT nsjail/cgroup certification or a production install.
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
from pathlib import Path
import subprocess
import sys
import zipfile

from langbot_plugin.runtime.plugin.artifact import PluginArtifactStore
from langbot_plugin.runtime.plugin.dependency_environment import PluginDependencyEnvironmentStore
from langbot_plugin.runtime.plugin.worker_launcher import PluginWorkerLauncher
from langbot_plugin.entities.io.context import PluginWorkerPolicy

NAMES = ['DifyDatasetsConnector', 'FastGPTConnector', 'LangRAG', 'RAGFlowConnector', 'LongTermMemory']
ROOT = Path(__file__).resolve().parents[1]


async def verify(out):
    assert importlib.metadata.version('langbot-plugin') == '0.7.4'
    out.mkdir(parents=True, exist_ok=True)
    dist = importlib.metadata.distribution('langbot-plugin')
    verified = []
    for name, encoded, size in csv.reader(io.StringIO(dist.read_text('RECORD'))):
        if name.startswith('langbot_plugin/') and name.endswith('.py'):
            digest = hashlib.sha256(Path(dist.locate_file(name)).read_bytes()).digest()
            assert encoded == 'sha256=' + base64.urlsafe_b64encode(digest).decode().rstrip('=')
            verified.append(name)
    (out / 'sdk-environment.json').write_text(json.dumps({
        'sdk': dist.version, 'python': sys.version, 'sdk_record_verified_files': len(verified),
        'source': 'installed PyPI distribution, not local SDK source',
        'runtime_distributions': sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions()),
    }, indent=2))
    artifacts = PluginArtifactStore(out / 'runtime')
    deps = PluginDependencyEnvironmentStore(out / 'runtime')
    launcher = PluginWorkerLauncher()
    launcher.configure(PluginWorkerPolicy(max_cpus=1, max_memory_mb=512, max_pids=128, max_open_files=256, max_file_size_mb=512, require_hard_limits=False), 'oss_dev')
    inventory = []
    for name in NAMES:
        dest = out / 'packages' / name
        dest.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([str(Path(sys.executable).parent / 'lbp'), 'build', '-o', str(dest)],
                                cwd=ROOT / name, capture_output=True, text=True, timeout=60)
        (out / (name + '-build.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
        packages = list(dest.glob('*.lbpkg'))
        assert len(packages) == 1
        package = packages[0]
        data = package.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        with zipfile.ZipFile(package) as z:
            assert not z.comment, 'Candidates must remain unsigned'
            entries = [{'path': p, 'sha256': hashlib.sha256(z.read(p)).hexdigest(), 'bytes': len(z.read(p))}
                       for p in sorted(z.namelist()) if not p.endswith('/')]
        artifact = artifacts.install_package(data, digest)
        assert artifacts.require_verified(digest) == artifact
        env = await launcher.prepare_dependency_environment(deps, artifact)
        assert deps.get_ready(env.digest) == env
        assert await launcher.prepare_dependency_environment(deps, artifact) == env
        assert not list(env.site_packages_path.glob('langbot_plugin*')), 'SDK must not be shadow installed'
        row = {'name': name, 'author': artifact.plugin_author, 'version': artifact.plugin_version,
               'package': str(package), 'sha256': digest, 'bytes': len(data), 'files': entries,
               'code_path': str(artifact.code_path), 'dependency_path': str(env.site_packages_path),
               'environment_digest': env.digest, 'requirements_digest': env.requirements_digest,
               'dependency_prepare_passed': True, 'dependency_cache_readback_passed': True,
               'sdk_shadow_installed': False, 'unsigned': True,
               'resolved_dependency_distributions': sorted(
                   f'{d.metadata["Name"]}=={d.version}' for d in
                   importlib.metadata.distributions(path=[str(env.site_packages_path)]))}
        inventory.append(row)
        (out / 'candidate-inventory.json').write_text(json.dumps(inventory, indent=2))
        print(name, artifact.plugin_version, digest, flush=True)
        child_env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
                     'PYTHONPATH': os.pathsep.join([str(dist.locate_file('')), str(env.site_packages_path)])}
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('sdk_rpc_probe.py')),
                                 str(artifact.code_path), str(out), name, digest],
                                cwd=artifact.code_path, env=child_env, text=True, capture_output=True, timeout=100)
        (out / (name + '-rpc.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout + result.stderr
    saved = json.loads((out / 'candidate-inventory.json').read_text())
    assert len(saved) == len({r['name'] for r in saved}) == 5
    assert {r['name'] for r in saved} == set(NAMES)
    print('VERIFIED 5 exact unsigned candidates, dependencies, discovery and RPC isolation')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(verify(args.evidence.resolve()))
