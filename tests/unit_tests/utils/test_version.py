"""
Unit tests for version utility functions.

Tests version comparison logic without network calls.
"""

from __future__ import annotations

from unittest.mock import Mock

from langbot.pkg.utils.version import VersionManager


class TestVersionComparison:
    """Tests for version comparison functions."""

    def _create_version_manager(self):
        """Create a VersionManager with mock app."""
        mock_app = Mock()
        mock_app.proxy_mgr = Mock()
        mock_app.proxy_mgr.get_forward_providers = Mock(return_value={})
        mock_app.logger = Mock()
        return VersionManager(mock_app)

    def test_is_newer_same_version(self):
        """is_newer returns False for same version."""
        vm = self._create_version_manager()
        result = vm.is_newer('v1.0.0', 'v1.0.0')
        assert result is False

    def test_is_newer_different_major_version(self):
        """is_newer returns False for different major version."""
        # Note: is_newer ignores major version changes
        vm = self._create_version_manager()
        result = vm.is_newer('v2.0.0', 'v1.0.0')
        assert result is False

    def test_is_newer_minor_update(self):
        """is_newer returns True for minor update within same major."""
        vm = self._create_version_manager()
        result = vm.is_newer('v1.1.0', 'v1.0.0')
        assert result is True

    def test_is_newer_patch_update(self):
        """is_newer returns True for patch update within same major."""
        vm = self._create_version_manager()
        result = vm.is_newer('v1.0.1', 'v1.0.0')
        assert result is True

    def test_is_newer_with_fourth_segment(self):
        """is_newer ignores fourth version segment."""
        # Both have same first 3 segments
        vm = self._create_version_manager()
        result = vm.is_newer('v1.0.0.1', 'v1.0.0.0')
        assert result is False

    def test_is_newer_short_version(self):
        """is_newer handles short version numbers."""
        vm = self._create_version_manager()
        result = vm.is_newer('v1.0', 'v1.0')
        assert result is False

    def test_is_newer_older_version(self):
        """is_newer returns True when new > old."""
        vm = self._create_version_manager()
        result = vm.is_newer('v1.2.0', 'v1.1.0')
        assert result is True


class TestCompareVersionStr:
    """Tests for compare_version_str static method."""

    def test_compare_equal_versions(self):
        """Equal versions return 0."""
        result = VersionManager.compare_version_str('v1.0.0', 'v1.0.0')
        assert result == 0

    def test_compare_without_v_prefix(self):
        """Versions without v prefix work the same."""
        result = VersionManager.compare_version_str('1.0.0', '1.0.0')
        assert result == 0

    def test_compare_mixed_prefix(self):
        """Mixed v prefix works correctly."""
        result = VersionManager.compare_version_str('v1.0.0', '1.0.0')
        assert result == 0

    def test_compare_first_greater(self):
        """First version greater returns 1."""
        result = VersionManager.compare_version_str('v1.1.0', 'v1.0.0')
        assert result == 1

    def test_compare_first_smaller(self):
        """First version smaller returns -1."""
        result = VersionManager.compare_version_str('v1.0.0', 'v1.1.0')
        assert result == -1

    def test_compare_different_lengths(self):
        """Different length versions are padded with zeros."""
        result = VersionManager.compare_version_str('v1.0', 'v1.0.0')
        assert result == 0

    def test_compare_shorter_greater(self):
        """Shorter version padded, first still greater."""
        result = VersionManager.compare_version_str('v1.1', 'v1.0.0')
        assert result == 1

    def test_compare_longer_greater(self):
        """Longer version, first smaller."""
        result = VersionManager.compare_version_str('v1.0', 'v1.0.1')
        assert result == -1

    def test_compare_major_version(self):
        """Major version comparison."""
        result = VersionManager.compare_version_str('v2.0.0', 'v1.9.9')
        assert result == 1

    def test_compare_minor_version(self):
        """Minor version comparison."""
        result = VersionManager.compare_version_str('v1.5.0', 'v1.4.9')
        assert result == 1

    def test_compare_patch_version(self):
        """Patch version comparison."""
        result = VersionManager.compare_version_str('v1.0.1', 'v1.0.0')
        assert result == 1

    def test_compare_four_segments(self):
        """Four segment version comparison."""
        result = VersionManager.compare_version_str('v1.0.0.1', 'v1.0.0.0')
        assert result == 1

    def test_compare_long_versions(self):
        """Long version strings work correctly."""
        result = VersionManager.compare_version_str('v1.2.3.4.5', 'v1.2.3.4.4')
        assert result == 1
