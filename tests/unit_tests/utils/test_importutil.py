"""Exercise module discovery and resource reads at their observable boundaries."""

from __future__ import annotations

import importlib
import os
import sys

import pytest

import langbot
from langbot.pkg.utils import importutil


@pytest.fixture
def package_root(tmp_path, monkeypatch):
    # Make a temporary package discoverable without changing the real source tree.
    monkeypatch.setattr(importutil, '__file__', str(tmp_path / 'pkg' / 'utils' / 'importutil.py'))
    monkeypatch.setattr(langbot, '__path__', [*langbot.__path__, str(tmp_path)])
    try:
        yield tmp_path
    finally:
        for name in tuple(sys.modules):
            if name == 'langbot.qa_fixture' or name.startswith('langbot.qa_fixture.'):
                sys.modules.pop(name)
        if hasattr(langbot, 'qa_fixture'):
            del langbot.qa_fixture


def _write_package(directory):
    directory.mkdir(parents=True)
    (directory / '__init__.py').write_text('', encoding='utf-8')
    return directory


def test_discovers_modules_in_real_packages_without_importing_other_entries(package_root):
    parent = _write_package(package_root / 'qa_fixture')
    first = _write_package(parent / 'first')
    second = _write_package(parent / 'second')
    (first / 'alpha.py').write_text("VALUE = 'alpha'\n", encoding='utf-8')
    (first / 'beta.py').write_text("VALUE = 'beta'\n", encoding='utf-8')
    (second / 'gamma.py').write_text("VALUE = 'gamma'\n", encoding='utf-8')
    (first / 'readme.txt').write_text('not a module', encoding='utf-8')
    (first / 'settings.json').write_text('{}', encoding='utf-8')
    _write_package(first / 'nested')
    first_pkg = importlib.import_module('langbot.qa_fixture.first')
    second_pkg = importlib.import_module('langbot.qa_fixture.second')

    importutil.import_modules_in_pkgs([first_pkg, second_pkg])

    loaded = {
        name: module.VALUE
        for name, module in sys.modules.items()
        if name.startswith(('langbot.qa_fixture.first.', 'langbot.qa_fixture.second.'))
    }
    assert loaded == {
        'langbot.qa_fixture.first.alpha': 'alpha',
        'langbot.qa_fixture.first.beta': 'beta',
        'langbot.qa_fixture.second.gamma': 'gamma',
    }


def test_import_dir_honors_an_alternate_package_prefix(package_root, monkeypatch):
    package = _write_package(package_root / 'qa_fixture')
    (package / 'module.py').write_text('VALUE = 42\n', encoding='utf-8')
    monkeypatch.syspath_prepend(str(package_root))

    try:
        importutil.import_dir(str(package), path_prefix='')

        assert sys.modules['qa_fixture.module'].VALUE == 42
        assert 'langbot.qa_fixture.module' not in sys.modules
    finally:
        sys.modules.pop('qa_fixture.module', None)
        sys.modules.pop('qa_fixture', None)


def test_dot_style_directory_is_forwarded_as_path(monkeypatch):
    paths = []
    monkeypatch.setattr(importutil, 'import_dir', paths.append)

    importutil.import_dot_style_dir('my.pkg.test')

    assert paths == [os.path.join('my', 'pkg', 'test')]


@pytest.mark.parametrize(
    ('read', 'api', 'edition'),
    [
        (importutil.read_resource_file, 'api:', 'edition: community'),
        (importutil.read_resource_file_bytes, b'api:', b'edition: community'),
    ],
    ids=['text', 'bytes'],
)
def test_reads_packaged_config_in_requested_representation(read, api, edition):
    result = read('templates/config.yaml')

    assert isinstance(result, type(edition))
    assert api in result
    assert edition in result


@pytest.mark.parametrize(
    'operation',
    [importutil.read_resource_file, importutil.read_resource_file_bytes, importutil.list_resource_files],
)
def test_missing_resources_raise_file_not_found(operation):
    with pytest.raises(FileNotFoundError):
        operation('templates/nonexistent-resource')


def test_lists_packaged_files():
    files = importutil.list_resource_files('templates')

    assert {'config.yaml', 'default-pipeline-config.json'} <= set(files)
    assert all(isinstance(file, str) for file in files)
