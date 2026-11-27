"""Instance-wide Harness key lifecycle, shared by all transport workers."""

import base64
import datetime as dt
import hashlib
import json
import time
import uuid

import sqlalchemy as sa
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..entity.persistence.harness_instance_key import HarnessInstanceKey, HarnessKeyAck
from ..entity.persistence.harness_oauth import HarnessDevice
from ..entity.persistence.harness_registration import HarnessBinding
from .binding import HarnessBindings, _derive_wrapping_key, _KEY, lock_keys
from .crypto.keys import generate_key_material

_FIELDS = ('v', 'rotation_id', 'instance_uuid', 'base_url', 'old_kid', 'new_kid', 'pub_x25519', 'pub_ed25519', 'created_at')
_ACK = HarnessKeyAck.__table__
SERVING_KEY_STATES = ('active', 'overlap')


class RotationError(ValueError):
    pass


async def ensure_serving(engine, kid):
    async with engine.connect() as conn:
        status = await conn.scalar(sa.select(_KEY.c.status).where(_KEY.c.kid == kid))
    if status not in SERVING_KEY_STATES:
        raise RotationError('key_retired' if status == 'retired' else 'key_unavailable')


async def retire(conn, predicate):
    await conn.execute(_KEY.update().where(predicate).values(
        status='retired', retired_at=dt.datetime.now(dt.timezone.utc), priv_ciphertext='', transition=None,
    ))


async def finish_if_ready(conn, instance_uuid):
    old = (await conn.execute(sa.select(_KEY).where(_KEY.c.status == 'overlap'))).mappings().one_or_none()
    if old is None:
        return False
    rotation_id = old['transition']['fields']['rotation_id']
    pending = sa.select(HarnessDevice.id).join(HarnessBinding, HarnessBinding.id == HarnessDevice.binding_id).where(
        HarnessBinding.instance_uuid == instance_uuid, HarnessBinding.revoked_at.is_(None),
        HarnessDevice.revoked_at.is_(None),
        ~sa.exists(sa.select(_ACK.c.device_id).where(_ACK.c.rotation_id == rotation_id, _ACK.c.device_id == HarnessDevice.id)),
    )
    if await conn.scalar(sa.select(sa.exists(pending))):
        return False
    # Keep the public transition for idempotent ACK retries by enrolled devices.
    await conn.execute(_KEY.update().where(_KEY.c.kid == old['kid']).values(
        status='retired', retired_at=dt.datetime.now(dt.timezone.utc), priv_ciphertext='',
    ))
    return True


