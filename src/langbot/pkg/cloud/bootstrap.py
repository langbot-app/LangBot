from __future__ import annotations

import dataclasses
import importlib.metadata
import inspect
import os
import threading
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ..workspace.policy import CloudWorkspacePolicy, SingleWorkspacePolicy
from .entitlements import EntitlementProvider, OpenSourceEntitlementProvider


CLOUD_BOOTSTRAP_ENTRY_POINT = 'langbot.cloud_bootstrap'
REQUIRED_TENANT_ISOLATION_VERSION = 2
SUPPORTED_PGVECTOR_DIMENSIONS = frozenset({384, 512, 768, 1024, 1536})


class CloudBootstrapError(RuntimeError):
    """Fail-closed Cloud bootstrap validation error."""


class CloudRuntimeUnavailableError(CloudBootstrapError):
    """The verified Cloud receipt no longer admits runtime work."""


@dataclasses.dataclass(frozen=True, slots=True)
class OpenSourceDeployment:
    """Default deployment selected when no closed bootstrap is installed."""

    mode: str = 'oss'
    workspace_policy: SingleWorkspacePolicy = dataclasses.field(default_factory=SingleWorkspacePolicy)
    entitlement_provider: OpenSourceEntitlementProvider = dataclasses.field(
        default_factory=OpenSourceEntitlementProvider
    )
    persistence_mode: str = 'oss_compat'
    required_vector_backend: str | None = None

    @property
    def multi_workspace_enabled(self) -> bool:
        return False

    def validate_instance_config(self, config: dict[str, Any]) -> None:
        del config


