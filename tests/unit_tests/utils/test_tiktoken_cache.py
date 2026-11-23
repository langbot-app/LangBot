from __future__ import annotations

import pytest

from langbot.pkg.utils import tiktoken_cache

NAME = '9b5ad71b2ce5302211f9c61530b329a4922fc6a4'
OTHER = 'fb374d419588a4632f3f557e76b4b70aebbca790'


@pytest.fixture
def bundled(tmp_path, monkeypatch):
    directory = tmp_path / 'litellm' / 'litellm_core_utils' / 'tokenizers'
    directory.mkdir(parents=True)
    (directory / '__init__.py').write_text('')
    (directory / 'anthropic_tokenizer.json').write_bytes(b'{}\r\n')
    monkeypatch.setattr(tiktoken_cache, '_bundled_tokenizer_dir', lambda: directory)
    monkeypatch.delenv(tiktoken_cache.CUSTOM_CACHE_ENV, raising=False)
    return directory


def test_crlf_files_are_copied_as_lf_and_litellm_is_pointed_at_them(bundled, tmp_path, monkeypatch):
    (bundled / NAME).write_bytes(b'IQ== 0\r\nIg== 1\r\n')
    (bundled / OTHER).write_bytes(b'Iw== 0\n')
    target = tmp_path / 'data' / 'tiktoken_cache'

    assert tiktoken_cache.ensure_offline_tiktoken_cache(target) == target

    assert (target / NAME).read_bytes() == b'IQ== 0\nIg== 1\n'
    assert (target / OTHER).read_bytes() == b'Iw== 0\n'
    assert not (target / 'anthropic_tokenizer.json').exists()
    assert not list(target.glob('*.tmp'))
    import os

    assert os.environ[tiktoken_cache.CUSTOM_CACHE_ENV] == str(target)


def test_repeated_start_rewrites_only_changed_files(bundled, tmp_path, monkeypatch):
    (bundled / NAME).write_bytes(b'IQ== 0\r\n')
    target = tmp_path / 'cache'
    tiktoken_cache.ensure_offline_tiktoken_cache(target)
    mtime = (target / NAME).stat().st_mtime_ns
    monkeypatch.delenv(tiktoken_cache.CUSTOM_CACHE_ENV)

    tiktoken_cache.ensure_offline_tiktoken_cache(target)

    assert (target / NAME).stat().st_mtime_ns == mtime


def test_lf_files_need_nothing(bundled, tmp_path):
    import os

    (bundled / NAME).write_bytes(b'IQ== 0\n')

    assert tiktoken_cache.ensure_offline_tiktoken_cache(tmp_path / 'cache') is None
    assert not (tmp_path / 'cache').exists()
    assert tiktoken_cache.CUSTOM_CACHE_ENV not in os.environ


def test_user_override_is_respected(bundled, tmp_path, monkeypatch):
    (bundled / NAME).write_bytes(b'IQ== 0\r\n')
    monkeypatch.setenv(tiktoken_cache.CUSTOM_CACHE_ENV, str(tmp_path / 'mine'))

    assert tiktoken_cache.ensure_offline_tiktoken_cache(tmp_path / 'cache') is None
    assert not (tmp_path / 'cache').exists()


def test_missing_litellm_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(tiktoken_cache, '_bundled_tokenizer_dir', lambda: None)
    monkeypatch.delenv(tiktoken_cache.CUSTOM_CACHE_ENV, raising=False)

    assert tiktoken_cache.ensure_offline_tiktoken_cache(tmp_path / 'cache') is None


def test_finds_the_installed_litellm_bundle():
    directory = tiktoken_cache._bundled_tokenizer_dir()

    assert directory is not None
    assert (directory / NAME).is_file()
