from __future__ import annotations

import os
import re
import sys

from .errors import BoxValidationError
from .models import BoxSpec


BOX_CONTROL_TOKEN_ENV = "LANGBOT_BOX_CONTROL_TOKEN"
BOX_TRUSTED_INSTANCE_ENV = "LANGBOT_BOX_TRUSTED_INSTANCE_UUID"
BOX_CONTROL_TOKEN_HEADER = "X-LangBot-Box-Control-Token"
BOX_INSTANCE_HEADER = "X-LangBot-Instance-Id"
BOX_WORKSPACE_HEADER = "X-LangBot-Workspace-Id"
BOX_PLACEMENT_GENERATION_HEADER = "X-LangBot-Placement-Generation"
BOX_SHARED_WORKSPACE_PROBE_PREFIX = ".langbot-box-volume-probe-"
CONTROL_TOKEN_MIN_LENGTH = 32

_INSTANCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHARED_WORKSPACE_PROBE_PATTERN = re.compile(
    rf"^{re.escape(BOX_SHARED_WORKSPACE_PROBE_PREFIX)}[a-f0-9]{{32}}$"
)

_BLOCKED_HOST_PATHS_POSIX = frozenset(
    {
        "/etc",
        "/proc",
        "/sys",
        "/dev",
        "/root",
        "/boot",
        "/run",
        "/var/run",
        "/run/docker.sock",
        "/var/run/docker.sock",
    }
)

_BLOCKED_HOST_PATHS_WINDOWS = frozenset(
    {
        r"C:\Windows",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
        r"C:\ProgramData",
        r"\\.\pipe\docker_engine",
    }
)

BLOCKED_HOST_PATHS = (
    _BLOCKED_HOST_PATHS_POSIX | _BLOCKED_HOST_PATHS_WINDOWS
    if sys.platform == "win32"
    else _BLOCKED_HOST_PATHS_POSIX
)


def normalize_instance_uuid(value: str) -> str:
    normalized = str(value or "").strip()
    if not _INSTANCE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("A valid trusted LangBot instance UUID is required")
    return normalized


def validate_control_token(value: str) -> str:
    token = str(value or "").strip()
    if len(token) < CONTROL_TOKEN_MIN_LENGTH or any(
        character.isspace() for character in token
    ):
        raise ValueError(
            f"{BOX_CONTROL_TOKEN_ENV} must be a non-whitespace secret of at least "
            f"{CONTROL_TOKEN_MIN_LENGTH} characters"
        )
    return token


def validate_shared_workspace_probe_name(value: str) -> str:
    """Validate the opaque basename used for one shared-volume challenge.

    The Box Runtime never accepts a path for this host-control operation.  A
    fixed prefix and a high-entropy lowercase hex suffix keep the one allowed
    filename shape narrow enough to use safely with ``openat``/``O_NOFOLLOW``.
    """

    name = str(value or "").strip()
    if not _SHARED_WORKSPACE_PROBE_PATTERN.fullmatch(name):
        raise ValueError("Invalid Box shared Workspace probe basename")
    return name


def _validate_host_path(host_path: str, field_name: str) -> None:
    real = os.path.realpath(host_path)
    sep = os.sep
    _norm = os.path.normcase
    for blocked in BLOCKED_HOST_PATHS:
        if _norm(real) == _norm(blocked) or _norm(real).startswith(
            _norm(blocked) + sep
        ):
            raise BoxValidationError(
                f"{field_name} {host_path} is blocked for security"
            )


def validate_sandbox_security(spec: BoxSpec) -> None:
    """Reject BoxSpec host mounts into blocked paths."""
    if spec.host_path:
        _validate_host_path(spec.host_path, "host_path")

    for mount in spec.extra_mounts:
        _validate_host_path(mount.host_path, "extra_mounts.host_path")
