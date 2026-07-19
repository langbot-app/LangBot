from __future__ import annotations

import asyncio
import datetime as dt
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from langbot_plugin.box.errors import BoxAdmissionError, BoxRuntimeUnavailableError
from langbot_plugin.box.models import (
    SandboxAdmissionGrant,
    SandboxAdmissionPolicy,
    SandboxAdmissionRevocation,
)

from ..api.http.context import ExecutionContext
from ..cloud.entitlements import EntitlementSnapshot, EntitlementUnavailableError

if TYPE_CHECKING:
    from langbot_plugin.box.client import BoxRuntimeClient

    from ..core.app import Application


_UTC = dt.timezone.utc
_MANAGED_SANDBOX_FEATURE = 'managed_sandbox'
_MANAGED_SANDBOX_SESSION_LIMIT = 'managed_sandbox_sessions'
_MAX_GRANT_TTL_SEC = 300


class SandboxAdmissionController:
    """Project Cloud entitlements into short-lived Box Runtime grants.

    Product and plan names intentionally never cross this boundary. The
    closed Control Plane supplies a versioned generic entitlement, while Core
    installs only the numeric authority understood by the shared Box Runtime.

    No state is allocated for a Workspace until it attempts to use the
    managed sandbox. Per-Workspace locks serialize renewal/revocation so a
    concurrent first use cannot install conflicting grants.
    """

    def __init__(
        self,
        ap: Application,
        client: BoxRuntimeClient,
        *,
        policy: SandboxAdmissionPolicy,
        wall_time: Callable[[], float] = time.time,
    ) -> None:
        self.ap = ap
        self.client = client
        self.policy = policy
        self._wall_time = wall_time
        self._locks: dict[str, asyncio.Lock] = {}
        self._highest_revisions: dict[str, int] = {}

    def _workspace_lock(self, workspace_uuid: str) -> asyncio.Lock:
        lock = self._locks.get(workspace_uuid)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[workspace_uuid] = lock
        return lock

    @staticmethod
    def _context_revision(context: ExecutionContext) -> int:
        revision = getattr(context, 'entitlement_revision', 0)
        if isinstance(revision, bool) or not isinstance(revision, int):
            return 0
        return max(revision, 0)

    def _revocation_revision(self, context: ExecutionContext, candidate_revision: int = 0) -> int:
        return max(
            1,
            self._highest_revisions.get(context.workspace_uuid, 0),
            self._context_revision(context),
            candidate_revision,
        )

    async def _revoke_locked(
        self,
        context: ExecutionContext,
        *,
        candidate_revision: int = 0,
    ) -> None:
        revision = self._revocation_revision(context, candidate_revision)
        revocation = SandboxAdmissionRevocation(
            instance_uuid=context.instance_uuid,
            workspace_uuid=context.workspace_uuid,
            entitlement_revision=revision,
        )
        try:
            result = await self.client.revoke_sandbox_admission_grant(revocation)
            if (
                not isinstance(result, dict)
                or result.get('revoked') is not True
                or result.get('workspace_uuid') != context.workspace_uuid
                or result.get('entitlement_revision') != revision
            ):
                raise BoxRuntimeUnavailableError('Box Runtime returned an invalid sandbox revocation receipt')
        except Exception as exc:
            # The caller still fails closed even if the control connection is
            # unavailable. A previously installed grant expires independently
            # in at most five minutes inside the Runtime.
            self.ap.logger.warning(
                'Failed to install Box sandbox admission revocation: '
                f'workspace_uuid={context.workspace_uuid} revision={revision} error={exc}'
            )
        self._highest_revisions[context.workspace_uuid] = revision

    @staticmethod
    def _require_managed_sandbox(snapshot: EntitlementSnapshot) -> None:
        snapshot.require_feature(_MANAGED_SANDBOX_FEATURE)
        sessions = snapshot.limit(_MANAGED_SANDBOX_SESSION_LIMIT)
        if sessions != 1:
            raise EntitlementUnavailableError('Workspace entitlement must grant exactly one managed sandbox session')

    def _grant_expiry(self, snapshot: EntitlementSnapshot) -> dt.datetime:
        now_epoch = int(self._wall_time())
        ttl_sec = min(self.policy.max_grant_ttl_sec, _MAX_GRANT_TTL_SEC)
        expires_epoch = min(snapshot.expires_at, now_epoch + ttl_sec)
        if expires_epoch <= now_epoch:
            raise EntitlementUnavailableError('Workspace entitlement expired before sandbox admission')
        return dt.datetime.fromtimestamp(expires_epoch, tz=_UTC)

    async def require(self, context: ExecutionContext) -> SandboxAdmissionGrant:
        """Validate entitlement freshness and install/renew one Runtime grant."""

        resolver = getattr(self.ap, 'entitlement_resolver', None)
        if resolver is None:
            raise EntitlementUnavailableError('Workspace entitlement resolver is unavailable')
        if context.instance_uuid != resolver.instance_uuid:
            raise EntitlementUnavailableError('Workspace entitlement targets another LangBot instance')

        lock = self._workspace_lock(context.workspace_uuid)
        async with lock:
            try:
                snapshot = await resolver.resolve(
                    context.workspace_uuid,
                    minimum_revision=self._context_revision(context),
                    now=int(self._wall_time()),
                )
            except EntitlementUnavailableError as exc:
                # Only a verified, scoped snapshot can authoritatively revoke
                # a revision. Provider timeouts, malformed responses, and
                # rollback/equivocation errors fail this request closed but do
                # not tombstone a still-valid revision forever.
                authoritative_revision = exc.entitlement_revision
                if authoritative_revision is not None:
                    await self._revoke_locked(
                        context,
                        candidate_revision=authoritative_revision,
                    )
                raise

            try:
                self._require_managed_sandbox(snapshot)
            except EntitlementUnavailableError:
                await self._revoke_locked(
                    context,
                    candidate_revision=snapshot.entitlement_revision,
                )
                raise

            grant = SandboxAdmissionGrant(
                instance_uuid=context.instance_uuid,
                workspace_uuid=context.workspace_uuid,
                execution_generation=context.placement_generation,
                entitlement_revision=snapshot.entitlement_revision,
                expires_at=self._grant_expiry(snapshot),
                max_sessions=1,
                max_managed_processes=0,
            )
            result = await self.client.upsert_sandbox_admission_grant(grant)
            if (
                not isinstance(result, dict)
                or result.get('installed') is not True
                or result.get('workspace_uuid') != context.workspace_uuid
                or result.get('execution_generation') != context.placement_generation
                or result.get('entitlement_revision') != snapshot.entitlement_revision
                or result.get('max_sessions') != 1
                or result.get('max_managed_processes') != 0
            ):
                raise BoxRuntimeUnavailableError('Box Runtime returned an invalid sandbox admission receipt')
            self._highest_revisions[context.workspace_uuid] = max(
                self._highest_revisions.get(context.workspace_uuid, 0),
                snapshot.entitlement_revision,
            )
            return grant

    async def revoke(self, context: ExecutionContext, *, entitlement_revision: int = 0) -> None:
        """Explicitly revoke a Workspace grant using a monotonic tombstone."""

        async with self._workspace_lock(context.workspace_uuid):
            await self._revoke_locked(context, candidate_revision=entitlement_revision)


def require_cloud_admission_policy(raw_policy: object) -> SandboxAdmissionPolicy:
    """Parse the Cloud Box policy without permitting an OSS downgrade."""

    try:
        policy = SandboxAdmissionPolicy.model_validate(raw_policy)
    except Exception as exc:
        raise BoxAdmissionError('Cloud Box sandbox admission policy is invalid') from exc
    if not policy.required:
        raise BoxAdmissionError('Cloud Box sandbox admission must be required')
    if policy.logical_session_id != 'global':
        raise BoxAdmissionError('Cloud Box sandbox session ID must be global')
    if policy.required_backend != 'nsjail':
        raise BoxAdmissionError('Cloud Box sandbox backend must be nsjail')
    if policy.max_sessions != 1 or policy.max_managed_processes != 0:
        raise BoxAdmissionError('Cloud Box sandbox policy must allow one session and zero managed processes')
    if policy.max_grant_ttl_sec > _MAX_GRANT_TTL_SEC:
        raise BoxAdmissionError('Cloud Box sandbox admission grant TTL must not exceed 300 seconds')
    if policy.workspace_quota_mb <= 0:
        raise BoxAdmissionError('Cloud Box sandbox workspace quota must be a positive integer')
    return policy
