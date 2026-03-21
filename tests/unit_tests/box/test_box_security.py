from __future__ import annotations

import pytest

from langbot.pkg.box.errors import BoxValidationError
from langbot.pkg.box.models import BoxHostMountMode, BoxNetworkMode, BoxSpec
from langbot.pkg.box.security import BLOCKED_HOST_PATHS, validate_sandbox_security


def _make_spec(**overrides) -> BoxSpec:
    defaults = {
        'session_id': 'test-session',
        'cmd': 'echo hi',
        'image': 'python:3.11-slim',
    }
    defaults.update(overrides)
    return BoxSpec(**defaults)


class TestValidateSandboxSecurity:
    def test_no_host_path_passes(self):
        spec = _make_spec(host_path=None)
        validate_sandbox_security(spec)  # should not raise

    def test_safe_host_path_passes(self):
        spec = _make_spec(host_path='/home/user/my-project')
        validate_sandbox_security(spec)  # should not raise

    @pytest.mark.parametrize('blocked', [
        '/etc',
        '/proc',
        '/sys',
        '/dev',
        '/root',
        '/boot',
        '/run',
        '/var/run',
        '/run/docker.sock',
        '/var/run/docker.sock',
        '/run/podman',
        '/var/run/podman',
    ])
    def test_blocked_paths_rejected(self, blocked):
        spec = _make_spec(host_path=blocked)
        with pytest.raises(BoxValidationError, match='blocked for security'):
            validate_sandbox_security(spec)

    def test_blocked_subpath_rejected(self):
        spec = _make_spec(host_path='/etc/nginx')
        with pytest.raises(BoxValidationError, match='blocked for security'):
            validate_sandbox_security(spec)

    def test_path_starting_with_blocked_prefix_but_different_dir_passes(self):
        # /etcetera is NOT /etc
        spec = _make_spec(host_path='/etcetera/data')
        validate_sandbox_security(spec)  # should not raise

    def test_blocked_host_paths_is_frozenset(self):
        assert isinstance(BLOCKED_HOST_PATHS, frozenset)