class HarnessKeyRotation:
    def __init__(self, ap):
        self.bindings = HarnessBindings(ap)
        self.engine = self.bindings.engine

    def _wrapping_key(self):
        return _derive_wrapping_key(self.bindings.jwt_secret, 1)

    async def plan(self, expected_kid):
        async with self.engine.begin() as conn:
            await lock_keys(conn)
            if await conn.scalar(sa.select(_KEY.c.kid).where(_KEY.c.status == 'overlap')):
                raise RotationError('rotation_pending')
            old = await self.bindings._active_key(conn)
            if old['kid'] != expected_kid:
                raise RotationError('key_changed')
            wrapping_key = self._wrapping_key()
            fresh = generate_key_material(wrapping_key)
            fields = dict(v=1, rotation_id=str(uuid.uuid4()), instance_uuid=self.bindings.instance_uuid,
                          base_url=self.bindings.base_url, old_kid=old['kid'], new_kid=fresh['kid'],
                          pub_x25519=fresh['x25519_pub'], pub_ed25519=fresh['ed25519_pub'], created_at=int(time.time()))
            private = json.loads(Fernet(wrapping_key).decrypt(old['priv_ciphertext'].encode()))
            signing = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private['ed25519'], validate=True))
            transcript = '\n'.join(['HTS1/KEY-ROTATION', *(str(fields[name]) for name in _FIELDS)]).encode()
            transition = {'fields': fields, 'sig_old': base64.b64encode(signing.sign(transcript)).decode()}
            await conn.execute(_KEY.update().where(_KEY.c.kid == expected_kid).values(status='overlap', transition=transition))
            await conn.execute(_KEY.insert().values(**fresh))
            await finish_if_ready(conn, self.bindings.instance_uuid)
            return transition

    async def emergency(self, suspect_kid):
        # Conservatively discard every serving key during overlap. Provision only
        # after committing retirement so key-generation failure cannot roll it back.
        async with self.engine.begin() as conn:
            await lock_keys(conn)
            status = await conn.scalar(sa.select(_KEY.c.status).where(_KEY.c.kid == suspect_kid))
            serving = _KEY.c.status.in_(SERVING_KEY_STATES)
            if status not in SERVING_KEY_STATES and (
                status != 'retired' or await conn.scalar(sa.select(sa.exists(sa.select(_KEY.c.kid).where(serving))))
            ):
                raise RotationError('key_changed')
            await retire(conn, serving)

        async with self.engine.begin() as conn:
            await lock_keys(conn)
            if await conn.scalar(sa.select(_KEY.c.kid).where(_KEY.c.status.in_(SERVING_KEY_STATES))):
                raise RotationError('key_changed')
            fresh = generate_key_material(self._wrapping_key())
            await conn.execute(_KEY.insert().values(**fresh))
        return dict(instance_uuid=self.bindings.instance_uuid, base_url=self.bindings.base_url, kid=fresh['kid'],
                    pub_x25519=fresh['x25519_pub'], pub_ed25519=fresh['ed25519_pub'], fingerprint=hashlib.sha256(
                        base64.b64decode(fresh['x25519_pub']) + base64.b64decode(fresh['ed25519_pub']),
                    ).hexdigest())

    def _device(self, binding_id, device_id):
        return sa.select(HarnessDevice.id).join(HarnessBinding, HarnessBinding.id == HarnessDevice.binding_id).where(
            HarnessBinding.instance_uuid == self.bindings.instance_uuid,
            HarnessBinding.id == binding_id, HarnessBinding.revoked_at.is_(None),
            HarnessDevice.id == device_id, HarnessDevice.revoked_at.is_(None),
        )

    async def get(self, binding_id, device_id, kid):
        async with self.engine.connect() as conn:
            if not await conn.scalar(self._device(binding_id, device_id)):
                raise RotationError('invalid_device')
            return await conn.scalar(sa.select(_KEY.c.transition).where(_KEY.c.kid == kid, _KEY.c.status == 'overlap'))

    async def ack(self, binding_id, device_id, kid, rotation_id, new_kid):
        if kid != new_kid:
            raise RotationError('wrong_rotation_key')
        async with self.engine.begin() as conn:
            await lock_keys(conn)
            if not await conn.scalar(self._device(binding_id, device_id)):
                raise RotationError('invalid_device')
            primary = await conn.scalar(sa.select(_KEY.c.kid).where(_KEY.c.status == 'active'))
            if primary != kid:
                raise RotationError('wrong_rotation_key')
            old = (await conn.execute(sa.select(_KEY.c.status, _KEY.c.transition).where(
                _KEY.c.transition['fields']['rotation_id'].as_string() == rotation_id,
                _KEY.c.transition['fields']['new_kid'].as_string() == new_kid,
            ))).one_or_none()
            ack = sa.select(_ACK.c.device_id).where(_ACK.c.rotation_id == rotation_id, _ACK.c.device_id == device_id)
            existing = await conn.scalar(ack)
            if old is None or (old.status != 'overlap' and not existing):
                raise RotationError('rotation_not_found')
            if old.status == 'retired':
                return {'acknowledged': True, 'retired': True}
            if not existing:
                await conn.execute(_ACK.insert().values(rotation_id=rotation_id, device_id=device_id))
            return {'acknowledged': True, 'retired': await finish_if_ready(conn, self.bindings.instance_uuid)}
