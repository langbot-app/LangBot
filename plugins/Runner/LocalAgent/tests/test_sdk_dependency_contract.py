import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
import yaml
from packaging.requirements import Requirement
from packaging.version import Version

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _sdk_requirements():
    project = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text())
    packaged = (PLUGIN_ROOT / "requirements.txt").read_text().splitlines()
    return [
        next(Requirement(line) for line in requirements if line.startswith("langbot-plugin"))
        for requirements in (project["project"]["dependencies"], packaged)
    ]


def test_project_and_packaged_sdk_constraints_match():
    project, packaged = _sdk_requirements()
    assert project.specifier == packaged.specifier
    assert str(project.specifier) == ">=0.7.18"


@pytest.mark.parametrize("version", ["0.7.18", "0.7.19", "0.8.0", "1.0.0"])
def test_sdk_constraints_accept_stable_releases_from_minimum(version):
    assert all(requirement.specifier.contains(version) for requirement in _sdk_requirements())


@pytest.mark.parametrize("version", ["0.7.16", "0.7.17"])
def test_sdk_constraints_reject_older_releases(version):
    assert not any(requirement.specifier.contains(version) for requirement in _sdk_requirements())


def test_installed_sdk_is_a_stable_release_matching_requirements():
    installed = Version(version("langbot-plugin"))
    assert not installed.is_prerelease
    assert all(requirement.specifier.contains(installed) for requirement in _sdk_requirements())


def test_manifest_and_project_versions_match():
    project = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text())
    manifest = yaml.safe_load((PLUGIN_ROOT / "manifest.yaml").read_text())
    assert project["project"]["version"] == manifest["metadata"]["version"]
