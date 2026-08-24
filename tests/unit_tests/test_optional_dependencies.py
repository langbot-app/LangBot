from __future__ import annotations

import tomllib
from pathlib import Path


def test_seekdb_is_only_declared_as_an_optional_dependency() -> None:
    project_root = Path(__file__).resolve().parents[2]
    with (project_root / 'pyproject.toml').open('rb') as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    project = pyproject['project']
    base_dependencies = project['dependencies']
    assert not any(dependency.lower().startswith('pyseekdb') for dependency in base_dependencies)
    assert project['optional-dependencies']['seekdb'] == ['pyseekdb==1.1.0.post3']
