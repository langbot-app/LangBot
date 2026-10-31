"""Exercise release tag selection without building or pushing an image."""

import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def _build_args(tmp_path, step_name, version):
    workflow = yaml.safe_load((ROOT / '.github/workflows/build-docker-image.yml').read_text())
    steps = workflow['jobs']['publish-docker-image']['steps']
    step = next(step for step in steps if step['name'] == step_name)
    command = step['run'].replace('${{ github.sha }}', 'a' * 40)
    command = command.replace('${{ steps.check_version.outputs.version }}', version)
    capture = tmp_path / 'docker-args'
    script = 'docker() { printf "%s\\n" "$@" > "$CAPTURE"; };\n' + command
    if 'env' in step:
        assert step['env']['RELEASE_VERSION'] == '${{ steps.check_version.outputs.version }}'
    subprocess.run(
        ['bash', '-euo', 'pipefail', '-c', script],
        check=True,
        env={**os.environ, 'CAPTURE': str(capture), 'RELEASE_VERSION': version},
    )
    args = capture.read_text().splitlines()
    assert '--push' in args
    assert args[args.index('--platform') + 1] == 'linux/arm64,linux/amd64'
    assert args[args.index('--build-arg') + 1] == 'LANGBOT_BUILD_REVISION=' + 'a' * 40
    return [args[i + 1] for i, value in enumerate(args) if value == '-t'], step['if']


@pytest.mark.parametrize('version', ['v4.11.0-beta.3', 'v4.12.0-beta.1'])
def test_beta_release_updates_beta_but_not_latest(tmp_path, version):
    tags, condition = _build_args(tmp_path, 'Build for Pre-release', version)
    assert tags == [f'rockchin/langbot:{version}', 'rockchin/langbot:beta']
    assert condition == '${{ github.event.release.prerelease == true }}'


@pytest.mark.parametrize('version', ['v4.11.0-rc.1', 'v4.12.0-alpha.1'])
def test_other_prereleases_do_not_update_channels(tmp_path, version):
    tags, _ = _build_args(tmp_path, 'Build for Pre-release', version)
    assert tags == [f'rockchin/langbot:{version}']


def test_stable_release_keeps_latest_without_updating_beta(tmp_path):
    tags, condition = _build_args(tmp_path, 'Build for Release', 'v4.11.0')
    assert tags == ['rockchin/langbot:v4.11.0', 'rockchin/langbot:latest']
    assert condition == '${{ github.event.release.prerelease == false }}'
