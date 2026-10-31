from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re
import time
import typing

import jwt
from sqlalchemy.exc import IntegrityError

from ..entity.persistence.support_admin import SupportAdminTemporarySession
from ..workspace.errors import WorkspaceError

if typing.TYPE_CHECKING:
    from ..core.app import Application


SUPPORT_ADMIN_TOKEN_TYP = 'langbot-support-admin+jwt'
SUPPORT_ADMIN_TOKEN_KIND = 'support_admin.session'
SUPPORT_ADMIN_EFFECTIVE_ROLE = 'owner'
SUPPORT_ADMIN_MAX_TOKEN_SECONDS = 300
_SHA256_HEX = re.compile(r'^[0-9a-f]{64}$')


class SupportAdminSessionError(ValueError):
    """Raised when a support-admin session or token is not admissible."""


class SupportAdminReplayError(SupportAdminSessionError):
    """Raised when a launch grant JTI has already been consumed."""


@dataclasses.dataclass(frozen=True, slots=True)
class IssuedSupportAdminSession:
    token: str
    grant_jti_hash: str
    workspace_uuid: str
    actor_account_uuid: str
    issued_at: datetime.datetime
    expires_at: datetime.datetime


@dataclasses.dataclass(frozen=True, slots=True)
class SupportAdminSessionIdentity:
    grant_jti_hash: str
    workspace_uuid: str
    actor_account_uuid: str
    instance_uuid: str
    placement_generation: int


def hash_grant_jti(jti: str) -> str:
    return hashlib.sha256(jti.encode('utf-8')).hexdigest()


