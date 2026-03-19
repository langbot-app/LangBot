from __future__ import annotations

import datetime as dt
import enum

import pydantic


DEFAULT_BOX_IMAGE = 'python:3.11-slim'
DEFAULT_BOX_MOUNT_PATH = '/workspace'


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
    cmd: str
    workdir: str = '/workspace'
    timeout_sec: int = 30
    network: BoxNetworkMode = BoxNetworkMode.OFF
    session_id: str
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    image: str = DEFAULT_BOX_IMAGE
    host_path: str | None = None
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE

    @pydantic.field_validator('cmd')
    @classmethod
    def validate_cmd(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('cmd must not be empty')
        return value

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


class BoxSessionInfo(pydantic.BaseModel):
    session_id: str
    backend_name: str
    backend_session_id: str
    image: str
    network: BoxNetworkMode
    host_path: str | None = None
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
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
