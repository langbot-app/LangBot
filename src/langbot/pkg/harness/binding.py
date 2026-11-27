"""Issue and atomically redeem instance enrollment links on self-hosted instances."""

import base64
import hashlib
import json
import re
import secrets
import time
import uuid
from urllib.parse import urlsplit

import sqlalchemy as sa
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..api.http.service.totp import _derive_wrapping_key
from ..entity.persistence.harness_instance_key import HarnessInstanceKey
from ..entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from ..utils import constants

_LINK = HarnessRegistrationLink.__table__
_BINDING = HarnessBinding.__table__
_KEY = HarnessInstanceKey.__table__
_TOKEN_PATTERN = re.compile(r'[A-Za-z0-9_-]{43}')
_LINK_TTL = 1800


def _b64(value):
    return base64.b64encode(value).decode('ascii')


def _digest(token):
    return hashlib.sha256(token.encode('ascii')).hexdigest()


def _https_origin(value):
    if not isinstance(value, str) or any(ord(c) <= 32 or c == '\\' for c in value):
        raise ValueError('invalid Harness origin')
    url = urlsplit(value)
    port = url.port
    if (
        url.scheme != 'https'
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.path not in ('', '/')
        or url.query
        or url.fragment
    ):
        raise ValueError('invalid Harness origin')
    host = url.hostname
    if ':' in host:
        host = f'[{host}]'
    return f'https://{host}' + (f':{port}' if port not in (None, 443) else '')


class HarnessBindings:
    def __init__(self, ap):
        config = ap.instance_config.data.get('harness', {})
        self.instance_uuid = constants.instance_id
        if config.get('enabled') is not True or getattr(ap.deployment, 'mode', None) != 'oss' or not self.instance_uuid:
            raise ValueError('Harness registration unavailable')
        self.base_url = _https_origin(config.get('instance_origin'))
        self.client_origin = _https_origin(config.get('client_origin'))
        self.jwt_secret = ap.instance_config.data['system']['jwt']['secret']
        self.engine = ap.persistence_mgr.get_db_engine()

    async def _active_key(self, conn):
        statement = (
            sa.select(_KEY).where(_KEY.c.status == 'active').order_by(_KEY.c.created_at.desc(), _KEY.c.kid).limit(1)
        )
        row = (await conn.execute(statement)).mappings().one_or_none()
        if row is not None:
            return row
        agreement = x25519.X25519PrivateKey.generate()
        signing = ed25519.Ed25519PrivateKey.generate()
        bundle = json.dumps(
            {'x25519': _b64(agreement.private_bytes_raw()), 'ed25519': _b64(signing.private_bytes_raw())}
        )
        cipher = Fernet(_derive_wrapping_key(self.jwt_secret, 1)).encrypt(bundle.encode()).decode()
        insert = sqlite_insert if conn.dialect.name == 'sqlite' else pg_insert
        await conn.execute(
            insert(_KEY)
            .values(
                kid='harness-initial-v1',
                x25519_pub=_b64(agreement.public_key().public_bytes_raw()),
                ed25519_pub=_b64(signing.public_key().public_bytes_raw()),
                priv_ciphertext=cipher,
            )
            .on_conflict_do_nothing(index_elements=['kid'])
        )
        return (await conn.execute(statement)).mappings().one()

    async def issue(self, ctx, *, label, preferred_auth):
        token = secrets.token_urlsafe(32)
        link_id = str(uuid.uuid4())
        expires_at = int(time.time()) + _LINK_TTL
        # SQLite requires the first statement in a competing write transaction to
        # be a write; otherwise upgrading a stale read snapshot can fail busy.
        async with self.engine.begin() as conn:
            if conn.dialect.name == 'sqlite':
                await conn.exec_driver_sql('BEGIN IMMEDIATE')
            key = await self._active_key(conn)
            await conn.execute(
                _LINK.insert().values(
                    id=link_id,
                    token_hash=_digest(token),
                    instance_uuid=self.instance_uuid,
                    issuer_workspace_uuid=ctx.workspace_uuid,
                    created_by_account_uuid=ctx.account_uuid,
                    kid=key['kid'],
                    preferred_auth=preferred_auth,
                    expires_at=expires_at,
                )
            )
        payload = {
            'v': 1,
            'instance_uuid': self.instance_uuid,
            'base_url': self.base_url,
            'label': label,
            'kind': 'self',
            'kid': key['kid'],
            'pub_x25519': key['x25519_pub'],
            'pub_ed25519': key['ed25519_pub'],
            'token': token,
            'preferred_auth': preferred_auth,
            'exp': expires_at,
        }
        fragment = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip('=')
        fingerprint = hashlib.sha256(
            base64.b64decode(key['x25519_pub']) + base64.b64decode(key['ed25519_pub'])
        ).hexdigest()
        return {
            'id': link_id,
            'url': f'{self.client_origin}/register#{fragment}',
            'fingerprint': fingerprint,
            'expires_at': expires_at,
        }

    async def redeem(self, token):
        if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
            return None
        now = int(time.time())
        binding_id = str(uuid.uuid4())
        async with self.engine.begin() as conn:
            result = await conn.execute(
                _LINK.update()
                .where(
                    _LINK.c.token_hash == _digest(token),
                    _LINK.c.instance_uuid == self.instance_uuid,
                    _LINK.c.revoked_at.is_(None),
                    _LINK.c.consumed_at.is_(None),
                    _LINK.c.expires_at > now,
                    sa.exists(sa.select(_KEY.c.kid).where(_KEY.c.kid == _LINK.c.kid, _KEY.c.status == 'active')),
                )
                .values(consumed_at=now)
                .returning(_LINK.c.issuer_workspace_uuid)
            )
            issuer = result.scalar_one_or_none()
            if issuer is None:
                return None
            await conn.execute(
                _BINDING.insert().values(
                    id=binding_id, instance_uuid=self.instance_uuid, issuer_workspace_uuid=issuer, created_at=now
                )
            )
        return {'harness_id': binding_id, 'instance_uuid': self.instance_uuid}

    def _managed(self, table, ctx):
        return (
            table.c.instance_uuid == self.instance_uuid,
            table.c.issuer_workspace_uuid == ctx.workspace_uuid,
            table.c.revoked_at.is_(None),
        )

    async def list_active(self, ctx, *, links):
        table = _LINK if links else _BINDING
        filters = self._managed(table, ctx)
        if links:
            statement = sa.select(table.c.id, table.c.expires_at, table.c.preferred_auth).where(
                *filters, table.c.consumed_at.is_(None), table.c.expires_at > int(time.time())
            )
            statement = statement.order_by(table.c.expires_at.desc(), table.c.id)
        else:
            statement = sa.select(table.c.id, table.c.created_at).where(*filters)
            statement = statement.order_by(table.c.created_at.desc(), table.c.id)
        async with self.engine.connect() as conn:
            return [dict(row) for row in (await conn.execute(statement.limit(100))).mappings()]

    async def revoke(self, ctx, target_id, *, links):
        table = _LINK if links else _BINDING
        filters = self._managed(table, ctx)
        if links:
            filters += (table.c.consumed_at.is_(None),)
        async with self.engine.begin() as conn:
            result = await conn.execute(
                table.update().where(*filters, table.c.id == target_id).values(revoked_at=int(time.time()))
            )
            return result.rowcount == 1