@dataclasses.dataclass(frozen=True, slots=True)
class VerifiedCloudDeployment:
    """Receipt returned only after the closed package verifies a Manifest.

    Core deliberately does not accept a config flag as a substitute for this
    object.  The closed entry point owns root-key/JWS verification and the
    entitlement adapter; open Core validates the receipt's runtime invariants.
    """

    instance_uuid: str
    manifest_jti: str
    manifest_generation: int
    expires_at: int
    release: str
    capabilities: frozenset[str]
    tenant_isolation_version: int
    entitlement_provider: EntitlementProvider
    verification_key_id: str
    mode: str = dataclasses.field(default='cloud', init=False)
    workspace_policy: CloudWorkspacePolicy = dataclasses.field(default_factory=CloudWorkspacePolicy, init=False)
    persistence_mode: str = dataclasses.field(default='cloud_runtime', init=False)
    required_vector_backend: str = dataclasses.field(default='pgvector', init=False)

    @property
    def multi_workspace_enabled(self) -> bool:
        return True

    def validate(self, expected_instance_uuid: str, *, now: int | None = None) -> None:
        current_time = int(time.time()) if now is None else now
        if not self.instance_uuid or self.instance_uuid != expected_instance_uuid:
            raise CloudBootstrapError('Verified Cloud Manifest targets another LangBot instance')
        if not self.manifest_jti or not self.verification_key_id:
            raise CloudBootstrapError('Verified Cloud Manifest receipt is incomplete')
        if isinstance(self.manifest_generation, bool) or self.manifest_generation <= 0:
            raise CloudBootstrapError('Verified Cloud Manifest generation must be positive')
        if self.expires_at <= current_time:
            raise CloudBootstrapError('Verified Cloud Manifest is expired')
        if self.tenant_isolation_version < REQUIRED_TENANT_ISOLATION_VERSION:
            raise CloudBootstrapError('Verified Cloud Manifest requires an unsupported tenant isolation version')
        if 'multi_workspace_v2' not in self.capabilities:
            raise CloudBootstrapError('Verified Cloud Manifest does not grant multi_workspace_v2')
        if not isinstance(self.entitlement_provider, EntitlementProvider):
            raise CloudBootstrapError('Verified Cloud bootstrap did not provide an entitlement adapter')

    def validate_instance_config(self, config: dict[str, Any]) -> None:
        if config.get('database', {}).get('use') != 'postgresql':
            raise CloudBootstrapError('Cloud runtime requires database.use=postgresql')
        if config.get('vdb', {}).get('use') != self.required_vector_backend:
            raise CloudBootstrapError('Cloud runtime requires vdb.use=pgvector')
        pgvector_config = config.get('vdb', {}).get('pgvector', {})
        if pgvector_config.get('use_business_database') is not True:
            raise CloudBootstrapError('Cloud runtime requires vdb.pgvector.use_business_database=true')
        dimensions = pgvector_config.get('allowed_dimensions')
        if (
            not isinstance(dimensions, list)
            or not dimensions
            or any(isinstance(item, bool) or not isinstance(item, int) for item in dimensions)
            or not set(dimensions).issubset(SUPPORTED_PGVECTOR_DIMENSIONS)
        ):
            supported = ', '.join(str(item) for item in sorted(SUPPORTED_PGVECTOR_DIMENSIONS))
            raise CloudBootstrapError(f'Cloud pgvector allowed_dimensions must be a non-empty subset of: {supported}')
        if config.get('mcp', {}).get('stdio', {}).get('enabled', True) is not False:
            raise CloudBootstrapError('Cloud runtime requires mcp.stdio.enabled=false')
        plugin_worker = config.get('plugin', {}).get('worker', {})
        if plugin_worker.get('require_hard_limits') is not True:
            raise CloudBootstrapError('Cloud Runtime requires plugin.worker.require_hard_limits=true')
        box_config = config.get('box', {})
        if box_config.get('enabled') is not True:
            raise CloudBootstrapError('Cloud runtime requires box.enabled=true')
        if box_config.get('backend') != 'nsjail':
            raise CloudBootstrapError('Cloud runtime requires box.backend=nsjail')
        runtime_endpoint = str(box_config.get('runtime', {}).get('endpoint', '') or '').strip()
        if not runtime_endpoint:
            raise CloudBootstrapError('Cloud runtime requires a shared external box.runtime.endpoint')
        admission = box_config.get('admission', {})
        required_admission = {
            'required': True,
            'logical_session_id': 'global',
            'required_backend': 'nsjail',
            'max_sessions': 1,
            'max_managed_processes': 0,
        }
        if any(admission.get(name) != value for name, value in required_admission.items()):
            raise CloudBootstrapError(
                'Cloud runtime requires grant-enforced Box admission with one global session and zero managed processes'
            )
        grant_ttl = admission.get('max_grant_ttl_sec')
        if isinstance(grant_ttl, bool) or not isinstance(grant_ttl, int) or not 1 <= grant_ttl <= 300:
            raise CloudBootstrapError('Cloud Box admission max_grant_ttl_sec must be between 1 and 300')
        workspace_quota_mb = admission.get('workspace_quota_mb')
        if isinstance(workspace_quota_mb, bool) or not isinstance(workspace_quota_mb, int) or workspace_quota_mb <= 0:
            raise CloudBootstrapError('Cloud Box admission workspace_quota_mb must be a positive integer')
        local_config = box_config.get('local', {})
        host_root = str(local_config.get('host_root', '') or '').strip()
        default_workspace = str(local_config.get('default_workspace', '') or '').strip()
        allowed_mount_roots = local_config.get('allowed_mount_roots')
        if not host_root or not os.path.isabs(host_root):
            raise CloudBootstrapError('Cloud Box local.host_root must be an absolute shared-volume path')
        if not default_workspace or not os.path.isabs(default_workspace):
            raise CloudBootstrapError('Cloud Box local.default_workspace must be an absolute shared-volume path')
        if (
            not isinstance(allowed_mount_roots, list)
            or not allowed_mount_roots
            or any(not isinstance(root, str) or not os.path.isabs(root) for root in allowed_mount_roots)
        ):
            raise CloudBootstrapError('Cloud Box local.allowed_mount_roots must contain absolute shared-volume paths')
        resolved_workspace = os.path.realpath(default_workspace)
        if not any(
            resolved_workspace == os.path.realpath(root)
            or resolved_workspace.startswith(f'{os.path.realpath(root)}{os.sep}')
            for root in allowed_mount_roots
        ):
            raise CloudBootstrapError('Cloud Box local.default_workspace must be under allowed_mount_roots')


class CloudBootstrapProvider(Protocol):
    def bootstrap(
        self,
        *,
        instance_uuid: str,
        instance_config: dict[str, Any],
    ) -> VerifiedCloudDeployment | Awaitable[VerifiedCloudDeployment]: ...


