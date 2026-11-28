"""Password-proven browser TOTP approval and device-proven one-time redemption."""

import hashlib
import re
import secrets
import time

import sqlalchemy as sa

from ..api.authz import permissions_for_role
from ..api.http.service.totp import TotpError
from ..entity.persistence.harness_oauth import HarnessDevice, HarnessHandoff
from ..entity.persistence.harness_registration import HarnessRegistrationLink
from ..entity.persistence.totp import TotpCredential
from ..entity.persistence.user import User
from ..entity.persistence.workspace import Workspace, WorkspaceMembership
from .binding import _KEY, HarnessBindings, lock_keys
from .rotation import SERVING_KEY_STATES

TTL = 180
ATTEMPTS = 5
_T = HarnessHandoff.__table__
_LINK = HarnessRegistrationLink.__table__
_TICKET = re.compile(r'[A-Za-z0-9_-]{43}')


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class HandoffRequired(ValueError):
    def __init__(self, details):
        super().__init__('interaction_required')
        self.details = details


class HarnessHandoffs(HarnessBindings):
    def __init__(self, ap):
        super().__init__(ap)
        self.ap = ap

    async def issue(self, binding_id, device_id, account, workspace_uuid):
        access = await self.ap.workspace_collaboration_service.resolve_account_workspace(account.uuid, workspace_uuid)
        if 'workspace.view' not in permissions_for_role(access.membership.role):
            raise ValueError('workspace_forbidden')
        credential = await self.ap.totp_service.get_credential(account.uuid)
        if credential is None or credential.confirmed_at is None:
            raise ValueError('invalid_grant')
        ticket = secrets.token_urlsafe(32)
        async with self.engine.begin() as conn:
            await lock_keys(conn)
            now = int(time.time())
            await self._link(conn, binding_id, now)
            await conn.execute(sa.delete(_T).where(_T.c.expires_at <= now))
            if await conn.scalar(sa.select(_T.c.ticket_hash).where(_T.c.account_uuid == account.uuid)):
                # Do not reset the per-account guess budget by requesting a new ticket.
                raise ValueError('handoff_already_pending')
            await conn.execute(sa.insert(_T).values(
                ticket_hash=_digest(ticket), instance_uuid=self.instance_uuid, binding_id=binding_id,
                device_id=device_id, account_uuid=account.uuid, workspace_uuid=access.workspace.uuid,
                password_digest=_digest(account.password), credential_uuid=credential.uuid,
                expires_at=now + TTL, attempts=0, state='pending',
            ))
        return {'handoff_ticket': ticket, 'handoff_url': f'{self.base_url}/oauth/handoff?ticket={ticket}', 'expires_in': TTL}

    async def _link(self, conn, binding_id, now):
        row = (await conn.execute(sa.select(_LINK).where(
            _LINK.c.id == binding_id, _LINK.c.instance_uuid == self.instance_uuid,
            _LINK.c.preferred_auth.is_distinct_from('space'), _LINK.c.consumed_at.is_not(None),
            _LINK.c.revoked_at.is_(None), _LINK.c.expires_at > now,
        ).with_for_update())).mappings().one_or_none()
        if row is None:
            raise ValueError('invalid_grant')
        return row

    def _selector(self, ticket):
        if not isinstance(ticket, str) or not _TICKET.fullmatch(ticket):
            raise ValueError('invalid_grant')
        return (_T.c.ticket_hash == _digest(ticket), _T.c.instance_uuid == self.instance_uuid)

    async def preview(self, ticket):
        async with self.engine.connect() as conn:
            found = await conn.scalar(sa.select(_LINK.c.id).join(_T, _T.c.binding_id == _LINK.c.id).where(
                *self._selector(ticket), _T.c.state == 'pending', _T.c.attempts < ATTEMPTS,
                _T.c.expires_at > int(time.time()), _LINK.c.revoked_at.is_(None),
                _LINK.c.expires_at > int(time.time()),
            ))
            return self.base_url if found is not None else None

    async def decide(self, ticket, *, code=None):
        conditions = (*self._selector(ticket), _T.c.state == 'pending', _T.c.expires_at > int(time.time()))
        async with self.engine.begin() as conn:
            if code is None:
                result = await conn.execute(sa.update(_T).where(*conditions).values(state='cancelled'))
                return 'cancelled' if result.rowcount == 1 else 'unavailable'
            row = (await conn.execute(sa.update(_T).where(*conditions, _T.c.attempts < ATTEMPTS)
                    .values(attempts=_T.c.attempts + 1).returning(_T))).mappings().one_or_none()
        if row is None:
            return 'unavailable'
        account = await self.ap.user_service.get_user_by_uuid(row['account_uuid'])
        if account is None or account.status != 'active' or not account.password or (
            _digest(account.password) != row['password_digest']
        ):
            return 'unavailable'
        try:
            if not await self.ap.totp_service.verify_code(
                account.uuid, code, expected_credential_uuid=row['credential_uuid'],
            ):
                return 'invalid'
        except TotpError:
            return 'invalid'
        async with self.engine.begin() as conn:
            result = await conn.execute(sa.update(_T).where(*conditions, _T.c.expires_at > int(time.time()))
                                        .values(state='approved'))
            return 'approved' if result.rowcount == 1 else 'unavailable'

    async def poll(self, oauth, ticket, binding_id, device_id, kid):
        selector = (*self._selector(ticket), _T.c.binding_id == binding_id, _T.c.device_id == device_id)
        async with self.engine.connect() as conn:
            status = (await conn.execute(sa.select(_T.c.state, _T.c.expires_at).where(*selector))).first()
        if status is None or status.expires_at <= int(time.time()):
            raise ValueError('invalid_grant')
        if status.state == 'pending':
            raise ValueError('authorization_pending')
        if status.state != 'approved':
            raise ValueError('invalid_grant')
        async with self.engine.begin() as conn:
            await lock_keys(conn)
            now = int(time.time())
            row = (await conn.execute(sa.update(_T).where(*selector, _T.c.state == 'approved', _T.c.expires_at > now)
                    .values(state='redeemed').returning(_T))).mappings().one_or_none()
            if row is None:
                raise ValueError('invalid_grant')
            link = await self._link(conn, binding_id, now)
            for required_kid in {kid, link['kid']}:
                if not await conn.scalar(sa.select(_KEY.c.kid).where(_KEY.c.kid == required_kid,
                                                                    _KEY.c.status.in_(SERVING_KEY_STATES))):
                    raise ValueError('invalid_grant')
            user, workspace = row['account_uuid'], row['workspace_uuid']
            member = (await conn.execute(sa.select(WorkspaceMembership.role, User.password).join(
                User, User.uuid == WorkspaceMembership.account_uuid,
            ).join(Workspace, Workspace.uuid == WorkspaceMembership.workspace_uuid).join(
                TotpCredential, TotpCredential.account_uuid == User.uuid,
            ).where(
                User.uuid == user, User.status == 'active', Workspace.uuid == workspace,
                Workspace.instance_uuid == self.instance_uuid, Workspace.status == 'active',
                WorkspaceMembership.status == 'active', TotpCredential.uuid == row['credential_uuid'],
                TotpCredential.disabled_at.is_(None), TotpCredential.confirmed_at.is_not(None),
            ).with_for_update())).one_or_none()
            if member is None or not member.password or _digest(member.password) != row['password_digest']:
                raise ValueError('workspace_forbidden')
            from .oauth import SCOPE_PERMISSIONS

            permissions = permissions_for_role(member.role)
            scopes = [scope for scope in ('workspace.view', 'agent.run', 'resource.view')
                      if SCOPE_PERMISSIONS[scope] in permissions]
            if 'workspace.view' not in scopes:
                raise ValueError('workspace_forbidden')
            device = (await conn.execute(sa.select(HarnessDevice.__table__).where(
                HarnessDevice.id == device_id, HarnessDevice.binding_id == binding_id, HarnessDevice.revoked_at.is_(None),
            ).with_for_update())).mappings().one_or_none()
            if device is None or device['account_uuid'] not in (None, user):
                raise ValueError('invalid_grant')
            tokens = await oauth.finish_password_grant(conn, link, device, user, workspace, scopes, now)
        return {**tokens, 'workspace_uuid': workspace}
