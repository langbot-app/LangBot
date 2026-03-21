from __future__ import annotations

import os

from .errors import BoxValidationError
from .models import BoxSpec

BLOCKED_HOST_PATHS = frozenset({
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
})

RESERVED_CONTAINER_PATHS = frozenset({
    '/workspace',
    '/tmp',
    '/var/tmp',
    '/run',
})


def validate_sandbox_security(spec: BoxSpec) -> None:
    """Validate that a BoxSpec does not request dangerous container config.

    Raises BoxValidationError when the spec contains a blocked host_path.
    """
    if spec.host_path:
        real = os.path.realpath(spec.host_path)
        for blocked in BLOCKED_HOST_PATHS:
            if real == blocked or real.startswith(blocked + '/'):
                raise BoxValidationError(
                    f'host_path {spec.host_path} is blocked for security'
                )