class SupportAdminSessionService:
    """Issue and validate temporary Workspace-scoped support-admin sessions."""

    def __init__(
        self,
        ap: Application,
        *,
        wall_time: typing.Callable[[], float] = time.time,
    ) -> None:
        self.ap = ap
        self._wall_time = wall_time

    async def consume_launch_grant(
        self,
        *,
        grant_jti_hash: str,
        workspace_uuid: str,
        actor_account_uuid: str,
    ) -> IssuedSupportAdminSession:
        self._validate_grant_hash(grant_jti_hash)
        if not workspace_uuid or not actor_account_uuid:
            raise SupportAdminSessionError('Support admin session requires an actor and Workspace')

        issued_at = self._utcnow()
        expires_at = issued_at + datetime.timedelta(seconds=SUPPORT_ADMIN_MAX_TOKEN_SECONDS)
        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if not callable(tenant_uow):
            raise SupportAdminSessionError('Support admin sessions require tenant persistence')

        try:
            async with tenant_uow(workspace_uuid) as uow:
                await self.ap.workspace_service.get_execution_binding(workspace_uuid, session=uow.session)
                uow.session.add(
                    SupportAdminTemporarySession(
                        grant_jti_hash=grant_jti_hash,
                        workspace_uuid=workspace_uuid,
                        actor_account_uuid=actor_account_uuid,
                        issued_at=issued_at,
                        expires_at=expires_at,
                    )
                )
                await uow.session.flush()
        except IntegrityError as exc:
            raise SupportAdminReplayError('Launch assertion has already been consumed') from exc
        except WorkspaceError as exc:
            raise SupportAdminSessionError('Workspace is unavailable for support access') from exc

        return IssuedSupportAdminSession(
            token=self._encode_token(
                grant_jti_hash=grant_jti_hash,
                workspace_uuid=workspace_uuid,
                actor_account_uuid=actor_account_uuid,
                issued_at=issued_at,
                expires_at=expires_at,
            ),
            grant_jti_hash=grant_jti_hash,
            workspace_uuid=workspace_uuid,
            actor_account_uuid=actor_account_uuid,
            issued_at=issued_at,
            expires_at=expires_at,
        )

    def is_support_admin_token(self, token: str) -> bool:
        """Return True only for compact JWTs marked as support-admin tokens."""

        if not isinstance(token, str) or token.count('.') != 2:
            return False
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return False
        if header.get('typ') == SUPPORT_ADMIN_TOKEN_TYP:
            return True
        try:
            payload = jwt.decode(token, options={'verify_signature': False})
        except jwt.PyJWTError:
            return False
        return payload.get('kind') == SUPPORT_ADMIN_TOKEN_KIND

    async def authenticate_token(
        self,
        token: str,
        *,
        requested_workspace_uuid: str | None,
    ) -> SupportAdminSessionIdentity:
        if not self.is_support_admin_token(token):
            raise SupportAdminSessionError('Not a support admin token')
        workspace_uuid = (requested_workspace_uuid or '').strip()
        if not workspace_uuid:
            raise SupportAdminSessionError('Support admin token requires an explicit Workspace selector')

        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']
        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=['HS256'],
                issuer='langbot-core',
                audience=self._audience(workspace_uuid),
                options={'require': ['exp', 'iat', 'nbf', 'iss', 'aud']},
            )
        except jwt.PyJWTError as exc:
            raise SupportAdminSessionError('Invalid support admin token') from exc
        self._validate_payload(payload, workspace_uuid)
        grant_jti_hash = payload['grant_jti_hash']
        actor_account_uuid = payload['actor_account_uuid']

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if not callable(tenant_uow):
            raise SupportAdminSessionError('Support admin sessions require tenant persistence')

        now = self._utcnow()
        async with tenant_uow(workspace_uuid) as uow:
            session = await uow.session.get(SupportAdminTemporarySession, grant_jti_hash)
            if (
                session is None
                or session.workspace_uuid != workspace_uuid
                or session.actor_account_uuid != actor_account_uuid
                or session.revoked_at is not None
                or session.expires_at <= now
            ):
                raise SupportAdminSessionError('Support admin session is inactive')
            binding = await self.ap.workspace_service.get_execution_binding(workspace_uuid, session=uow.session)
            session.last_used_at = now
            await uow.session.flush()

        return SupportAdminSessionIdentity(
            grant_jti_hash=grant_jti_hash,
            workspace_uuid=workspace_uuid,
            actor_account_uuid=actor_account_uuid,
            instance_uuid=binding.instance_uuid,
            placement_generation=binding.placement_generation,
        )

    async def revoke_session(self, grant_jti_hash: str, workspace_uuid: str) -> None:
        self._validate_grant_hash(grant_jti_hash)
        now = self._utcnow()
        async with self.ap.persistence_mgr.tenant_uow(workspace_uuid) as uow:
            row = await uow.session.get(SupportAdminTemporarySession, grant_jti_hash)
            if row is not None and row.revoked_at is None:
                row.revoked_at = now

    def _encode_token(
        self,
        *,
        grant_jti_hash: str,
        workspace_uuid: str,
        actor_account_uuid: str,
        issued_at: datetime.datetime,
        expires_at: datetime.datetime,
    ) -> str:
        jwt_secret = self.ap.instance_config.data['system']['jwt']['secret']
        payload: dict[str, typing.Any] = {
            'kind': SUPPORT_ADMIN_TOKEN_KIND,
            'iss': 'langbot-core',
            'aud': self._audience(workspace_uuid),
            'sub': f'support-admin:{actor_account_uuid}',
            'iat': issued_at,
            'nbf': issued_at,
            'exp': expires_at,
            'actor_account_uuid': actor_account_uuid,
            'workspace_uuid': workspace_uuid,
            'effective_role': SUPPORT_ADMIN_EFFECTIVE_ROLE,
            'grant_jti_hash': grant_jti_hash,
        }
        return jwt.encode(payload, jwt_secret, algorithm='HS256', headers={'typ': SUPPORT_ADMIN_TOKEN_TYP})

    def _validate_payload(self, payload: dict[str, typing.Any], workspace_uuid: str) -> None:
        if payload.get('kind') != SUPPORT_ADMIN_TOKEN_KIND:
            raise SupportAdminSessionError('Invalid support admin token kind')
        if payload.get('workspace_uuid') != workspace_uuid:
            raise SupportAdminSessionError('Support admin session is scoped to another Workspace')
        if payload.get('effective_role') != SUPPORT_ADMIN_EFFECTIVE_ROLE:
            raise SupportAdminSessionError('Invalid support admin token role')
        actor_account_uuid = payload.get('actor_account_uuid')
        if not isinstance(actor_account_uuid, str) or not actor_account_uuid.strip():
            raise SupportAdminSessionError('Invalid support admin actor')
        grant_jti_hash = payload.get('grant_jti_hash')
        if not isinstance(grant_jti_hash, str) or not _SHA256_HEX.match(grant_jti_hash):
            raise SupportAdminSessionError('Invalid support admin grant')

    def _audience(self, workspace_uuid: str) -> str:
        return f'langbot-support-admin:{self.ap.workspace_service.instance_uuid}:{workspace_uuid}'

    @staticmethod
    def _validate_grant_hash(grant_jti_hash: str) -> None:
        if not _SHA256_HEX.match(grant_jti_hash):
            raise SupportAdminSessionError('Invalid support admin grant')

    def _utcnow(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self._wall_time(), datetime.UTC).replace(tzinfo=None)
