"""Load identity consumers from integrity-checked official plugin source."""

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext


SOURCE_LOCK = Path(__file__).resolve().parents[1] / 'fixtures' / 'legacy_plugin_identity_sources.json'


def verified_plugin_root() -> Path:
    """Allow optional local execution, but never skip an explicitly provisioned source."""
    configured = os.environ.get('LANGBOT_LEGACY_PLUGIN_ROOT')
    if configured is None:
        pytest.skip('set LANGBOT_LEGACY_PLUGIN_ROOT to the official revision in legacy_plugin_identity_sources.json')
    if not configured.strip():
        pytest.fail('LANGBOT_LEGACY_PLUGIN_ROOT is set but empty', pytrace=False)
    root = Path(configured).resolve()
    lock = json.loads(SOURCE_LOCK.read_text())
    for relative, expected in lock['files'].items():
        path = root / relative
        if not path.resolve().is_relative_to(root) or not path.is_file():
            pytest.fail(f'Official plugin fixture is missing or outside its root: {relative}', pytrace=False)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            pytest.fail(
                f'Official plugin fixture hash mismatch: {relative}; expected {lock["repository"]}@{lock["revision"]}',
                pytrace=False,
            )
    return root


def load_identity_helper(root: Path, folder: str, method: str, error_name: str):
    """Execute actual identity code and its error class without vendor client I/O."""
    plugin = root / 'Runner' / folder
    path = plugin / 'components/runner/default.py'
    tree = ast.parse(path.read_text())
    runner_classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'DefaultRunner']
    assert len(runner_classes) == 1, f'{path}: expected one DefaultRunner'
    methods = [node for node in runner_classes[0].body if isinstance(node, ast.FunctionDef) and node.name == method]
    assert len(methods) == 1, f'{path}: expected one {method}'
    client_path = plugin / 'pkg' / f'{folder.removesuffix("-agent")}_client.py'
    client_tree = ast.parse(client_path.read_text())
    errors = [node for node in client_tree.body if isinstance(node, ast.ClassDef) and node.name == error_name]
    assert len(errors) == 1, f'{client_path}: expected one {error_name}'

    scoped_path = plugin / 'pkg/scoped_identity.py'
    spec = importlib.util.spec_from_file_location(f'identity_contract_{folder.replace("-", "_")}', scoped_path)
    assert spec is not None and spec.loader is not None
    scoped_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scoped_module)
    namespace = {'RunnerContext': RunnerContext, 'scoped_identity': scoped_module.scoped_identity}
    exec(compile(ast.Module(body=errors, type_ignores=[]), str(client_path), 'exec'), namespace)
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[method], namespace[error_name]
