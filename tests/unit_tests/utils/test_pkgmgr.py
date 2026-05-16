"""
Unit tests for package manager utilities.

Tests pip command generation without actual installation.
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

from langbot.pkg.utils import pkgmgr


class TestPkgMgr:
    """Tests for package manager functions."""

    def test_install_calls_pipmain(self):
        """install calls pipmain with correct arguments."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install('requests')

            mock_pipmain.assert_called_once_with(['install', 'requests'])

    def test_install_with_version(self):
        """install handles package with version specifier."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install('requests>=2.0.0')

            mock_pipmain.assert_called_once_with(['install', 'requests>=2.0.0'])

    def test_install_upgrade_calls_pipmain(self):
        """install_upgrade calls pipmain with upgrade and mirror."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install_upgrade('requests')

            expected_args = [
                'install',
                '--upgrade',
                'requests',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
            ]
            mock_pipmain.assert_called_once_with(expected_args)

    def test_run_pip_with_params(self):
        """run_pip passes params to pipmain."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.run_pip(['list', '--outdated'])

            mock_pipmain.assert_called_once_with(['list', '--outdated'])

    def test_run_pip_empty_params(self):
        """run_pip handles empty params."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.run_pip([])

            mock_pipmain.assert_called_once_with([])

    def test_install_requirements_calls_pipmain(self):
        """install_requirements calls pipmain with requirements file."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install_requirements('requirements.txt')

            expected_args = [
                'install',
                '-r',
                'requirements.txt',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
            ]
            mock_pipmain.assert_called_once_with(expected_args)

    def test_install_requirements_defaults_extra_params_to_none(self):
        """install_requirements should not use a mutable default for extra_params."""
        signature = inspect.signature(pkgmgr.install_requirements)

        assert signature.parameters['extra_params'].default is None

    def test_install_requirements_omitted_extra_params_uses_independent_base_commands(self, monkeypatch):
        """Omitted extra_params should not share mutable state across calls."""
        calls = []
        monkeypatch.setattr(pkgmgr, 'pipmain', calls.append)

        pkgmgr.install_requirements('requirements.txt')
        pkgmgr.install_requirements('requirements-dev.txt')

        assert calls == [
            [
                'install',
                '-r',
                'requirements.txt',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
            ],
            [
                'install',
                '-r',
                'requirements-dev.txt',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
            ],
        ]

    def test_install_requirements_preserves_explicit_extra_params(self, monkeypatch):
        """Explicit extra_params should be appended to the generated pip command."""
        calls = []
        monkeypatch.setattr(pkgmgr, 'pipmain', calls.append)

        pkgmgr.install_requirements('requirements.txt', extra_params=['--no-deps'])

        assert calls == [
            [
                'install',
                '-r',
                'requirements.txt',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
                '--no-deps',
            ]
        ]

    def test_install_requirements_with_extra_params(self):
        """install_requirements handles extra params."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install_requirements('requirements.txt', ['--no-cache-dir'])

            expected_args = [
                'install',
                '-r',
                'requirements.txt',
                '-i',
                'https://pypi.tuna.tsinghua.edu.cn/simple',
                '--trusted-host',
                'pypi.tuna.tsinghua.edu.cn',
                '--no-cache-dir',
            ]
            mock_pipmain.assert_called_once_with(expected_args)

    def test_install_requirements_multiple_extra_params(self):
        """install_requirements handles multiple extra params."""
        with patch('langbot.pkg.utils.pkgmgr.pipmain') as mock_pipmain:
            pkgmgr.install_requirements('requirements.txt', ['--no-cache-dir', '--verbose'])

            call_args = mock_pipmain.call_args[0][0]
            assert '--no-cache-dir' in call_args
            assert '--verbose' in call_args
