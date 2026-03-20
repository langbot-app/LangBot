from __future__ import annotations

import datetime as dt
import enum

import pydantic


DEFAULT_BOX_IMAGE = 'python:3.11-slim'
DEFAULT_BOX_MOUNT_PATH = '/workspace'


def get_box_config(ap) -> dict:
    """Return the 'box' section from instance config, with safe fallbacks."""
    instance_config = getattr(ap, 'instance_config', None)
    config_data = getattr(instance_config, 'data', {}) if instance_config is not None else {}
    return config_data.get('box', {})


class BoxNetworkMode(str, enum.Enum):
    OFF = 'off'
    ON = 'on'


class BoxExecutionStatus(str, enum.Enum):
    COMPLETED = 'completed'
    TIMED_OUT = 'timed_out'


class BoxHostMountMode(str, enum.Enum):
    READ_ONLY = 'ro'
    READ_WRITE = 'rw'


class BoxSpec(pydantic.BaseModel):
    cmd: str = ''
    workdir: str = '/workspace'
    timeout_sec: int = 30
    network: BoxNetworkMode = BoxNetworkMode.OFF
    session_id: str
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    image: str = DEFAULT_BOX_IMAGE
    host_path: str | None = None
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    # Resource limits
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True

    @pydantic.field_validator('cmd')
    @classmethod
    def validate_cmd(cls, value: str) -> str:
        return value.strip()

    @pydantic.field_validator('workdir')
    @classmethod
    def validate_workdir(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith('/'):
            raise ValueError('workdir must be an absolute path inside the sandbox')
        return value

    @pydantic.field_validator('timeout_sec')
    @classmethod
    def validate_timeout_sec(cls, value: int) -> int:
        if value <= 0:
            raise ValueError('timeout_sec must be greater than 0')
        return value

    @pydantic.field_validator('cpus')
    @classmethod
    def validate_cpus(cls, value: float) -> float:
        if value <= 0:
            raise ValueError('cpus must be greater than 0')
        return value

    @pydantic.field_validator('memory_mb')
    @classmethod
    def validate_memory_mb(cls, value: int) -> int:
        if value < 32:
            raise ValueError('memory_mb must be at least 32')
        return value

    @pydantic.field_validator('pids_limit')
    @classmethod
    def validate_pids_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError('pids_limit must be at least 1')
        return value

    @pydantic.field_validator('session_id')
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('session_id must not be empty')
        return value

    @pydantic.field_validator('env')
    @classmethod
    def validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(k): str(v) for k, v in value.items()}

    @pydantic.field_validator('host_path')
    @classmethod
    def validate_host_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value.startswith('/'):
            raise ValueError('host_path must be an absolute host path')
        return value

    @pydantic.model_validator(mode='after')
    def validate_host_mount_consistency(self) -> 'BoxSpec':
        if self.host_path is None:
            return self
        if not self.workdir.startswith(DEFAULT_BOX_MOUNT_PATH):
            raise ValueError('workdir must stay under /workspace when host_path is provided')
        return self


class BoxProfile(pydantic.BaseModel):
    """Preset sandbox configuration.

    Provides default values for BoxSpec fields and optionally locks fields
    so that tool-call parameters cannot override them.
    """

    name: str
    image: str = DEFAULT_BOX_IMAGE
    network: BoxNetworkMode = BoxNetworkMode.OFF
    timeout_sec: int = 30
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    max_timeout_sec: int = 120
    # Resource limits
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True
    locked: frozenset[str] = frozenset()

    model_config = pydantic.ConfigDict(frozen=True)


BUILTIN_PROFILES: dict[str, BoxProfile] = {
    'default': BoxProfile(
        name='default',
        network=BoxNetworkMode.OFF,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
        read_only_rootfs=True,
        max_timeout_sec=120,
    ),
    'offline_readonly': BoxProfile(
        name='offline_readonly',
        network=BoxNetworkMode.OFF,
        host_path_mode=BoxHostMountMode.READ_ONLY,
        cpus=0.5,
        memory_mb=256,
        pids_limit=64,
        read_only_rootfs=True,
        max_timeout_sec=60,
        locked=frozenset({'network', 'host_path_mode', 'read_only_rootfs'}),
    ),
    'network_basic': BoxProfile(
        name='network_basic',
        network=BoxNetworkMode.ON,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
        read_only_rootfs=True,
        max_timeout_sec=120,
    ),
    'network_extended': BoxProfile(
        name='network_extended',
        network=BoxNetworkMode.ON,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=2.0,
        memory_mb=1024,
        pids_limit=256,
        read_only_rootfs=False,
        max_timeout_sec=300,
    ),
}


class BoxSessionInfo(pydantic.BaseModel):
    session_id: str
    backend_name: str
    backend_session_id: str
    image: str
    network: BoxNetworkMode
    host_path: str | None = None
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True
    created_at: dt.datetime
    last_used_at: dt.datetime


class BoxExecutionResult(pydantic.BaseModel):
    session_id: str
    backend_name: str
    status: BoxExecutionStatus
    exit_code: int | None
    stdout: str = ''
    stderr: str = ''
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.status == BoxExecutionStatus.COMPLETED and self.exit_code == 0
