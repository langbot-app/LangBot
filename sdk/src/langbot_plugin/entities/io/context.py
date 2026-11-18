from __future__ import annotations

import json
import math
import re
from enum import Enum
from typing import Literal

import pydantic


_SHA256_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PluginExecutionMode(str, Enum):
    """Process placement selected by the trusted control plane."""

    DEDICATED = "dedicated"
    SHARED_CERTIFIED = "shared-runtime-v1"


class RuntimeIdentity(pydantic.BaseModel):
    """Stable instance scope plus this Runtime process' short-lived identity."""

    instance_uuid: str
    runtime_id: str

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("instance_uuid", "runtime_id")
    @classmethod
    def validate_required_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value


class PluginWorkerResourceOverrides(pydantic.BaseModel):
    """Optional Cloud-only limits; omitted fields inherit the instance policy."""

    max_cpus: float | None = None
    max_memory_mb: int | None = None
    max_pids: int | None = None
    max_open_files: int | None = None
    max_file_size_mb: int | None = None

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("max_cpus", mode="before")
    @classmethod
    def validate_cpu(cls, value):
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("max_cpus must be a positive number")
        if not math.isfinite(value) or value <= 0:
            raise ValueError("max_cpus must be finite and greater than 0")
        return float(value)

    @pydantic.field_validator(
        "max_memory_mb",
        "max_pids",
        "max_open_files",
        "max_file_size_mb",
        mode="before",
    )
    @classmethod
    def validate_integer(cls, value):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            raise ValueError("must be a positive integer")
        return value


