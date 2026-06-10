"""
Tests for langbot.pkg.utils.importutil module.

Tests import utility functions:
- import_dir: imports modules from a directory
- import_modules_in_pkg: imports all modules in a package
- import_modules_in_pkgs: imports all modules in multiple packages
- import_dot_style_dir: imports modules using dot notation path
- read_resource_file: reads a text resource file
- read_resource_file_bytes: reads a binary resource file
- list_resource_files: lists files in a resource directory

Uses mocking for import operations to avoid actual module imports.
"""

import pytest
import importlib
from unittest.mock import patch, MagicMock


class TestImportDir:
    """Test import_dir function."""

    def test_calls_importlib_for_each_python_file(self, tmp_path):
        """Should call importlib.import_module for each .py file."""
        module_dir = tmp_path / "test_modules"
        module_dir.mkdir()

        (module_dir / "__init__.py").write_text("")
        (module_dir / "module_a.py").write_text("VALUE_A = 'a'\n")
        (module_dir / "module_b.py").write_text("VALUE_B = 'b'\n")
        (module_dir / "readme.txt").write_text("not a module")

        from langbot.pkg.utils import importutil

        with patch.object(importlib, "import_module") as mock_import:
            importutil.import_dir(str(module_dir), path_prefix="test_prefix.")
            # Should call import_module for each .py file (excluding __init__.py)
            assert mock_import.call_count == 2

    def test_skips_init_py(self, tmp_path):
        """Should skip __init__.py when importing."""
        module_dir = tmp_path / "test_modules"
        module_dir.mkdir()

        (module_dir / "__init__.py").write_text("")
        (module_dir / "regular.py").write_text("VALUE = 1\n")

        from langbot.pkg.utils import importutil

        with patch.object(importlib, "import_module") as mock_import:
            importutil.import_dir(str(module_dir), path_prefix="test_prefix.")
            # __init__.py should be skipped
            mock_import.assert_called_once()
            # The call should not include __init__
            call_args = mock_import.call_args[0][0]
            assert "__init__" not in call_args

    def test_ignores_non_py_files(self, tmp_path):
        """Should ignore non-.py files."""
        module_dir = tmp_path / "test_modules"
        module_dir.mkdir()

        (module_dir / "module.py").write_text("VALUE = 1\n")
        (module_dir / "readme.txt").write_text("text")
        (module_dir / "data.json").write_text("{}")

        from langbot.pkg.utils import importutil

        with patch.object(importlib, "import_module") as mock_import:
            importutil.import_dir(str(module_dir), path_prefix="test_prefix.")
            # Only .py files should be imported
            assert mock_import.call_count == 1


class TestImportModulesInPkg:
    """Test import_modules_in_pkg function."""

    def test_imports_modules_from_package(self, tmp_path):
        """Should import all modules from a package object."""
        mock_pkg = MagicMock()
        mock_pkg.__file__ = str(tmp_path / "__init__.py")

        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "mod1.py").write_text("MOD1 = 1\n")

        from langbot.pkg.utils import importutil

        with patch.object(importutil, "import_dir") as mock_import_dir:
            importutil.import_modules_in_pkg(mock_pkg)
            mock_import_dir.assert_called_once()
            call_path = mock_import_dir.call_args[0][0]
            assert call_path == str(tmp_path)


class TestImportModulesInPkgs:
    """Test import_modules_in_pkgs function."""

    def test_imports_from_multiple_packages(self):
        """Should call import_modules_in_pkg for each package."""
        from langbot.pkg.utils import importutil

        mock_pkg1 = MagicMock()
        mock_pkg1.__file__ = "/path/to/pkg1/__init__.py"
        mock_pkg2 = MagicMock()
        mock_pkg2.__file__ = "/path/to/pkg2/__init__.py"

        with patch.object(importutil, "import_modules_in_pkg") as mock_import:
            importutil.import_modules_in_pkgs([mock_pkg1, mock_pkg2])
            assert mock_import.call_count == 2


class TestImportDotStyleDir:
    """Test import_dot_style_dir function."""

    def test_converts_dot_notation_to_path(self, tmp_path):
        """Should convert dot notation to path and import."""
        # Create structure matching the dot notation
        (tmp_path / "my").mkdir()
        (tmp_path / "my" / "pkg").mkdir()
        (tmp_path / "my" / "pkg" / "test").mkdir()

        from langbot.pkg.utils import importutil

        with patch.object(importutil, "import_dir") as mock_import_dir:
            importutil.import_dot_style_dir("my.pkg.test")
            # The path should be converted using os.path.join
            call_path = mock_import_dir.call_args[0][0]
            # Should contain the path components joined
            assert "my" in call_path


class TestReadResourceFile:
    """Test read_resource_file function."""

    def test_reads_resource_file_content(self):
        """Should read content from a resource file."""
        from langbot.pkg.utils import importutil

        content = importutil.read_resource_file("templates/config.yaml")
        assert "admins:" in content
        assert "edition: community" in content

    def test_raises_for_nonexistent_file(self):
        """Should raise exception for non-existent resource file."""
        from langbot.pkg.utils import importutil

        with pytest.raises((FileNotFoundError, Exception)):
            importutil.read_resource_file("nonexistent/path/file.txt")


class TestReadResourceFileBytes:
    """Test read_resource_file_bytes function."""

    def test_reads_resource_file_as_bytes(self):
        """Should read content as bytes from a resource file."""
        from langbot.pkg.utils import importutil

        content = importutil.read_resource_file_bytes("templates/config.yaml")
        assert b"admins:" in content
        assert b"edition: community" in content

    def test_raises_for_nonexistent_file_bytes(self):
        """Should raise exception for non-existent resource file."""
        from langbot.pkg.utils import importutil

        with pytest.raises((FileNotFoundError, Exception)):
            importutil.read_resource_file_bytes("nonexistent/path/file.txt")


class TestListResourceFiles:
    """Test list_resource_files function."""

    def test_lists_files_in_resource_directory(self):
        """Should list files in a resource directory."""
        from langbot.pkg.utils import importutil

        files = importutil.list_resource_files("templates")
        assert "config.yaml" in files
        assert "default-pipeline-config.json" in files
        assert all(isinstance(file, str) for file in files)

    def test_raises_for_nonexistent_directory(self):
        """Should raise exception for non-existent directory."""
        from langbot.pkg.utils import importutil

        with pytest.raises((FileNotFoundError, Exception)):
            importutil.list_resource_files("nonexistent_directory_xyz")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
