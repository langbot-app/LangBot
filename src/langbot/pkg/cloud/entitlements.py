from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

import pydantic


class EntitlementUnavailableError(RuntimeError):
    """Raised when a trusted, currently-active entitlement is unavailable."""

    def __init__(self, message: str, *, entitlement_revision: int | None = None) -> None:
        super().__init__(message)
        self.entitlement_revision = entitlement_revision


class EntitlementFeatureUnavailableError(EntitlementUnavailableError):
    """Raised only when an active entitlement does not grant one feature."""

    def __init__(
        self,
        feature: str,
        *,
        entitlement_revision: int | None = None,
    ) -> None:
        self.feature = feature
        super().__init__(
            f'Workspace entitlement does not grant {feature}',
            entitlement_revision=entitlement_revision,
        )


class EntitlementSnapshot(pydantic.BaseModel):
    """Capability projection consumed by open-source Core.

    Admission and quota decisions use normalized features/limits rather than
    product plan names. ``plan_name`` is signed display metadata for Cloud UI
    only and must never drive authorization or quota enforcement.
    """

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    instance_uuid: str = pydantic.Field(min_length=1, max_length=256)
    workspace_uuid: str = pydantic.Field(min_length=1, max_length=256)
    entitlement_revision: int = pydantic.Field(ge=1)
    status: str = pydantic.Field(pattern=r'^(active|suspended|cancelled)$')
    not_before: int = pydantic.Field(ge=0)
    expires_at: int = pydantic.Field(gt=0)
    features: dict[str, bool] = pydantic.Field(default_factory=dict)
    limits: dict[str, int] = pydantic.Field(default_factory=dict)
    # Signed display metadata for Cloud UI only. Admission and quota decisions
    # must continue to use generic ``features`` and ``limits`` exclusively.
    plan_name: str | None = pydantic.Field(default=None, min_length=1, max_length=128)

    @pydantic.field_validator('features')
    @classmethod
    def _validate_feature_names(cls, value: dict[str, bool]) -> dict[str, bool]:
        if any(not str(name).strip() for name in value):
            raise ValueError('Entitlement feature names must be non-empty')
        return dict(value)

    @pydantic.field_validator('limits')
    @classmethod
    def _validate_limits(cls, value: dict[str, int]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for name, limit in value.items():
            if not str(name).strip():
                raise ValueError('Entitlement limit names must be non-empty')
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
                raise ValueError(f'Entitlement limit {name!r} must be a non-negative integer')
            normalized[str(name)] = limit
        return normalized

    def require_active(
        self,
        *,
        instance_uuid: str,
        workspace_uuid: str,
        now: int | None = None,
    ) -> EntitlementSnapshot:
        current_time = int(time.time()) if now is None else now
        if self.instance_uuid != instance_uuid or self.workspace_uuid != workspace_uuid:
            raise EntitlementUnavailableError('Entitlement scope does not match the Workspace execution context')
        if self.status != 'active':
            raise EntitlementUnavailableError(
                'Workspace entitlement is not active',
                entitlement_revision=self.entitlement_revision,
            )
        if current_time < self.not_before or current_time >= self.expires_at:
            raise EntitlementUnavailableError(
                'Workspace entitlement is not currently valid',
                entitlement_revision=self.entitlement_revision,
            )
        return self

    def require_feature(self, feature: str) -> None:
        if self.features.get(feature) is not True:
            raise EntitlementFeatureUnavailableError(
                feature,
                entitlement_revision=self.entitlement_revision,
            )

    def limit(self, name: str) -> int:
        value = self.limits.get(name)
        if value is None:
            raise EntitlementUnavailableError(f'Workspace entitlement does not define limit {name}')
        return value


@runtime_checkable
class EntitlementProvider(Protocol):
    """Closed Control Plane adapter injected by a verified Cloud bootstrap."""

    async def get_workspace_entitlement(self, workspace_uuid: str) -> EntitlementSnapshot:
        """Return the newest verified snapshot for one Workspace."""


class OpenSourceEntitlementProvider:
    """Marker provider for OSS; Cloud admission grants never use this class."""

    async def get_workspace_entitlement(self, workspace_uuid: str) -> EntitlementSnapshot:
        del workspace_uuid
        raise EntitlementUnavailableError('Signed Workspace entitlements are only available in Cloud mode')


class EntitlementResolver:
    """Validate scope/freshness and reject revision rollback or equivocation."""

    def __init__(
        self,
        instance_uuid: str,
        provider: EntitlementProvider,
        *,
        deployment_admission: Callable[[], object] | None = None,
    ) -> None:
        self.instance_uuid = instance_uuid
        self.provider = provider
        self._deployment_admission = deployment_admission
        self._lock = asyncio.Lock()
        self._snapshots: dict[str, tuple[int, str, EntitlementSnapshot]] = {}
        self._active_workspace_uuids: frozenset[str] | None = None

    @staticmethod
    def _fingerprint(snapshot: EntitlementSnapshot) -> str:
        return json.dumps(snapshot.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))

    async def resolve(
        self,
        workspace_uuid: str,
        *,
        minimum_revision: int = 0,
        now: int | None = None,
    ) -> EntitlementSnapshot:
        if self._deployment_admission is not None:
            self._deployment_admission()
        async with self._lock:
            self._require_projected_workspace_locked(workspace_uuid)
        candidate = await self.provider.get_workspace_entitlement(workspace_uuid)
        if self._deployment_admission is not None:
            # A provider call may cross the Manifest expiry boundary.
            self._deployment_admission()
        if not isinstance(candidate, EntitlementSnapshot):
            raise EntitlementUnavailableError('Entitlement provider returned an invalid snapshot')
        # Deep-copy untrusted provider-owned containers before caching them.
        candidate = EntitlementSnapshot.model_validate(candidate.model_dump())
        candidate.require_active(
            instance_uuid=self.instance_uuid,
            workspace_uuid=workspace_uuid,
            now=now,
        )
        if candidate.entitlement_revision < minimum_revision:
            raise EntitlementUnavailableError('Workspace entitlement revision rolled back')

        fingerprint = self._fingerprint(candidate)
        async with self._lock:
            # The directory may fence a Workspace while the provider call is
            # in flight. Recheck before retaining or returning its snapshot.
            self._require_projected_workspace_locked(workspace_uuid)
            previous = self._snapshots.get(workspace_uuid)
            if previous is not None:
                previous_revision, previous_fingerprint, _ = previous
                if candidate.entitlement_revision < previous_revision:
                    raise EntitlementUnavailableError('Workspace entitlement revision rolled back')
                if candidate.entitlement_revision == previous_revision and fingerprint != previous_fingerprint:
                    raise EntitlementUnavailableError('Workspace entitlement revision has conflicting contents')
            self._snapshots[workspace_uuid] = (
                candidate.entitlement_revision,
                fingerprint,
                candidate,
            )
        return candidate.model_copy(deep=True)

    def _require_projected_workspace_locked(self, workspace_uuid: str) -> None:
        active_workspace_uuids = self._active_workspace_uuids
        if active_workspace_uuids is not None and workspace_uuid not in active_workspace_uuids:
            raise EntitlementUnavailableError('Workspace is not active in the Cloud directory projection')

    async def reconcile_active_workspaces(
        self,
        workspace_uuids: set[str] | frozenset[str],
    ) -> None:
        """Drop entitlement history for Workspaces fenced by the directory."""

        active = frozenset(workspace_uuids)
        async with self._lock:
            self._active_workspace_uuids = active
            self._snapshots = {
                workspace_uuid: cached for workspace_uuid, cached in self._snapshots.items() if workspace_uuid in active
            }

    async def set_workspace_active(
        self,
        workspace_uuid: str,
        *,
        active: bool,
    ) -> None:
        """Apply one incremental directory activity change."""

        await self.update_workspace_activity(
            active_workspace_uuids={workspace_uuid} if active else set(),
            inactive_workspace_uuids=set() if active else {workspace_uuid},
        )

    async def update_workspace_activity(
        self,
        *,
        active_workspace_uuids: set[str] | frozenset[str],
        inactive_workspace_uuids: set[str] | frozenset[str],
    ) -> None:
        """Apply one directory delta without copying the active set per item."""

        active_updates = set(active_workspace_uuids)
        inactive_updates = set(inactive_workspace_uuids)
        if active_updates & inactive_updates:
            raise ValueError('Workspace activity update contains conflicting entries')
        async with self._lock:
            current = set(self._active_workspace_uuids or ())
            current.update(active_updates)
            current.difference_update(inactive_updates)
            for workspace_uuid in inactive_updates:
                self._snapshots.pop(workspace_uuid, None)
            self._active_workspace_uuids = frozenset(current)

    def snapshot_counts(self) -> dict[str, int]:
        return {
            'active_workspaces': len(self._active_workspace_uuids or ()),
            'cached_snapshots': len(self._snapshots),
        }
