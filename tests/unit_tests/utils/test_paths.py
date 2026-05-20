"""
Tests for langbot.pkg.utils.paths module.

Tests path utility functions:
- get_frontend_path: locates frontend build files
- get_resource_path: locates resource files
- _check_if_source_install: detects source install mode

Uses tmp_path for file system isolation where applicable.
"""

import os
import pytest


class TestCheckIfSourceInstall:
    """Test _check_if_source_install function."""

    def test_returns_true_for_source_install(self, tmp_path, monkeypatch):
        """Should return True when main.py with LangBot marker exists."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n# This is the entry point')

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths._check_if_source_install()
        assert result is True

        paths._is_source_install = None

    # Note: ``_check_if_source_install`` was refactored to walk
    # ``Path(__file__).resolve().parents`` looking for ``pyproject.toml`` +
    # ``main.py`` instead of relying on the cwd. That makes it robust to where
    # the process is launched from but also means the old "cwd doesn't have
    # main.py" / "main.py without marker" / "IOError on read" cases no longer
    # apply — there's no file read at all. The corresponding negative tests
    # were removed; ``test_returns_true_for_source_install`` still exercises
    # the positive path because the repo checkout itself is a source install.


class TestGetFrontendPath:
    """Test get_frontend_path function."""

    def test_returns_web_dist_by_default(self):
        """Should return a path containing web/dist as default."""
        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_frontend_path()
        # The result should contain web/dist or be an absolute path to it
        assert 'web/dist' in result or result.endswith('dist')

        paths._is_source_install = None

    def test_finds_dist_directory_in_source_mode(self, tmp_path, monkeypatch):
        """Should find web/dist when running from source mode."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n')

        web_dist = tmp_path / 'web' / 'dist'
        web_dist.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_frontend_path()
        assert result == 'web/dist'

        paths._is_source_install = None

    def test_prefers_dist_over_out_in_source_mode(self, tmp_path, monkeypatch):
        """Should prefer web/dist over web/out when both exist in source mode."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n')

        web_dist = tmp_path / 'web' / 'dist'
        web_dist.mkdir(parents=True)
        web_out = tmp_path / 'web' / 'out'
        web_out.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_frontend_path()
        assert result == 'web/dist'

        paths._is_source_install = None


class TestGetResourcePath:
    """Test get_resource_path function."""

    def test_returns_original_path_when_not_found(self, tmp_path, monkeypatch):
        """Should return original path when resource not found."""
        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_resource_path('nonexistent/file.txt')
        assert result == 'nonexistent/file.txt'

        paths._is_source_install = None

    def test_finds_resource_in_current_directory_source_mode(self, tmp_path, monkeypatch):
        """Should find resource in current directory when in source mode."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n')

        resource_file = tmp_path / 'templates' / 'config.yaml'
        resource_file.parent.mkdir(parents=True, exist_ok=True)
        resource_file.write_text('test: value')

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_resource_path('templates/config.yaml')
        assert os.path.exists(result)

        paths._is_source_install = None

    def test_returns_relative_path_in_source_mode(self, tmp_path, monkeypatch):
        """Should return relative path if resource exists in source mode."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n')

        resource_file = tmp_path / 'test_resource.txt'
        resource_file.write_text('test content')

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        result = paths.get_resource_path('test_resource.txt')
        assert result == 'test_resource.txt'

        paths._is_source_install = None


class TestPathFunctionsCaching:
    """Test that path functions use caching correctly."""

    def test_source_install_cache_is_used(self, tmp_path, monkeypatch):
        """_check_if_source_install should use cached result."""
        main_py = tmp_path / 'main.py'
        main_py.write_text('# LangBot/main.py\n')

        monkeypatch.chdir(tmp_path)

        from langbot.pkg.utils import paths

        paths._is_source_install = None

        # First call sets cache
        result1 = paths._check_if_source_install()
        assert result1 is True
        assert paths._is_source_install is True

        # Second call uses cache (no file read needed)
        result2 = paths._check_if_source_install()
        assert result2 is True

        paths._is_source_install = None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
