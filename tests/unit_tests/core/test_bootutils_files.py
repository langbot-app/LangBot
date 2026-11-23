"""Regression tests for bootutils.files.generate_files.

Historically the directory-creation loop iterated as
``for required_paths in required_paths:`` while the function declared
``global required_paths``, which rebound the module-level list to the last
iterated string (``'data/labels'``) after the first call. A second call then
iterated over that string character by character and attempted to create
single-character directories. These tests pin the module-level state and the
repeat-call behaviour.
"""

from __future__ import annotations

import asyncio
from importlib import import_module


def get_files_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.core.bootutils.files')


def test_required_paths_stays_a_list_after_generate_files(tmp_path, monkeypatch):
    files = get_files_module()
    monkeypatch.chdir(tmp_path)
    original = list(files.required_paths)

    asyncio.run(files.generate_files())

    assert isinstance(files.required_paths, list)
    assert files.required_paths == original


def test_generate_files_is_idempotent(tmp_path, monkeypatch):
    files = get_files_module()
    monkeypatch.chdir(tmp_path)

    first = asyncio.run(files.generate_files())
    second = asyncio.run(files.generate_files())

    for path in files.required_paths:
        assert (tmp_path / path).is_dir()
    # The config template is copied on the first run only.
    assert first == ['data/config.yaml']
    assert second == []
    assert (tmp_path / 'data' / 'config.yaml').is_file()
    # No junk single-character directories left behind by a second run.
    assert sorted(p.name for p in tmp_path.iterdir()) == ['data', 'temp']
