"""Tests for core bootutils dependency checking."""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock, patch

from tests.utils.import_isolation import isolated_sys_modules


class TestCheckDeps:
    """Tests for check_deps function."""

    def _make_deps_import_mocks(self):
        """Create mocks for deps import."""
        return {}

    def test_check_deps_all_present(self):
        """check_deps returns empty list when all deps present."""
        mocks = self._make_deps_import_mocks()

        with isolated_sys_modules(mocks):
            # Mock find_spec to always return a spec (module found)
            with patch.object(importlib.util, 'find_spec', return_value=MagicMock()):
                from langbot.pkg.core.bootutils.deps import check_deps

                import asyncio

                result = asyncio.run(check_deps())

                assert result == []

    def test_check_deps_missing_deps(self):
        """check_deps returns list of missing deps."""
        mocks = self._make_deps_import_mocks()

        with isolated_sys_modules(mocks):
            # Mock find_spec to return None for some deps
            def mock_find_spec(name):
                if name in ['requests', 'openai']:
                    return None  # Missing
                return MagicMock()  # Present

            with patch.object(importlib.util, 'find_spec', side_effect=mock_find_spec):
                from langbot.pkg.core.bootutils.deps import check_deps

                import asyncio

                result = asyncio.run(check_deps())

                assert result == ['requests', 'openai']

    def test_check_deps_all_missing(self):
        """check_deps returns all deps when none present."""
        mocks = self._make_deps_import_mocks()

        with isolated_sys_modules(mocks):
            # Mock find_spec to always return None
            with patch.object(importlib.util, 'find_spec', return_value=None):
                from langbot.pkg.core.bootutils.deps import check_deps, required_deps

                import asyncio

                result = asyncio.run(check_deps())

                assert result == list(required_deps)

    def test_required_deps_dict_exists(self):
        """required_deps dictionary is defined."""
        mocks = self._make_deps_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.bootutils.deps import required_deps

            assert isinstance(required_deps, dict)
            assert len(required_deps) > 0
            # Check some expected deps
            assert 'requests' in required_deps
            assert 'yaml' in required_deps

    def test_required_deps_maps_import_name_to_package_name(self):
        """required_deps maps import name to package name."""
        mocks = self._make_deps_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.bootutils.deps import required_deps

            # Some import names differ from package names
            assert required_deps['PIL'] == 'pillow'
            assert required_deps['yaml'] == 'pyyaml'
            assert required_deps['jwt'] == 'pyjwt'


def test_deps_module_does_not_install_packages():
    """Startup must never mutate the environment with pip (LANG-511)."""
    from langbot.pkg.core.bootutils import deps

    assert not hasattr(deps, 'install_deps')
    assert not hasattr(deps, 'precheck_plugin_deps')
    assert not hasattr(deps, 'pip')
