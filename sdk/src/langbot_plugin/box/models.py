from __future__ import annotations

import datetime as dt
import enum
import ntpath
import posixpath
from typing import Literal

import pydantic


DEFAULT_BOX_IMAGE = "rockchin/langbot-sandbox:latest"
DEFAULT_BOX_MOUNT_PATH = "/workspace"
_UTC = dt.timezone.utc


class BoxNetworkMode(str, enum.Enum):
    OFF = "off"
    ON = "on"


class BoxExecutionStatus(str, enum.Enum):
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"


class BoxHostMountMode(str, enum.Enum):
    NONE = "none"
    READ_ONLY = "ro"
    READ_WRITE = "rw"


class BoxManagedProcessStatus(str, enum.Enum):
    RUNNING = "running"
    EXITED = "exited"


class SandboxAdmissionGrant(pydantic.BaseModel):
    """Short-lived authority for one Workspace managed sandbox.

    The authenticated LangBot host is the only party allowed to install this
    grant.  The Box Runtime deliberately understands numeric capabilities,
    not product plan names.
    """

    instance_uuid: str
    workspace_uuid: str
    execution_generation: int
    entitlement_revision: int
    expires_at: dt.datetime
    max_sessions: int
    max_managed_processes: int

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("instance_uuid", "workspace_uuid")
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @pydantic.field_validator(
        "execution_generation",
        "entitlement_revision",
        "max_sessions",
        "max_managed_processes",
        mode="before",
    )
    @classmethod
    def reject_boolean_integer(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be an integer")
        return value

    @pydantic.field_validator("execution_generation", "entitlement_revision")
    @classmethod
    def validate_positive_revision(cls, value: int) -> int:
        if value < 1:
            raise ValueError("must be greater than or equal to 1")
        return value

    @pydantic.field_validator("max_sessions", "max_managed_processes")
    @classmethod
    def validate_non_negative_limit(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be greater than or equal to 0")
        return value

    @pydantic.field_validator("expires_at")
    @classmethod
    def validate_aware_expiry(cls, value: dt.datetime) -> dt.datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value.astimezone(_UTC)

    @property
    def workspace_key(self) -> tuple[str, str]:
        return self.instance_uuid, self.workspace_uuid

    def is_expired(self, now: dt.datetime | None = None) -> bool:
        current = now or dt.datetime.now(_UTC)
        return self.expires_at <= current.astimezone(_UTC)


class SandboxAdmissionRevocation(pydantic.BaseModel):
    """Monotonic tombstone that invalidates a Workspace admission grant."""

    instance_uuid: str
    workspace_uuid: str
    entitlement_revision: int

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("instance_uuid", "workspace_uuid")
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @pydantic.field_validator("entitlement_revision", mode="before")
    @classmethod
    def reject_boolean_revision(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("entitlement_revision must be an integer")
        return value

    @pydantic.field_validator("entitlement_revision")
    @classmethod
    def validate_positive_revision(cls, value: int) -> int:
        if value < 1:
            raise ValueError("entitlement_revision must be greater than or equal to 1")
        return value

    @property
    def workspace_key(self) -> tuple[str, str]:
        return self.instance_uuid, self.workspace_uuid


class SandboxAdmissionPolicy(pydantic.BaseModel):
    """Instance-owned hard policy for grant-enforced sandbox execution.

    This policy is supplied by deployment configuration and caps every grant.
    It contains no subscription or edition vocabulary.
    """

    required: bool = False
    logical_session_id: Literal["global"] = "global"
    required_backend: Literal["nsjail"] = "nsjail"
    max_sessions: int = 1
    max_managed_processes: int = 0
    max_grant_ttl_sec: int = 300
    max_timeout_sec: int = 120
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True
    workspace_quota_mb: int = 0
    readiness_cache_sec: int = 15

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator(
        "max_sessions",
        "max_managed_processes",
        "max_grant_ttl_sec",
        "max_timeout_sec",
        "memory_mb",
        "pids_limit",
        "workspace_quota_mb",
        "readiness_cache_sec",
        mode="before",
    )
    @classmethod
    def reject_boolean_integer(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be an integer")
        return value

    @pydantic.field_validator("cpus", mode="before")
    @classmethod
    def reject_boolean_cpu(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("cpus must be a number")
        return value

    @pydantic.field_validator("max_sessions")
    @classmethod
    def validate_session_cap(cls, value: int) -> int:
        if value < 0 or value > 1:
            raise ValueError("max_sessions must be between 0 and 1")
        return value

    @pydantic.field_validator("max_managed_processes")
    @classmethod
    def validate_managed_process_cap(cls, value: int) -> int:
        if value != 0:
            raise ValueError("max_managed_processes must be 0")
        return value

    @pydantic.field_validator("max_grant_ttl_sec", "max_timeout_sec", "pids_limit")
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @pydantic.field_validator("memory_mb")
    @classmethod
    def validate_memory_limit(cls, value: int) -> int:
        if value < 32:
            raise ValueError("memory_mb must be at least 32")
        return value

    @pydantic.field_validator("workspace_quota_mb", "readiness_cache_sec")
    @classmethod
    def validate_non_negative_integer(cls, value: int) -> int:
        if value < 0:
            raise ValueError("must be greater than or equal to 0")
        return value

    @pydantic.field_validator("cpus")
    @classmethod
    def validate_positive_cpu(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("cpus must be greater than 0")
        return value


ARTIFACT_MOUNT_ROOT = "/opt/langbot-artifacts"


class BoxMountSpec(pydantic.BaseModel):
    """A generic additional bind mount specification."""

    host_path: str
    mount_path: str
    mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    content_digest: str | None = None
    manifest_path: str | None = None

    @pydantic.field_validator("host_path")
    @classmethod
    def validate_host_path(cls, value: str) -> str:
        value = value.strip()
        if not (posixpath.isabs(value) or ntpath.isabs(value)):
            raise ValueError("host_path must be an absolute host path")
        return value

    @pydantic.field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("mount_path must be an absolute path inside the sandbox")
        if posixpath.normpath(value) != value:
            raise ValueError("mount_path must be normalized")
        return value

    @pydantic.field_validator("content_digest")
    @classmethod
    def validate_content_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value.startswith("sha256:"):
            raise ValueError("content_digest must use sha256:<hex>")
        digest = value[len("sha256:") :]
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise ValueError("content_digest must use sha256:<64 lowercase hex>")
        return value

    @pydantic.field_validator("manifest_path")
    @classmethod
    def validate_manifest_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not (posixpath.isabs(value) or ntpath.isabs(value)):
            raise ValueError("manifest_path must be an absolute host path")
        return value

    @property
    def is_content_addressed(self) -> bool:
        return bool(
            self.mode == BoxHostMountMode.READ_ONLY
            and self.content_digest
            and self.manifest_path
            and self.mount_path == f"{ARTIFACT_MOUNT_ROOT}/{self.content_digest[7:]}"
        )

    @pydantic.model_validator(mode="after")
    def validate_artifact_path(self):
        if (
            self.mount_path == ARTIFACT_MOUNT_ROOT
            or self.mount_path.startswith(ARTIFACT_MOUNT_ROOT + "/")
        ) and not self.is_content_addressed:
            raise ValueError(
                "Artifact paths require a read-only digest-addressed mount and manifest"
            )
        return self


class BoxSpec(pydantic.BaseModel):
    cmd: str = ""
    workdir: str = DEFAULT_BOX_MOUNT_PATH
    timeout_sec: int = 30
    network: BoxNetworkMode = BoxNetworkMode.OFF
    session_id: str
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    image: str = DEFAULT_BOX_IMAGE
    host_path: str | None = None
    host_path_mode: BoxHostMountMode = BoxHostMountMode.READ_WRITE
    mount_path: str = DEFAULT_BOX_MOUNT_PATH
    extra_mounts: list[BoxMountSpec] = pydantic.Field(default_factory=list)
    persistent: bool = False
    # Resource limits
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True
    workspace_quota_mb: int = 0

    model_config = pydantic.ConfigDict(extra="forbid")

    @pydantic.model_validator(mode="before")
    @classmethod
    def populate_workdir_from_mount_path(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("workdir") not in (None, ""):
            return data
        mount_path = data.get("mount_path")
        if isinstance(mount_path, str) and mount_path.strip():
            data = dict(data)
            data["workdir"] = mount_path
        return data

    @pydantic.field_validator("cmd")
    @classmethod
    def validate_cmd(cls, value: str) -> str:
        return value.strip()

    @pydantic.field_validator("workdir")
    @classmethod
    def validate_workdir(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("workdir must be an absolute path inside the sandbox")
        return value

    @pydantic.field_validator("timeout_sec")
    @classmethod
    def validate_timeout_sec(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeout_sec must be greater than 0")
        return value

    @pydantic.field_validator("cpus")
    @classmethod
    def validate_cpus(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("cpus must be greater than 0")
        return value

    @pydantic.field_validator("memory_mb")
    @classmethod
    def validate_memory_mb(cls, value: int) -> int:
        if value < 32:
            raise ValueError("memory_mb must be at least 32")
        return value

    @pydantic.field_validator("pids_limit")
    @classmethod
    def validate_pids_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("pids_limit must be at least 1")
        return value

    @pydantic.field_validator("workspace_quota_mb")
    @classmethod
    def validate_workspace_quota_mb(cls, value: int) -> int:
        if value < 0:
            raise ValueError("workspace_quota_mb must be greater than or equal to 0")
        return value

    @pydantic.field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("session_id must not be empty")
        return value

    @pydantic.field_validator("env")
    @classmethod
    def validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(k): str(v) for k, v in value.items()}

    @pydantic.field_validator("host_path")
    @classmethod
    def validate_host_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not (posixpath.isabs(value) or ntpath.isabs(value)):
            raise ValueError("host_path must be an absolute host path")
        return value

    @pydantic.field_validator("mount_path")
    @classmethod
    def validate_mount_path(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("mount_path must be an absolute path inside the sandbox")
        return value

    @pydantic.model_validator(mode="after")
    def validate_host_mount_consistency(self) -> "BoxSpec":
        if self.host_path is None:
            return self
        if self.host_path_mode == BoxHostMountMode.NONE:
            return self
        if self.workdir != self.mount_path and not self.workdir.startswith(
            f"{self.mount_path}/"
        ):
            raise ValueError(
                "workdir must stay under mount_path when host_path is provided"
            )
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
    workspace_quota_mb: int = 0
    locked: frozenset[str] = frozenset()

    model_config = pydantic.ConfigDict(frozen=True)


BUILTIN_PROFILES: dict[str, BoxProfile] = {
    "default": BoxProfile(
        name="default",
        network=BoxNetworkMode.ON,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
        read_only_rootfs=True,
        max_timeout_sec=120,
    ),
    "offline": BoxProfile(
        name="offline",
        network=BoxNetworkMode.OFF,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
        read_only_rootfs=True,
        max_timeout_sec=120,
    ),
    "offline_readonly": BoxProfile(
        name="offline_readonly",
        network=BoxNetworkMode.OFF,
        host_path_mode=BoxHostMountMode.READ_ONLY,
        cpus=0.5,
        memory_mb=256,
        pids_limit=64,
        read_only_rootfs=True,
        max_timeout_sec=60,
        locked=frozenset({"network", "host_path_mode", "read_only_rootfs"}),
    ),
    "network_basic": BoxProfile(
        name="network_basic",
        network=BoxNetworkMode.ON,
        host_path_mode=BoxHostMountMode.READ_WRITE,
        cpus=1.0,
        memory_mb=512,
        pids_limit=128,
        read_only_rootfs=True,
        max_timeout_sec=120,
    ),
    "network_extended": BoxProfile(
        name="network_extended",
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
    mount_path: str = DEFAULT_BOX_MOUNT_PATH
    persistent: bool = False
    cpus: float = 1.0
    memory_mb: int = 512
    pids_limit: int = 128
    read_only_rootfs: bool = True
    workspace_quota_mb: int = 0
    created_at: dt.datetime
    last_used_at: dt.datetime


class BoxManagedProcessSpec(pydantic.BaseModel):
    process_id: str = "default"
    command: str
    args: list[str] = pydantic.Field(default_factory=list)
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    cwd: str = DEFAULT_BOX_MOUNT_PATH
    # Per-process memory override in MB. 0 = inherit from session default.
    memory_mb: int = 0

    @pydantic.field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("command must not be empty")
        return value

    @pydantic.field_validator("args")
    @classmethod
    def validate_args(cls, value: list[str]) -> list[str]:
        return [str(item) for item in value]

    @pydantic.field_validator("env")
    @classmethod
    def validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(k): str(v) for k, v in value.items()}

    @pydantic.field_validator("cwd")
    @classmethod
    def validate_cwd(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("cwd must be an absolute path inside the sandbox")
        return value


class BoxManagedProcessInfo(pydantic.BaseModel):
    session_id: str
    process_id: str = "default"
    status: BoxManagedProcessStatus
    command: str
    args: list[str]
    cwd: str
    env_keys: list[str]
    attached: bool = False
    started_at: dt.datetime
    exited_at: dt.datetime | None = None
    exit_code: int | None = None
    stderr_preview: str = ""


class BoxExecutionResult(pydantic.BaseModel):
    session_id: str
    backend_name: str
    status: BoxExecutionStatus
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.status == BoxExecutionStatus.COMPLETED and self.exit_code == 0