class DeploymentAdmissionGuard:
    """Continuously enforce one verified deployment receipt.

    Startup verification alone is insufficient because a long-running process
    could otherwise keep serving after the signed Manifest expires. The guard
    tracks both wall-clock expiry and a monotonic deadline so moving the system
    clock backwards cannot extend an already admitted receipt.

    A closed bootstrap may atomically replace the receipt with a strictly newer
    Manifest generation after performing its own signature verification. The
    logical instance and deployment mode cannot change during the process.
    """

    def __init__(
        self,
        instance_uuid: str,
        deployment: OpenSourceDeployment | VerifiedCloudDeployment,
        *,
        wall_time: Callable[[], float] = time.time,
        monotonic_time: Callable[[], float] = time.monotonic,
    ) -> None:
        self.instance_uuid = instance_uuid
        self._wall_time = wall_time
        self._monotonic_time = monotonic_time
        self._lock = threading.Lock()
        self._deployment = deployment
        self._deadline: float | None = None
        self._install_initial(deployment)

    @property
    def deployment(self) -> OpenSourceDeployment | VerifiedCloudDeployment:
        with self._lock:
            return self._deployment

    def _install_initial(self, deployment: OpenSourceDeployment | VerifiedCloudDeployment) -> None:
        now = int(self._wall_time())
        if isinstance(deployment, VerifiedCloudDeployment):
            deployment.validate(self.instance_uuid, now=now)
            self._deadline = self._monotonic_time() + (deployment.expires_at - now)
        elif not isinstance(deployment, OpenSourceDeployment):
            raise TypeError('Deployment admission requires a verified deployment object')

    @staticmethod
    def _receipt_identity(deployment: VerifiedCloudDeployment) -> tuple[Any, ...]:
        return (
            deployment.instance_uuid,
            deployment.manifest_jti,
            deployment.manifest_generation,
            deployment.expires_at,
            deployment.release,
            tuple(sorted(deployment.capabilities)),
            deployment.tenant_isolation_version,
            deployment.verification_key_id,
        )

    def replace(self, deployment: VerifiedCloudDeployment) -> None:
        """Atomically install a verified, non-rollback Cloud receipt."""

        now = int(self._wall_time())
        deployment.validate(self.instance_uuid, now=now)
        with self._lock:
            current = self._deployment
            if not isinstance(current, VerifiedCloudDeployment):
                raise CloudRuntimeUnavailableError('Deployment mode cannot change while LangBot is running')
            if deployment.manifest_generation < current.manifest_generation:
                raise CloudRuntimeUnavailableError('Cloud Manifest generation rolled back')
            if deployment.manifest_generation == current.manifest_generation and self._receipt_identity(
                deployment
            ) != self._receipt_identity(current):
                raise CloudRuntimeUnavailableError('Cloud Manifest generation has conflicting contents')
            self._deployment = deployment
            self._deadline = self._monotonic_time() + (deployment.expires_at - now)

    def require_active(self) -> OpenSourceDeployment | VerifiedCloudDeployment:
        """Return the active deployment or fail closed after Manifest expiry."""

        now = int(self._wall_time())
        monotonic_now = self._monotonic_time()
        with self._lock:
            deployment = self._deployment
            deadline = self._deadline
        if isinstance(deployment, OpenSourceDeployment):
            return deployment
        try:
            deployment.validate(self.instance_uuid, now=now)
        except CloudBootstrapError as exc:
            raise CloudRuntimeUnavailableError(str(exc)) from exc
        if deadline is None or monotonic_now >= deadline:
            raise CloudRuntimeUnavailableError('Verified Cloud Manifest is expired')
        return deployment


async def _invoke_provider(
    loaded: Any,
    *,
    instance_uuid: str,
    instance_config: dict[str, Any],
) -> VerifiedCloudDeployment:
    provider = loaded() if inspect.isclass(loaded) else loaded
    bootstrap = getattr(provider, 'bootstrap', None)
    if not callable(bootstrap):
        raise CloudBootstrapError('Cloud bootstrap entry point must expose bootstrap()')
    result = bootstrap(instance_uuid=instance_uuid, instance_config=instance_config)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, VerifiedCloudDeployment):
        raise CloudBootstrapError('Cloud bootstrap must return VerifiedCloudDeployment')
    return result


async def resolve_deployment(
    *,
    instance_uuid: str,
    instance_config: dict[str, Any],
    entry_points: Callable[[], Any] | None = None,
    now: int | None = None,
) -> OpenSourceDeployment | VerifiedCloudDeployment:
    """Discover the optional closed bootstrap and validate its receipt.

    Absence selects OSS singleton mode.  Presence is fail-closed: duplicate,
    broken, invalid, or expired providers never fall back to an OSS Workspace.
    """

    discover = entry_points or importlib.metadata.entry_points
    discovered = discover()
    if hasattr(discovered, 'select'):
        candidates = list(discovered.select(group=CLOUD_BOOTSTRAP_ENTRY_POINT))
    else:  # Python/importlib compatibility for dict-like EntryPoints
        candidates = list(discovered.get(CLOUD_BOOTSTRAP_ENTRY_POINT, ()))
    if not candidates:
        deployment = OpenSourceDeployment()
        deployment.validate_instance_config(instance_config)
        return deployment
    if len(candidates) != 1:
        raise CloudBootstrapError('Exactly one Cloud bootstrap provider may be installed')

    try:
        loaded = candidates[0].load()
        deployment = await _invoke_provider(
            loaded,
            instance_uuid=instance_uuid,
            instance_config=instance_config,
        )
        deployment.validate(instance_uuid, now=now)
        deployment.validate_instance_config(instance_config)
        return deployment
    except CloudBootstrapError:
        raise
    except Exception as exc:
        raise CloudBootstrapError('Closed Cloud bootstrap failed') from exc