class PluginWorkerPolicy(pydantic.BaseModel):
    """Immutable instance policy applied to every isolated plugin worker."""

    max_cpus: float
    max_memory_mb: int
    max_pids: int
    max_open_files: int
    max_file_size_mb: int
    max_workers: int = 16
    max_total_cpus: float = 8.0
    max_total_memory_mb: int = 8192
    max_installations: int = 10_000
    max_pending_registrations: int = 1024
    max_concurrent_restarts: int = 1
    restart_failure_threshold: int = 8
    restart_failure_window_seconds: float = 30.0
    restart_circuit_open_seconds: float = 60.0
    require_hard_limits: bool = False
    dedicated: PluginWorkerResourceOverrides | None = None
    shared: PluginWorkerResourceOverrides | None = None

    def for_execution_mode(
        self, execution_mode: PluginExecutionMode | str, runtime_profile: str
    ) -> PluginWorkerPolicy:
        """Resolve Cloud worker limits without changing legacy OSS policy."""
        if runtime_profile != "shared":
            return self
        mode = PluginExecutionMode(execution_mode)
        override = (
            self.shared
            if mode is PluginExecutionMode.SHARED_CERTIFIED
            else self.dedicated
        )
        if override is None:
            return self
        # Overrides are already validated. Aggregate fields describe legacy OSS
        # admission, not Cloud desired-state worker resource reservations.
        return self.model_copy(update=override.model_dump(exclude_none=True))

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("max_cpus", mode="before")
    @classmethod
    def validate_numeric_cpu_limit(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("max_cpus must be a positive number")
        return value

    @pydantic.field_validator(
        "max_memory_mb",
        "max_pids",
        "max_open_files",
        "max_file_size_mb",
        "max_workers",
        "max_total_memory_mb",
        "max_installations",
        "max_pending_registrations",
        "max_concurrent_restarts",
        "restart_failure_threshold",
        mode="before",
    )
    @classmethod
    def validate_integer_limits(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("must be a positive integer")
        return value

    @pydantic.field_validator("require_hard_limits", mode="before")
    @classmethod
    def validate_require_hard_limits(cls, value):
        if not isinstance(value, bool):
            raise ValueError("require_hard_limits must be a boolean")
        return value

    @pydantic.field_validator(
        "max_cpus",
        "max_total_cpus",
        "restart_failure_window_seconds",
        "restart_circuit_open_seconds",
        mode="before",
    )
    @classmethod
    def validate_numeric_limits(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("must be a positive number")
        return value

    @pydantic.field_validator(
        "max_cpus",
        "max_total_cpus",
        "restart_failure_window_seconds",
        "restart_circuit_open_seconds",
    )
    @classmethod
    def validate_max_cpus(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("must be finite and greater than 0")
        return float(value)

    @pydantic.field_validator(
        "max_memory_mb",
        "max_pids",
        "max_open_files",
        "max_file_size_mb",
        "max_workers",
        "max_total_memory_mb",
        "max_installations",
        "max_pending_registrations",
        "max_concurrent_restarts",
        "restart_failure_threshold",
    )
    @classmethod
    def validate_positive_integer_limit(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value

    @pydantic.model_validator(mode="after")
    def validate_aggregate_limits(self):
        if self.max_total_cpus < self.max_cpus:
            raise ValueError("max_total_cpus cannot be lower than max_cpus")
        if self.max_total_memory_mb < self.max_memory_mb:
            raise ValueError("max_total_memory_mb cannot be lower than max_memory_mb")
        if self.max_installations < self.max_workers:
            raise ValueError("max_installations cannot be lower than max_workers")
        if self.restart_failure_threshold > self.max_installations:
            raise ValueError(
                "restart_failure_threshold cannot exceed max_installations"
            )
        if self.restart_failure_window_seconds > 3600:
            raise ValueError(
                "restart_failure_window_seconds cannot exceed 3600 seconds"
            )
        if self.restart_circuit_open_seconds > 3600:
            raise ValueError("restart_circuit_open_seconds cannot exceed 3600 seconds")
        return self

    @property
    def effective_worker_capacity(self) -> int:
        """Conservative process cap implied by count, CPU, and memory budgets."""

        return max(
            min(
                self.max_workers,
                int(self.max_total_cpus // self.max_cpus),
                self.max_total_memory_mb // self.max_memory_mb,
            ),
            1,
        )


class ActionContext(pydantic.BaseModel):
    """Trusted Workspace binding carried outside an action's data payload.

    Plugin-provided data must never be used to construct this object at the
    Runtime-to-Host boundary.  Runtime handlers bind it from the trusted
    LangBot control connection and forward that binding unchanged.
    """

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int = 1
    installation_uuid: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("instance_uuid", "workspace_uuid")
    @classmethod
    def validate_required_uuid(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @pydantic.field_validator("installation_uuid")
    @classmethod
    def validate_optional_uuid(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @pydantic.field_validator("placement_generation")
    @classmethod
    def validate_placement_generation(cls, value: int) -> int:
        if value < 1:
            raise ValueError("placement_generation must be greater than or equal to 1")
        return value

    def same_workspace(self, other: ActionContext) -> bool:
        """Return whether both contexts identify the same fenced Workspace."""

        return (
            self.instance_uuid == other.instance_uuid
            and self.workspace_uuid == other.workspace_uuid
            and self.placement_generation == other.placement_generation
        )

    def for_installation(self, installation_uuid: str | None) -> ActionContext:
        """Return the same Workspace binding with an installation capability."""

        return ActionContext(
            instance_uuid=self.instance_uuid,
            workspace_uuid=self.workspace_uuid,
            placement_generation=self.placement_generation,
            installation_uuid=installation_uuid,
        )

    def without_installation(self) -> ActionContext:
        """Return the Runtime-level Workspace binding."""

        if self.installation_uuid is None:
            return self
        return ActionContext(
            instance_uuid=self.instance_uuid,
            workspace_uuid=self.workspace_uuid,
            placement_generation=self.placement_generation,
        )


class InstallationBinding(ActionContext):
    """Complete, immutable authority for one plugin installation revision.

    ``placement_generation`` is retained on the wire for compatibility. Its
    target multi-tenant meaning is the Workspace execution generation.
    """

    installation_uuid: str
    runtime_revision: int
    artifact_digest: str

    @pydantic.field_validator("placement_generation", mode="before")
    @classmethod
    def validate_integer_execution_generation(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("placement_generation must be an integer")
        return value

    @pydantic.field_validator("runtime_revision", mode="before")
    @classmethod
    def reject_boolean_revision(cls, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("runtime_revision must be an integer")
        return value

    @pydantic.field_validator("runtime_revision")
    @classmethod
    def validate_runtime_revision(cls, value: int) -> int:
        if value < 1:
            raise ValueError("runtime_revision must be greater than or equal to 1")
        return value

    @pydantic.field_validator("artifact_digest")
    @classmethod
    def validate_artifact_digest(cls, value: str) -> str:
        value = value.strip()
        if _SHA256_DIGEST_PATTERN.fullmatch(value) is None:
            raise ValueError("artifact_digest must be a lowercase SHA-256 hex digest")
        return value

    @property
    def execution_generation(self) -> int:
        """Target-semantic alias for the compatibility wire field."""

        return self.placement_generation

    def same_installation(self, other: InstallationBinding) -> bool:
        """Return whether both bindings name the exact immutable worker tuple."""

        return self == other


class RuntimeConfig(pydantic.BaseModel):
    """Instance-scoped payload accepted by ``SET_RUNTIME_CONFIG``."""

    runtime_identity: RuntimeIdentity
    worker_policy: PluginWorkerPolicy
    runtime_profile: Literal["oss_dev", "shared"] = "oss_dev"
    cloud_service_url: str | None = None

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    def model_dump(self, **kwargs):
        include_pending_registration_limit = kwargs.pop(
            "include_pending_registration_limit",
            False,
        )
        payload = super().model_dump(**kwargs)
        if isinstance(payload.get("worker_policy"), dict):
            for mode in ("dedicated", "shared"):
                if (
                    self.runtime_profile != "shared"
                    or payload["worker_policy"].get(mode) is None
                ):
                    payload["worker_policy"].pop(mode, None)
        if not include_pending_registration_limit and isinstance(
            payload.get("worker_policy"),
            dict,
        ):
            payload["worker_policy"].pop("max_pending_registrations", None)
        return payload

    def model_dump_json(self, **kwargs) -> str:
        include_pending_registration_limit = kwargs.pop(
            "include_pending_registration_limit",
            False,
        )
        return json.dumps(
            self.model_dump(
                include_pending_registration_limit=include_pending_registration_limit,
                **kwargs,
            )
        )

    @pydantic.field_validator("cloud_service_url")
    @classmethod
    def validate_cloud_service_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value:
            raise ValueError("cloud_service_url must not be empty")
        return value


class PluginInstallationDesiredState(pydantic.BaseModel):
    """One installation entry replayed by the trusted control plane."""

    binding: InstallationBinding
    enabled: bool = True
    execution_mode: PluginExecutionMode = PluginExecutionMode.DEDICATED

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("enabled", mode="before")
    @classmethod
    def validate_enabled(cls, value):
        if not isinstance(value, bool):
            raise ValueError("enabled must be a boolean")
        return value


class ReconcilePluginInstallationsRequest(pydantic.BaseModel):
    installations: tuple[PluginInstallationDesiredState, ...]

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.model_validator(mode="after")
    def validate_unique_installations(self):
        installation_ids = [
            item.binding.installation_uuid for item in self.installations
        ]
        if len(installation_ids) != len(set(installation_ids)):
            raise ValueError(
                "installations must contain unique installation_uuid values"
            )
        return self


class ApplyPluginInstallationRequest(pydantic.BaseModel):
    artifact_file_key: str | None = None
    enabled: bool = True
    execution_mode: PluginExecutionMode = PluginExecutionMode.DEDICATED

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)

    @pydantic.field_validator("artifact_file_key")
    @classmethod
    def validate_artifact_file_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("artifact_file_key must not be empty")
        return value

    @pydantic.field_validator("enabled", mode="before")
    @classmethod
    def validate_enabled(cls, value):
        if not isinstance(value, bool):
            raise ValueError("enabled must be a boolean")
        return value


class RemovePluginInstallationRequest(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", frozen=True)


ActionEnvelopeContext = InstallationBinding | ActionContext
_ACTION_ENVELOPE_CONTEXT_ADAPTER: pydantic.TypeAdapter[ActionEnvelopeContext] = (
    pydantic.TypeAdapter(ActionEnvelopeContext)
)


def parse_action_envelope_context(
    value: ActionEnvelopeContext | dict,
) -> ActionEnvelopeContext:
    """Parse a legacy Workspace context or complete installation binding."""

    return _ACTION_ENVELOPE_CONTEXT_ADAPTER.validate_python(value)
