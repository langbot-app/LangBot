from __future__ import annotations

import dataclasses
import importlib.metadata
import inspect
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ..workspace.policy import CloudWorkspacePolicy, SingleWorkspacePolicy
from .entitlements import EntitlementProvider, OpenSourceEntitlementProvider


CLOUD_BOOTSTRAP_ENTRY_POINT = 'langbot.cloud_bootstrap'
REQUIRED_TENANT_ISOLATION_VERSION = 2


class CloudBootstrapError(RuntimeError):
    """Fail-closed Cloud bootstrap validation error."""


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
        if config.get('mcp', {}).get('stdio', {}).get('enabled', True) is not False:
            raise CloudBootstrapError('Cloud runtime requires mcp.stdio.enabled=false')


class CloudBootstrapProvider(Protocol):
    def bootstrap(
        self,
        *,
        instance_uuid: str,
        instance_config: dict[str, Any],
    ) -> VerifiedCloudDeployment | Awaitable[VerifiedCloudDeployment]: ...


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
