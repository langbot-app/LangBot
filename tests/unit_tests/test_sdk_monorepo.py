"""Boundaries between Core and the in-tree plugin SDK (sdk/)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github/workflows'


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def test_core_pins_the_in_tree_sdk_version():
    gate = load_script('check_sdk_release_pin')
    assert gate.core_sdk_pin(ROOT) == gate.sdk_version(ROOT)
    sdk = tomllib.loads((ROOT / 'sdk/pyproject.toml').read_text())['project']
    assert sdk['name'] == 'langbot-plugin'
    assert (ROOT / 'sdk/src/langbot_plugin/version.py').read_text().strip() == f'__version__ = "{sdk["version"]}"'


def test_core_never_resolves_the_sdk_from_the_tree():
    # Core and its artifacts install the PyPI pin; a uv path source would make
    # Docker/fnOS/source installs diverge from the published Core wheel.
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert 'langbot-plugin' not in project.get('tool', {}).get('uv', {}).get('sources', {})
    assert 'workspace' not in project.get('tool', {}).get('uv', {})


@pytest.mark.parametrize(
    ('filename', 'job'),
    [
        ('build-release-artifacts.yaml', 'build-artifacts'),
        ('build-fnos-fpk.yaml', 'build-fnos-fpk'),
        ('build-docker-image.yml', 'publish-docker-image'),
        ('publish-to-pypi.yml', 'build-and-publish'),
        ('discord-release.yml', 'announce'),
    ],
)
def test_core_release_jobs_only_accept_core_tags(filename, job):
    condition = workflow(filename)['jobs'][job]['if']
    assert "startsWith(github.event.release.tag_name, 'v')" in condition or (
        "startsWith(inputs.source_ref || github.event.release.tag_name, 'v')" in condition
    )


def test_core_release_workflows_run_the_sdk_pin_gate():
    for filename in ('publish-to-pypi.yml', 'build-docker-image.yml'):
        text = (WORKFLOWS / filename).read_text()
        assert 'scripts/check_sdk_release_pin.py' in text, filename
    docker_checkout = workflow('build-docker-image.yml')['jobs']['publish-docker-image']['steps'][0]
    assert docker_checkout['with']['fetch-depth'] == 0


def test_sdk_workflows_never_touch_core_releases():
    for path in WORKFLOWS.glob('sdk-*.yml'):
        data = workflow(path.name)
        events = data.get('on', data.get(True))
        assert 'release' not in events, path.name
        assert 'langbot-app/langbot-plugin-sdk' not in path.read_text(), path.name
        for event in ('push', 'pull_request'):
            if event in events and 'paths' in events[event]:
                assert all(p.startswith(('sdk/', '.github/workflows/sdk-')) for p in events[event]['paths']), path.name
    publish = workflow('sdk-publish.yml')
    assert publish.get('on', publish.get(True))['push']['tags'] == ['sdk/v*']
    assert 'gh release' not in (WORKFLOWS / 'sdk-publish.yml').read_text()


def test_core_artifact_checker_rejects_sdk_sources():
    artifacts = load_script('check_core_artifacts')
    assert artifacts.forbidden_member('sdk/src/langbot_plugin/__init__.py')
    assert artifacts.forbidden_member('langbot-4.11.7/sdk/pyproject.toml')
    assert artifacts.forbidden_member('app/sdk/README.md')
    assert not artifacts.forbidden_member('langbot/pkg/plugin/connector.py')
    assert not artifacts.forbidden_member('app/.venv/lib/python3.12/site-packages/langbot_plugin/__init__.py')
    assert 'prune sdk' in (ROOT / 'MANIFEST.in').read_text()
    assert '/sdk export-ignore' in (ROOT / '.gitattributes').read_text()
    assert 'sdk/' in (ROOT / '.dockerignore').read_text().splitlines()
    assert "--exclude='/sdk/'" in (ROOT / 'packaging/fnos/build.sh').read_text()


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.com', *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def sdk_repo(tmp_path):
    if shutil.which('git') is None:
        pytest.skip('git is required')
    (tmp_path / 'sdk/src/langbot_plugin').mkdir(parents=True)
    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "langbot"\nversion = "1.0.0"\ndependencies = ["langbot-plugin==0.9.0"]\n'
    )
    (tmp_path / 'sdk/pyproject.toml').write_text('[project]\nname = "langbot-plugin"\nversion = "0.9.0"\n')
    (tmp_path / 'sdk/src/langbot_plugin/__init__.py').write_text('')
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'add', '-A')
    git(tmp_path, 'commit', '-q', '-m', 'init')
    return tmp_path


def test_release_gate_accepts_a_released_unchanged_sdk(sdk_repo):
    gate = load_script('check_sdk_release_pin')
    git(sdk_repo, 'tag', 'sdk/v0.9.0')
    (sdk_repo / 'README.md').write_text('core change')
    git(sdk_repo, 'add', '-A')
    git(sdk_repo, 'commit', '-q', '-m', 'core only')
    assert gate.check(sdk_repo, check_pypi=False) == '0.9.0'


def test_release_gate_rejects_missing_tag_and_unreleased_sdk_changes(sdk_repo):
    gate = load_script('check_sdk_release_pin')
    with pytest.raises(SystemExit, match='sdk/v0.9.0 does not exist'):
        gate.check(sdk_repo, check_pypi=False)
    git(sdk_repo, 'tag', 'sdk/v0.9.0')
    (sdk_repo / 'sdk/src/langbot_plugin/__init__.py').write_text('NEW = 1\n')
    git(sdk_repo, 'commit', '-q', '-am', 'unreleased sdk change')
    with pytest.raises(SystemExit, match='changed since sdk/v0.9.0'):
        gate.check(sdk_repo, check_pypi=False)


def test_release_gate_rejects_pin_drift_and_loose_pins(sdk_repo):
    gate = load_script('check_sdk_release_pin')
    (sdk_repo / 'sdk/pyproject.toml').write_text('[project]\nname = "langbot-plugin"\nversion = "0.9.1"\n')
    with pytest.raises(SystemExit, match='Core pins langbot-plugin==0.9.0'):
        gate.check(sdk_repo, check_pypi=False)
    (sdk_repo / 'pyproject.toml').write_text(
        '[project]\nname = "langbot"\nversion = "1.0.0"\ndependencies = ["langbot-plugin>=0.9.0"]\n'
    )
    with pytest.raises(SystemExit, match='exactly'):
        gate.check(sdk_repo, check_pypi=False)


def test_release_gate_skips_trees_without_sdk(tmp_path):
    gate = load_script('check_sdk_release_pin')
    assert gate.check(tmp_path, check_pypi=False) is None
