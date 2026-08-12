from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import pydantic


DEFAULT_MAX_ACTIVE_WORKSPACES = 1_000
HARD_MAX_ACTIVE_WORKSPACES = 5_000
DEFAULT_MAX_SNAPSHOT_WORKSPACES = 1_000
HARD_MAX_SNAPSHOT_WORKSPACES = 5_000
DEFAULT_MAX_SNAPSHOT_MEMBERSHIPS = 20_000
HARD_MAX_SNAPSHOT_MEMBERSHIPS = 100_000
DEFAULT_MAX_CONTROL_PLANE_RESPONSE_BYTES = 32 * 1024 * 1024
HARD_MAX_CONTROL_PLANE_RESPONSE_BYTES = 64 * 1024 * 1024


class DirectoryProjectionUnavailableError(RuntimeError):
    """Raised when the verified Cloud directory cannot safely admit work."""


class DirectoryProjectionLimits(pydantic.BaseModel):
    """Instance-owned cardinality limits for verified Cloud directory data.

    These are operational safety limits, not subscription entitlements.  Core
    fails the complete projection transaction when a limit is exceeded instead
    of truncating an authoritative directory and accidentally hiding tenants.
    The closed adapter consumes the same limits before priming entitlement
    caches, and additionally bounds the HTTP response buffered for signature
    verification.
    """

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    max_active_workspaces: int = pydantic.Field(
        default=DEFAULT_MAX_ACTIVE_WORKSPACES,
        ge=1,
        le=HARD_MAX_ACTIVE_WORKSPACES,
    )
    max_snapshot_workspaces: int = pydantic.Field(
        default=DEFAULT_MAX_SNAPSHOT_WORKSPACES,
        ge=1,
        le=HARD_MAX_SNAPSHOT_WORKSPACES,
    )
    max_snapshot_memberships: int = pydantic.Field(
        default=DEFAULT_MAX_SNAPSHOT_MEMBERSHIPS,
        ge=1,
        le=HARD_MAX_SNAPSHOT_MEMBERSHIPS,
    )
    max_response_bytes: int = pydantic.Field(
        default=DEFAULT_MAX_CONTROL_PLANE_RESPONSE_BYTES,
        ge=1024 * 1024,
        le=HARD_MAX_CONTROL_PLANE_RESPONSE_BYTES,
    )

    @pydantic.field_validator(
        'max_active_workspaces',
        'max_snapshot_workspaces',
        'max_snapshot_memberships',
        'max_response_bytes',
        mode='before',
    )
    @classmethod
    def _reject_boolean_limits(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError('must be an integer')
        return value

    @pydantic.model_validator(mode='after')
    def _validate_workspace_limits(self) -> DirectoryProjectionLimits:
        if self.max_snapshot_workspaces < self.max_active_workspaces:
            raise ValueError('max_snapshot_workspaces must be greater than or equal to max_active_workspaces')
        return self


def directory_projection_limits_from_config(config: dict[str, Any]) -> DirectoryProjectionLimits:
    """Parse typed Cloud directory limits from the instance configuration."""

    cloud_config = config.get('cloud', {})
    if not isinstance(cloud_config, dict):
        raise ValueError('cloud must be a mapping')
    directory_config = cloud_config.get('directory', {})
    if not isinstance(directory_config, dict):
        raise ValueError('cloud.directory must be a mapping')
    return DirectoryProjectionLimits.model_validate(directory_config)


class DirectoryMember(pydantic.BaseModel):
    """One account membership published by the SaaS control plane."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    membership_uuid: str = pydantic.Field(min_length=1, max_length=36)
    account_uuid: str = pydantic.Field(min_length=1, max_length=36)
    normalized_email: str = pydantic.Field(min_length=1, max_length=320)
    display_name: str = pydantic.Field(min_length=1, max_length=255)
    account_status: str = pydantic.Field(pattern=r'^(active|blocked|disabled|deleted)$')
    role: str = pydantic.Field(pattern=r'^(owner|admin|member|developer|operator|viewer)$')
    membership_status: str = pydantic.Field(pattern=r'^(active|invited|disabled|removed)$')
    projection_revision: int = pydantic.Field(ge=1)
    joined_at: datetime.datetime | None = None

    @pydantic.field_validator('normalized_email')
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized != value:
            raise ValueError('Directory email must already be normalized')
        return normalized


class DirectoryWorkspace(pydantic.BaseModel):
    """One Workspace and its authoritative membership projection."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    uuid: str = pydantic.Field(min_length=1, max_length=36)
    name: str = pydantic.Field(min_length=1, max_length=255)
    slug: str = pydantic.Field(min_length=1, max_length=255)
    type: str = pydantic.Field(pattern=r'^(personal|team)$')
    status: str = pydantic.Field(pattern=r'^(provisioning|active|suspended|archived|deleted)$')
    created_by_account_uuid: str = pydantic.Field(min_length=1, max_length=36)
    projection_revision: int = pydantic.Field(ge=1)
    execution_generation: int = pydantic.Field(ge=1)
    members: tuple[DirectoryMember, ...] = pydantic.Field(
        default=(),
        max_length=HARD_MAX_SNAPSHOT_MEMBERSHIPS,
    )

    @pydantic.field_validator('members', mode='before')
    @classmethod
    def _copy_members(cls, value: Sequence[DirectoryMember] | None) -> tuple[DirectoryMember, ...]:
        return tuple(value or ())

    @pydantic.model_validator(mode='after')
    def _validate_members(self) -> DirectoryWorkspace:
        membership_uuids: set[str] = set()
        account_uuids: set[str] = set()
        for member in self.members:
            if member.membership_uuid in membership_uuids:
                raise ValueError('Directory Workspace contains duplicate membership UUIDs')
            if member.account_uuid in account_uuids:
                raise ValueError('Directory Workspace contains duplicate account UUIDs')
            membership_uuids.add(member.membership_uuid)
            account_uuids.add(member.account_uuid)
        if self.created_by_account_uuid not in account_uuids:
            raise ValueError('Directory Workspace must include its creator')
        return self


class DirectorySnapshot(pydantic.BaseModel):
    """Full signed directory state at one monotonic outbox cursor."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    instance_uuid: str = pydantic.Field(min_length=1, max_length=255)
    cursor: int = pydantic.Field(ge=0)
    generated_at: datetime.datetime
    workspaces: tuple[DirectoryWorkspace, ...] = pydantic.Field(
        default=(),
        max_length=HARD_MAX_SNAPSHOT_WORKSPACES,
    )

    @pydantic.field_validator('workspaces', mode='before')
    @classmethod
    def _copy_workspaces(cls, value: Sequence[DirectoryWorkspace] | None) -> tuple[DirectoryWorkspace, ...]:
        return tuple(value or ())

    @pydantic.model_validator(mode='after')
    def _validate_workspaces(self) -> DirectorySnapshot:
        workspace_uuids: set[str] = set()
        slugs: set[str] = set()
        membership_uuids: set[str] = set()
        for workspace in self.workspaces:
            if workspace.uuid in workspace_uuids:
                raise ValueError('Directory snapshot contains duplicate Workspace UUIDs')
            if workspace.slug in slugs:
                raise ValueError('Directory snapshot contains duplicate Workspace slugs')
            workspace_uuids.add(workspace.uuid)
            slugs.add(workspace.slug)
            for member in workspace.members:
                if member.membership_uuid in membership_uuids:
                    raise ValueError('Directory snapshot contains duplicate membership UUIDs')
                membership_uuids.add(member.membership_uuid)
        return self


class DirectoryDelta(pydantic.BaseModel):
    """Signed authoritative state for an explicitly requested Workspace set."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    instance_uuid: str = pydantic.Field(min_length=1, max_length=255)
    requested_workspace_uuids: tuple[str, ...]
    generated_at: datetime.datetime
    workspaces: tuple[DirectoryWorkspace, ...] = ()

    @pydantic.field_validator('requested_workspace_uuids', mode='before')
    @classmethod
    def _copy_requested_workspace_uuids(cls, value: Sequence[str]) -> tuple[str, ...]:
        return tuple(value)

    @pydantic.field_validator('workspaces', mode='before')
    @classmethod
    def _copy_workspaces(cls, value: Sequence[DirectoryWorkspace] | None) -> tuple[DirectoryWorkspace, ...]:
        return tuple(value or ())

    @pydantic.model_validator(mode='after')
    def _validate_workspaces(self) -> DirectoryDelta:
        requested = self.requested_workspace_uuids
        if not requested or len(requested) > 100:
            raise ValueError('Directory delta must request between 1 and 100 Workspaces')
        if any(not workspace_uuid or len(workspace_uuid) > 36 for workspace_uuid in requested):
            raise ValueError('Directory delta contains an invalid requested Workspace UUID')
        if len(requested) != len(set(requested)):
            raise ValueError('Directory delta contains duplicate requested Workspace UUIDs')

        requested_set = set(requested)
        workspace_uuids: set[str] = set()
        slugs: set[str] = set()
        membership_uuids: set[str] = set()
        for workspace in self.workspaces:
            if workspace.uuid in workspace_uuids:
                raise ValueError('Directory delta contains duplicate Workspace UUIDs')
            if workspace.uuid not in requested_set:
                raise ValueError('Directory delta returned an unrequested Workspace')
            if workspace.slug in slugs:
                raise ValueError('Directory delta contains duplicate Workspace slugs')
            workspace_uuids.add(workspace.uuid)
            slugs.add(workspace.slug)
            for member in workspace.members:
                if member.membership_uuid in membership_uuids:
                    raise ValueError('Directory delta contains duplicate membership UUIDs')
                membership_uuids.add(member.membership_uuid)
        return self


class DirectoryEvent(pydantic.BaseModel):
    """One signed control-plane outbox notification."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    cursor: int = pydantic.Field(ge=1)
    uuid: str = pydantic.Field(min_length=1, max_length=36)
    aggregate_uuid: str = pydantic.Field(min_length=1, max_length=36)
    event_type: str = pydantic.Field(min_length=1, max_length=128)
    revision: int = pydantic.Field(ge=1)
    payload: dict[str, Any] = pydantic.Field(default_factory=dict)
    created_at: datetime.datetime


class DirectoryEventBatch(pydantic.BaseModel):
    """Signed events returned after a caller-supplied directory cursor."""

    model_config = pydantic.ConfigDict(frozen=True, extra='forbid')

    instance_uuid: str = pydantic.Field(min_length=1, max_length=255)
    after_cursor: int = pydantic.Field(ge=0)
    cursor: int = pydantic.Field(ge=0)
    high_water_cursor: int = pydantic.Field(ge=0)
    events: tuple[DirectoryEvent, ...] = ()

    @pydantic.field_validator('events', mode='before')
    @classmethod
    def _copy_events(cls, value: Sequence[DirectoryEvent] | None) -> tuple[DirectoryEvent, ...]:
        return tuple(value or ())

    @pydantic.model_validator(mode='after')
    def _validate_events(self) -> DirectoryEventBatch:
        if self.cursor < self.after_cursor:
            raise ValueError('Directory event cursor rolled back')
        if self.high_water_cursor < self.cursor:
            raise ValueError('Directory event high-water mark rolled back')
        event_cursors = [event.cursor for event in self.events]
        event_uuids = [event.uuid for event in self.events]
        if event_cursors != sorted(event_cursors) or len(event_cursors) != len(set(event_cursors)):
            raise ValueError('Directory events must have strictly increasing cursors')
        if len(event_uuids) != len(set(event_uuids)):
            raise ValueError('Directory event batch contains duplicate UUIDs')
        if any(cursor <= self.after_cursor or cursor > self.cursor for cursor in event_cursors):
            raise ValueError('Directory event falls outside the requested cursor window')
        if not self.events and (self.cursor != self.after_cursor or self.high_water_cursor != self.after_cursor):
            raise ValueError('Empty Directory event batch cannot advance or trail the high-water mark')
        if self.events and self.cursor != self.events[-1].cursor:
            raise ValueError('Directory event batch cursor must equal its final event cursor')
        return self


@runtime_checkable
class DirectoryProjectionProvider(Protocol):
    """Closed adapter that returns signature-verified control-plane data."""

    async def fetch_snapshot(self, instance_uuid: str) -> DirectorySnapshot:
        """Fetch and verify an authoritative full snapshot."""

    async def fetch_events(
        self,
        instance_uuid: str,
        after_cursor: int,
        limit: int,
    ) -> DirectoryEventBatch:
        """Fetch and verify directory events after one process-local cursor."""

    async def fetch_workspaces(
        self,
        instance_uuid: str,
        workspace_uuids: tuple[str, ...],
    ) -> DirectoryDelta:
        """Fetch and verify authoritative state for an explicit Workspace set."""
