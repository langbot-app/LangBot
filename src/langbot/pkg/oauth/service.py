"""Device-bound OAuth password, refresh, handoff and revocation services."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid

import jwt
import sqlalchemy as sa
from cryptography.fernet import Fernet

from ..api.authz import permissions_for_role
from ..api.http.service.totp import _derive_wrapping_key
from ..entity.persistence.harness_oauth import HarnessDevice
from ..entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from ..utils import constants
from .entities import OAuthClient, OAuthGrant, OAuthHandoffTicket, OAuthPendingState
from .errors import OAuthError, TotpHandoffRequired
from .policy import OAuthPolicy, SCOPE_PERMISSIONS

ACCESS_TTL = 3600
REFRESH_TTL = 180 * 24 * 3600
HANDOFF_TTL = 5 * 60
ALLOWED_SCOPES = frozenset(SCOPE_PERMISSIONS)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class OAuthService:
    def __init__(self, ap):
        self.ap = ap
        self.engine = ap.persistence_mgr.get_db_engine()
        self.instance_uuid = constants.instance_id
        self.policy = OAuthPolicy(ap)

    def _jwt_secret(self) -> str:
        return self.ap.instance_config.data['system']['jwt']['secret']

    async def token(self, payload: dict) -> dict:
        grant_type = payload.get('grant_type')
        if grant_type == 'password':
            return await self.password_grant(payload)
        if grant_type == 'refresh_token':
            return await self.refresh_grant(payload.get('refresh_token', ''))
        if grant_type == 'totp_handoff':
            return await self.complete_handoff(payload)
        raise OAuthError('unsupported_grant_type')

    async def password_grant(self, payload: dict) -> dict:
        required = ('binding_id', 'device_id', 'username', 'password', 'workspace_uuid')
        if any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
            raise OAuthError('invalid_request')
        binding_id, device_id = payload['binding_id'], payload['device_id']
        if not await self.policy.pending_device(binding_id, device_id, self.instance_uuid):
            raise OAuthError('invalid_device', 401)
        email = payload['username']
        try:
            await self.ap.user_service.authenticate(email, payload['password'], payload.get('totp_code'))
        except Exception as exc:
            if exc.__class__.__name__ == 'TotpRequiredError':
                challenge = await self.ap.user_service.issue_totp_login_challenge(email)
                account = await self.ap.user_service.get_user_by_email(email)
                if not challenge or account is None:
                    raise OAuthError('invalid_grant', 401) from exc
                ticket = await self._create_handoff(payload, account.uuid, challenge)
                raise TotpHandoffRequired(ticket) from exc
            if 'TotpInvalidCodeError' == exc.__class__.__name__:
                raise OAuthError('totp_invalid_code', 401) from exc
            raise OAuthError('invalid_grant', 401) from exc
        account = await self.ap.user_service.get_user_by_email(email)
        if account is None:
            raise OAuthError('invalid_grant', 401)
        return await self._issue_for_account(payload, account)

    async def _create_handoff(self, payload: dict, account_uuid: str, challenge: str) -> str:
        now = int(time.time())
        state = secrets.token_urlsafe(32)
        ticket = secrets.token_urlsafe(32)
        pending_id = str(uuid.uuid4())
        ticket_id = str(uuid.uuid4())
        scopes = self._requested_scopes(payload.get('scope', 'agent.run resource.view'))
        wrapping = _derive_wrapping_key(self._jwt_secret(), 1)
        ciphertext = Fernet(wrapping).encrypt(challenge.encode()).decode()
        async with self.engine.begin() as conn:
            await conn.execute(
                OAuthPendingState.__table__.insert().values(
                    id=pending_id,
                    state_hash=_hash(state),
                    binding_id=payload['binding_id'],
                    device_id=payload['device_id'],
                    workspace_uuid=payload['workspace_uuid'],
                    scope=' '.join(scopes),
                    expires_at=now + HANDOFF_TTL,
                )
            )
            await conn.execute(
                OAuthHandoffTicket.__table__.insert().values(
                    id=ticket_id,
                    ticket_hash=_hash(ticket),
                    pending_state_id=pending_id,
                    account_uuid=account_uuid,
                    challenge_ciphertext=ciphertext,
                    expires_at=now + HANDOFF_TTL,
                )
            )
        return ticket

    async def complete_handoff(self, payload: dict) -> dict:
        ticket, code = payload.get('handoff_ticket'), payload.get('totp_code')
        if not isinstance(ticket, str) or not isinstance(code, str) or not ticket or not code:
            raise OAuthError('invalid_request')
        now = int(time.time())
        async with self.engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        sa.select(OAuthHandoffTicket.__table__, OAuthPendingState.__table__)
                        .join(OAuthPendingState, OAuthPendingState.id == OAuthHandoffTicket.pending_state_id)
                        .where(
                            OAuthHandoffTicket.ticket_hash == _hash(ticket),
                            OAuthHandoffTicket.consumed_at.is_(None),
                            OAuthHandoffTicket.expires_at > now,
                            OAuthPendingState.consumed_at.is_(None),
                            OAuthPendingState.expires_at > now,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise OAuthError('invalid_handoff_ticket', 401)
            ticket_row = {key: row[key] for key in OAuthHandoffTicket.__table__.columns.keys()}
            pending = {key: row[key] for key in OAuthPendingState.__table__.columns.keys()}
            await conn.execute(
                OAuthHandoffTicket.__table__.update()
                .where(OAuthHandoffTicket.id == ticket_row['id'])
                .values(consumed_at=now)
            )
            await conn.execute(
                OAuthPendingState.__table__.update()
                .where(OAuthPendingState.id == pending['id'])
                .values(consumed_at=now)
            )
        challenge = (
            Fernet(_derive_wrapping_key(self._jwt_secret(), 1))
            .decrypt(ticket_row['challenge_ciphertext'].encode())
            .decode()
        )
        account = await self.ap.user_service.get_user_by_uuid(ticket_row['account_uuid'])
        if account is None or not await self.ap.user_service.verify_totp_second_factor(
            account.user, code, challenge_token=challenge
        ):
            raise OAuthError('totp_invalid_code', 401)
        params = {
            'binding_id': pending['binding_id'],
            'device_id': pending['device_id'],
            'workspace_uuid': pending['workspace_uuid'],
            'scope': pending['scope'],
        }
        return await self._issue_for_account(params, account)

    @staticmethod
    def _requested_scopes(raw) -> list[str]:
        if not isinstance(raw, str):
            raise OAuthError('invalid_scope')
        scopes = sorted(set(raw.split()) & ALLOWED_SCOPES)
        if not scopes:
            raise OAuthError('invalid_scope')
        return scopes

    async def _issue_for_account(self, payload: dict, account) -> dict:
        workspace_uuid = payload['workspace_uuid']
        try:
            access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                account.uuid, workspace_uuid
            )
        except Exception as exc:
            raise OAuthError('workspace_forbidden', 403) from exc
        scopes = self._requested_scopes(payload.get('scope', 'agent.run resource.view'))
        role_permissions = permissions_for_role(access.membership.role)
        scopes = [scope for scope in scopes if SCOPE_PERMISSIONS[scope] in role_permissions]
        if not scopes:
            raise OAuthError('insufficient_scope', 403)
        binding_id, device_id = payload['binding_id'], payload['device_id']
        if not await self.policy.pending_device(binding_id, device_id, self.instance_uuid):
            # Existing account-bound devices refresh/login only through a live binding.
            if not await self.policy.live_device_binding(binding_id, device_id, self.instance_uuid):
                raise OAuthError('invalid_device', 401)
        now = int(time.time())
        async with self.engine.begin() as conn:
            link = (
                (
                    await conn.execute(
                        sa.select(HarnessRegistrationLink.__table__).where(
                            HarnessRegistrationLink.id == binding_id,
                            HarnessRegistrationLink.instance_uuid == self.instance_uuid,
                            HarnessRegistrationLink.consumed_at.is_not(None),
                            HarnessRegistrationLink.revoked_at.is_(None),
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if link is None:
                raise OAuthError('invalid_binding', 401)
            if await conn.scalar(sa.select(HarnessBinding.id).where(HarnessBinding.id == binding_id)) is None:
                await conn.execute(
                    HarnessBinding.__table__.insert().values(
                        id=binding_id,
                        instance_uuid=self.instance_uuid,
                        issuer_workspace_uuid=link['issuer_workspace_uuid'],
                        created_at=now,
                    )
                )
            client_id = await conn.scalar(
                sa.select(OAuthClient.id).where(
                    OAuthClient.binding_id == binding_id,
                    OAuthClient.device_id == device_id,
                    OAuthClient.revoked_at.is_(None),
                )
            )
            if client_id is None:
                client_id = str(uuid.uuid4())
                await conn.execute(
                    OAuthClient.__table__.insert().values(
                        id=client_id, binding_id=binding_id, device_id=device_id, created_at=now
                    )
                )
            await conn.execute(
                HarnessDevice.__table__.update()
                .where(HarnessDevice.id == device_id, HarnessDevice.binding_id == binding_id)
                .values(account_uuid=account.uuid)
            )
        return await self._mint_grant(client_id, binding_id, device_id, account.uuid, workspace_uuid, scopes, now=now)

    async def _mint_grant(self, client_id, binding_id, device_id, account_uuid, workspace_uuid, scopes, *, now=None):
        now = int(time.time()) if now is None else now
        grant_id = str(uuid.uuid4())
        refresh = 'or_' + secrets.token_urlsafe(48)
        async with self.engine.begin() as conn:
            await conn.execute(
                OAuthGrant.__table__.insert().values(
                    id=grant_id,
                    client_id=client_id,
                    binding_id=binding_id,
                    device_id=device_id,
                    account_uuid=account_uuid,
                    workspace_uuid=workspace_uuid,
                    scope=' '.join(scopes),
                    refresh_token_hash=_hash(refresh),
                    refresh_history='[]',
                    refresh_expires_at=now + REFRESH_TTL,
                    created_at=now,
                )
            )
        access_token = jwt.encode(
            {
                'typ': 'langbot_oauth_at',
                'sub': account_uuid,
                'ws': workspace_uuid,
                'bid': binding_id,
                'cid': client_id,
                'dev': device_id,
                'scp': scopes,
                'gid': grant_id,
                'iss': self.instance_uuid,
                'iat': now,
                'exp': now + ACCESS_TTL,
            },
            self._jwt_secret(),
            algorithm='HS256',
        )
        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TTL,
            'refresh_token': refresh,
            'scope': ' '.join(scopes),
        }

    async def refresh_grant(self, refresh_token: str) -> dict:
        if not isinstance(refresh_token, str) or not refresh_token:
            raise OAuthError('invalid_grant', 401)
        now, token_hash = int(time.time()), _hash(refresh_token)
        reused = False
        async with self.engine.begin() as conn:
            row = (
                (
                    await conn.execute(
                        sa.select(OAuthGrant.__table__)
                        .where(
                            sa.or_(
                                OAuthGrant.refresh_token_hash == token_hash,
                                OAuthGrant.refresh_history.contains(token_hash),
                            )
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None or row['revoked_at'] is not None or row['refresh_expires_at'] <= now:
                raise OAuthError('invalid_grant', 401)
            history = json.loads(row['refresh_history'] or '[]')
            if token_hash in history:
                await conn.execute(
                    OAuthGrant.__table__.update().where(OAuthGrant.id == row['id']).values(revoked_at=now)
                )
                reused = True
            else:
                if not await self.policy.live_device_binding(
                    row['binding_id'], row['device_id'], self.instance_uuid, row['client_id']
                ):
                    raise OAuthError('invalid_grant', 401)
                effective = await self.policy.effective_permissions(
                    row['account_uuid'],
                    row['workspace_uuid'],
                    row['scope'].split(),
                    row['binding_id'],
                    row['device_id'],
                    self.instance_uuid,
                    row['client_id'],
                )
                scopes = [scope for scope in row['scope'].split() if SCOPE_PERMISSIONS.get(scope) in effective]
                if not scopes:
                    raise OAuthError('insufficient_scope', 403)
                history.append(token_hash)
                new_refresh = 'or_' + secrets.token_urlsafe(48)
                await conn.execute(
                    OAuthGrant.__table__.update()
                    .where(OAuthGrant.id == row['id'])
                    .values(
                        refresh_token_hash=_hash(new_refresh),
                        refresh_history=json.dumps(history),
                        scope=' '.join(scopes),
                    )
                )
                row = dict(row)
                row['scope'] = ' '.join(scopes)
        if reused:
            raise OAuthError('refresh_token_reuse', 401)
        await self._validate_grant_binding(row)
        token = self._mint_access(row, now)
        return self._token_response(token, new_refresh, row['scope'])

    async def _validate_grant_binding(self, row):
        if not await self.policy.live_device_binding(
            row['binding_id'], row['device_id'], self.instance_uuid, row['client_id']
        ):
            raise OAuthError('invalid_grant', 401)

    def _mint_access(self, row, now):
        return jwt.encode(
            {
                'typ': 'langbot_oauth_at',
                'sub': row['account_uuid'],
                'ws': row['workspace_uuid'],
                'bid': row['binding_id'],
                'cid': row['client_id'],
                'dev': row['device_id'],
                'scp': row['scope'].split(),
                'gid': row['id'],
                'iss': self.instance_uuid,
                'iat': now,
                'exp': now + ACCESS_TTL,
            },
            self._jwt_secret(),
            algorithm='HS256',
        )

    @staticmethod
    def _token_response(token, refresh, scope):
        return {
            'access_token': token,
            'token_type': 'Bearer',
            'expires_in': ACCESS_TTL,
            'refresh_token': refresh,
            'scope': scope,
        }

    async def revoke(self, token: str) -> bool:
        if not isinstance(token, str) or not token:
            raise OAuthError('invalid_request')
        now = int(time.time())
        token_hash = _hash(token)
        try:
            claims = jwt.decode(
                token,
                self._jwt_secret(),
                algorithms=['HS256'],
                issuer=self.instance_uuid,
                options={'require': ['exp', 'iss', 'gid']},
            )
            grant_id = claims['gid']
        except Exception:
            grant_id = None
        async with self.engine.begin() as conn:
            statement = sa.update(OAuthGrant).where(OAuthGrant.revoked_at.is_(None))
            if grant_id:
                statement = statement.where(OAuthGrant.id == grant_id)
            else:
                statement = statement.where(
                    sa.or_(
                        OAuthGrant.refresh_token_hash == token_hash,
                        OAuthGrant.refresh_history.contains(token_hash),
                    )
                )
            result = await conn.execute(statement.values(revoked_at=now))
        return result.rowcount == 1

    async def validate_access_token(self, token: str, workspace_uuid: str | None = None) -> dict:
        try:
            claims = jwt.decode(
                token,
                self._jwt_secret(),
                algorithms=['HS256'],
                issuer=self.instance_uuid,
                options={'require': ['exp', 'iss', 'sub', 'ws', 'bid', 'cid', 'dev', 'scp', 'gid']},
            )
        except Exception as exc:
            raise OAuthError('invalid_token', 401) from exc
        if claims.get('typ') != 'langbot_oauth_at' or (workspace_uuid is not None and workspace_uuid != claims['ws']):
            raise OAuthError('workspace_forbidden', 403)
        async with self.engine.connect() as conn:
            grant = await conn.scalar(
                sa.select(OAuthGrant.id).where(
                    OAuthGrant.id == claims['gid'],
                    OAuthGrant.client_id == claims['cid'],
                    OAuthGrant.account_uuid == claims['sub'],
                    OAuthGrant.workspace_uuid == claims['ws'],
                    OAuthGrant.binding_id == claims['bid'],
                    OAuthGrant.device_id == claims['dev'],
                    OAuthGrant.revoked_at.is_(None),
                )
            )
        if grant is None:
            raise OAuthError('invalid_grant', 401)
        permissions = await self.policy.effective_permissions(
            claims['sub'],
            claims['ws'],
            claims['scp'],
            claims['bid'],
            claims['dev'],
            self.instance_uuid,
            claims['cid'],
        )
        if not permissions:
            raise OAuthError('insufficient_scope', 403)
        return claims
