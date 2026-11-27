"""Device enrollment and scoped OAuth service for Harness."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid

import jwt
import sqlalchemy as sa

from ..api.authz import permissions_for_role
from ..entity.persistence.harness_oauth import HarnessDevice, HarnessOAuthGrant
from ..entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from ..utils import constants

ACCESS_TTL = 3600
REFRESH_TTL = 180 * 24 * 3600
SCOPES = frozenset({'workspace.view', 'resource.view', 'resource.manage', 'member.view', 'agent.run'})
SCOPE_PERMISSIONS = {
    'workspace.view': 'workspace.view',
    'resource.view': 'resource.view',
    'resource.manage': 'resource.manage',
    'member.view': 'member.view',
    'agent.run': 'runtime.operate',
}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _key_bytes(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError('invalid device key') from exc
    if len(decoded) != 32:
        raise ValueError('invalid device key')
    return decoded


class HarnessOAuthService:
    def __init__(self, ap):
        self.ap = ap
        self.engine = ap.persistence_mgr.get_db_engine()
        self.instance_uuid = constants.instance_id

    async def register_device(self, binding_id: str, enrollment_token: str, payload: dict) -> dict:
        required = ('device_kid', 'x25519_pub', 'ed25519_pub')
        if not isinstance(payload, dict) or any(not isinstance(payload.get(k), str) for k in required):
            raise ValueError('device key is required')
        _key_bytes(payload['x25519_pub'])
        _key_bytes(payload['ed25519_pub'])
        device_id = str(uuid.uuid4())
        now = int(time.time())
        async with self.engine.begin() as conn:
            binding = await conn.execute(
                sa.select(HarnessRegistrationLink.id, HarnessRegistrationLink.token_hash)
                .where(
                    HarnessRegistrationLink.id == binding_id,
                    HarnessRegistrationLink.consumed_at.is_not(None),
                    HarnessRegistrationLink.revoked_at.is_(None),
                    HarnessRegistrationLink.instance_uuid == self.instance_uuid,
                )
            )
            record = binding.one_or_none()
            if record is None or not hmac.compare_digest(record.token_hash, _hash(enrollment_token)):
                return None
            consumed = await conn.execute(
                sa.update(HarnessRegistrationLink)
                .where(
                    HarnessRegistrationLink.id == binding_id,
                    HarnessRegistrationLink.token_hash == record.token_hash,
                    HarnessRegistrationLink.consumed_at.is_not(None),
                    HarnessRegistrationLink.revoked_at.is_(None),
                )
                # Keep the unique index valid when multiple pending enrollment
                # links are consumed for distinct devices.
                .values(token_hash=_hash(f'consumed:{binding_id}'))
            )
            if consumed.rowcount != 1:
                return None
            await conn.execute(
                HarnessDevice.__table__.insert().values(
                    id=device_id,
                    binding_id=binding_id,
                    device_kid=payload['device_kid'],
                    x25519_pub=payload['x25519_pub'],
                    ed25519_pub=payload['ed25519_pub'],
                    platform=str(payload.get('platform', 'unknown'))[:32],
                    created_at=now,
                )
            )
        return {'device_id': device_id, 'device_kid': payload['device_kid']}

    async def lookup_device(self, binding_id: str, device_kid: str) -> dict | None:
        async with self.engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        sa.select(HarnessDevice.__table__)
                        .where(
                            HarnessDevice.binding_id == binding_id,
                            HarnessDevice.device_kid == device_kid,
                            HarnessDevice.revoked_at.is_(None),
                            sa.exists(sa.select(HarnessRegistrationLink.id).where(
                                HarnessRegistrationLink.id == HarnessDevice.binding_id,
                                HarnessRegistrationLink.instance_uuid == self.instance_uuid,
                                HarnessRegistrationLink.consumed_at.is_not(None),
                                HarnessRegistrationLink.revoked_at.is_(None),
                            )),
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
        return dict(row) if row else None

    async def password_grant(self, binding_id: str, payload: dict) -> dict:
        if not isinstance(payload, dict) or payload.get('grant_type') != 'password':
            raise ValueError('unsupported_grant_type')
        email, password, device_id, workspace_uuid = (
            payload.get('username'),
            payload.get('password'),
            payload.get('device_id'),
            payload.get('workspace_uuid'),
        )
        if not all(isinstance(v, str) and v for v in (email, password, device_id, workspace_uuid)):
            raise ValueError('invalid_grant')
        async with self.engine.connect() as conn:
            device = (
                (
                    await conn.execute(
                        sa.select(HarnessDevice.__table__)
                        .where(
                            HarnessDevice.id == device_id,
                            HarnessDevice.binding_id == binding_id,
                            HarnessDevice.revoked_at.is_(None),
                            sa.exists(sa.select(HarnessRegistrationLink.id).where(
                                HarnessRegistrationLink.id == HarnessDevice.binding_id,
                                HarnessRegistrationLink.instance_uuid == self.instance_uuid,
                                HarnessRegistrationLink.consumed_at.is_not(None),
                                HarnessRegistrationLink.revoked_at.is_(None),
                            )),
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
        if device is None:
            raise ValueError('invalid_device')
        try:
            await self.ap.user_service.authenticate(email, password, payload.get('totp_code'))
        except Exception as exc:
            if exc.__class__.__name__ == 'TotpRequiredError':
                raise ValueError('interaction_required') from exc
            raise ValueError('invalid_grant') from exc
        account = await self.ap.user_service.get_user_by_email(email)
        if account is None or (device['account_uuid'] is not None and device['account_uuid'] != account.uuid):
            raise ValueError('invalid_grant')
        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(account.uuid, workspace_uuid)
        workspace_uuid = access.workspace.uuid
        raw_scope = payload.get('scope', 'workspace.view agent.run resource.view')
        if not isinstance(raw_scope, str):
            raise ValueError('invalid_scope')
        permissions = set(permissions_for_role(access.membership.role))
        scopes = sorted(scope for scope in set(raw_scope.split()) & SCOPES if SCOPE_PERMISSIONS[scope] in permissions)
        if not scopes:
            raise ValueError('insufficient_scope')
        # The instance link remains a pending enrollment until successful account
        # authentication and Workspace authorization. Only now create the durable
        # binding used by grants and management APIs.
        now = int(time.time())
        async with self.engine.begin() as conn:
            link = (
                await conn.execute(
                    sa.select(HarnessRegistrationLink.__table__).where(
                        HarnessRegistrationLink.id == binding_id,
                        HarnessRegistrationLink.instance_uuid == self.instance_uuid,
                        HarnessRegistrationLink.consumed_at.is_not(None),
                        HarnessRegistrationLink.revoked_at.is_(None),
                    )
                )
            ).mappings().one_or_none()
            if link is None:
                raise ValueError('invalid_binding')
            if device['account_uuid'] is not None:
                active = await conn.scalar(sa.select(HarnessBinding.id).where(
                    HarnessBinding.id == binding_id,
                    HarnessBinding.instance_uuid == self.instance_uuid,
                    HarnessBinding.revoked_at.is_(None),
                ).join(HarnessDevice, HarnessDevice.binding_id == HarnessBinding.id).where(
                    HarnessDevice.id == device_id, HarnessDevice.account_uuid == account.uuid,
                    HarnessDevice.revoked_at.is_(None),
                ))
                if active is None:
                    raise ValueError('invalid_device')
                return await self._issue_grant(conn, binding_id, device_id, account.uuid, workspace_uuid, scopes)
            claimed = await conn.execute(
                HarnessDevice.__table__.update()
                .where(
                    HarnessDevice.id == device_id,
                    HarnessDevice.binding_id == binding_id,
                    HarnessDevice.account_uuid.is_(None),
                    HarnessDevice.revoked_at.is_(None),
                )
                .values(account_uuid=account.uuid)
            )
            if claimed.rowcount != 1:
                raise ValueError('invalid_device')
            await conn.execute(
                HarnessBinding.__table__.insert().values(
                    id=binding_id,
                    instance_uuid=self.instance_uuid,
                    issuer_workspace_uuid=link['issuer_workspace_uuid'],
                    created_at=now,
                )
            )
            return await self._issue_grant(conn, binding_id, device_id, account.uuid, workspace_uuid, scopes)

    async def switch_workspace(self, account_uuid, binding_id, device_id, workspace_uuid):
        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(account_uuid, workspace_uuid)
        permissions = permissions_for_role(access.membership.role)
        if 'workspace.view' not in permissions:
            raise ValueError('workspace_forbidden')
        scopes = [scope for scope in ('workspace.view', 'agent.run', 'resource.view')
                  if SCOPE_PERMISSIONS[scope] in permissions]
        async with self.engine.begin() as conn:
            tokens = await self._issue_grant(conn, binding_id, device_id, account_uuid, access.workspace.uuid, scopes)
        return {**tokens, 'workspace_uuid': access.workspace.uuid}

    async def _issue_grant(self, conn, binding_id, device_id, account_uuid, workspace_uuid, scopes):
        now = int(time.time())
        refresh = 'hr_' + secrets.token_urlsafe(48)
        grant = {
            'id': str(uuid.uuid4()), 'binding_id': binding_id, 'device_id': device_id,
            'account_uuid': account_uuid, 'workspace_uuid': workspace_uuid, 'scope': ' '.join(scopes),
        }
        tokens = await self._mint_from_grant(grant, refresh)
        await conn.execute(HarnessOAuthGrant.__table__.insert().values(
            **grant, refresh_token_hash=_hash(refresh), refresh_expires_at=now + REFRESH_TTL, created_at=now,
        ))
        return tokens

    async def refresh_grant(self, refresh_token: str, *, binding_id: str, device_id: str) -> dict:
        now = int(time.time())
        token_hash = _hash(refresh_token)
        reused = False
        async with self.engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        sa.select(HarnessOAuthGrant.__table__)
                        .where(
                            HarnessOAuthGrant.binding_id == binding_id,
                            HarnessOAuthGrant.device_id == device_id,
                            sa.or_(
                                HarnessOAuthGrant.refresh_token_hash == token_hash,
                                HarnessOAuthGrant.previous_refresh_token_hash == token_hash,
                            )
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise ValueError('invalid_grant')
            if row['revoked_at'] is not None or row['refresh_expires_at'] <= now:
                raise ValueError('invalid_grant')
            # A previous token can only be observed when a rotated token was
            # replayed. Revoke the whole grant family before returning an
            # error; this invalidates every access token on the device at the
            # next request as well as the current refresh chain.
            if row['previous_refresh_token_hash'] == token_hash:
                await conn.execute(
                    HarnessOAuthGrant.__table__.update()
                    .where(HarnessOAuthGrant.id == row['id'])
                    .values(revoked_at=now)
                )
                reused = True
            else:
                binding = await conn.scalar(
                    sa.select(HarnessBinding.id).where(
                        HarnessBinding.id == row['binding_id'],
                        HarnessBinding.instance_uuid == self.instance_uuid,
                        HarnessBinding.revoked_at.is_(None),
                    )
                )
                device = await conn.scalar(
                    sa.select(HarnessDevice.id).where(
                        HarnessDevice.id == row['device_id'],
                        HarnessDevice.revoked_at.is_(None),
                    )
                )
                if binding is None or device is None:
                    raise ValueError('invalid_grant')
                account = await self.ap.user_service.get_user_by_uuid(row['account_uuid'])
                if account is None or account.status != 'active':
                    raise ValueError('invalid_grant')
                access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                    row['account_uuid'], row['workspace_uuid']
                )
                allowed = set(permissions_for_role(access.membership.role))
                scopes = [scope for scope in row['scope'].split() if SCOPE_PERMISSIONS.get(scope) in allowed]
                if not scopes:
                    raise ValueError('insufficient_scope')
                new_refresh = 'hr_' + secrets.token_urlsafe(48)
                updated = await conn.execute(
                    HarnessOAuthGrant.__table__.update()
                    .where(
                        HarnessOAuthGrant.id == row['id'],
                        HarnessOAuthGrant.refresh_token_hash == token_hash,
                        HarnessOAuthGrant.revoked_at.is_(None),
                    )
                    .values(
                        refresh_token_hash=_hash(new_refresh),
                        previous_refresh_token_hash=token_hash,
                        refresh_generation=row['refresh_generation'] + 1,
                        scope=' '.join(scopes),
                    )
                )
                if updated.rowcount != 1:
                    raise ValueError('invalid_grant')
                row = dict(row)
                row['scope'] = ' '.join(scopes)
        if reused:
            # Raise only after the transaction commits the revocation.
            raise ValueError('refresh_token_reuse')
        return await self._mint_from_grant(row, new_refresh)

    async def _mint_from_grant(self, row, refresh):
        now = int(time.time())
        scopes = row['scope'].split()
        token = jwt.encode(
            {
                'typ': 'langbot_harness_at',
                'gid': row['id'],
                'sub': row['account_uuid'],
                'ws': row['workspace_uuid'],
                'bid': row['binding_id'],
                'dev': row['device_id'],
                'scp': scopes,
                'iss': self.instance_uuid,
                'exp': now + ACCESS_TTL,
                'iat': now,
            },
            self.ap.instance_config.data['system']['jwt']['secret'],
            algorithm='HS256',
        )
        return {
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TTL,
            'refresh_token': refresh,
            'scope': ' '.join(scopes),
        }

    async def revoke_device(self, device_id: str, account_uuid: str) -> bool:
        """Revoke a device and all grants issued to it."""
        now = int(time.time())
        async with self.engine.begin() as conn:
            result = await conn.execute(
                HarnessDevice.__table__.update()
                .where(
                    HarnessDevice.id == device_id,
                    HarnessDevice.account_uuid == account_uuid,
                    HarnessDevice.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            if result.rowcount != 1:
                return False
            await conn.execute(
                HarnessOAuthGrant.__table__.update()
                .where(
                    HarnessOAuthGrant.device_id == device_id,
                    HarnessOAuthGrant.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        return True
