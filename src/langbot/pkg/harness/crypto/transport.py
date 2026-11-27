"""HTS1 authenticated WebSocket frame transport.

Key lookup and encrypted-at-rest key management are intentionally injected by
the application boundary; this module owns the wire-level cryptography.
"""

import base64
import hmac
import json
import re
import secrets
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from .suite import INFO, TS_SKEW, WINDOW, derive, open_, seal


def _raw_public(key) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def hs1_transcript(v: int, kid: str, ts: int, nonce: str, server_ephemeral: str) -> bytes:
    return f'HTS1/HS1\n{v}\n{kid}\n{ts}\n{nonce}\n{server_ephemeral}'.encode()


class ReplayGuard:
    """Bounded one-use server challenge store."""

    def __init__(self):
        self._nonces: dict[str, float] = {}

    def issue(self) -> str:
        now = time.time()
        self._nonces = {key: expiry for key, expiry in self._nonces.items() if expiry >= now}
        nonce = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('=')
        self._nonces[nonce] = now + 60
        return nonce

    def consume(self, nonce: str) -> bool:
        expiry = self._nonces.pop(nonce, None)
        return expiry is not None and expiry >= time.time()


def begin_handshake(kid, signing_key, nonce):
    ephemeral = x25519.X25519PrivateKey.generate()
    eh = base64.b64encode(_raw_public(ephemeral.public_key())).decode()
    timestamp = int(time.time())
    transcript = hs1_transcript(1, kid, timestamp, nonce, eh)
    return {
        'v': 1, 'kid': kid, 'e_h': eh, 'ts': timestamp, 'nonce_s': nonce,
        'sig_h': base64.b64encode(signing_key.sign(transcript)).decode(),
    }, ephemeral, transcript


def finish_handshake(kid, transcript, ephemeral, server_static, client_static, client_signing, hs2):
    if not isinstance(hs2, dict) or type(hs2.get('v')) is not int or hs2['v'] != 1 or not all(
        isinstance(hs2.get(field), str) and len(hs2[field]) <= 128 for field in ('e_c', 'sig_c', 'confirm')
    ):
        raise ValueError('invalid HS2')
    client_ephemeral = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(hs2['e_c'], validate=True))
    transcript += b'\n' + hs2['e_c'].encode('ascii')
    client_signing.verify(base64.b64decode(hs2['sig_c'], validate=True), b'HTS1/HS2\n' + transcript)
    shared = (
        ephemeral.exchange(client_ephemeral)
        + server_static.exchange(client_ephemeral)
        + ephemeral.exchange(client_static)
    )
    c2h, h2c, confirm = derive(shared, kid, transcript)
    if not hmac.compare_digest(base64.b64decode(hs2['confirm'], validate=True), hmac.digest(confirm, INFO + transcript, 'sha256')):
        raise ValueError('invalid HS2 key confirmation')
    return c2h, h2c


class SecureSession:
    """Sequence-checked authenticated JSON frame session."""

    def __init__(self, websocket, kid: str, send_key: bytes, receive_key: bytes):
        self.websocket = websocket
        self.kid = kid
        self.send_key = send_key
        self.receive_key = receive_key
        self.send_seq = 0
        self.highest = -1
        self.seen: set[int] = set()

    async def receive_payload(self):
        frame = json.loads(await self.websocket.receive())
        if (
            not isinstance(frame, dict)
            or frame.get('v') != 1
            or frame.get('kid') != self.kid
            or frame.get('kind') != 'ws'
        ):
            raise ValueError('invalid HTS1 frame header')
        wire_seq = frame.get('seq')
        if not isinstance(wire_seq, str) or not re.fullmatch(r'0|[1-9][0-9]{0,19}', wire_seq):
            raise ValueError('invalid HTS1 sequence')
        seq = int(wire_seq)
        if seq >= 2**64 or seq in self.seen or seq <= self.highest - WINDOW:
            raise ValueError('HTS1 sequence outside replay window')
        encoded = frame.get('box')
        if not isinstance(encoded, str):
            raise ValueError('invalid HTS1 ciphertext')
        plain = open_(self.receive_key, seq, base64.b64decode(encoded, validate=True))
        self.seen.add(seq)
        self.highest = max(self.highest, seq)
        self.seen = {item for item in self.seen if item > self.highest - WINDOW}
        payload = json.loads(plain)
        timestamp = payload.get('ts') if isinstance(payload, dict) else None
        if timestamp is not None and (
            not isinstance(timestamp, (int, float)) or abs(time.time() - timestamp) > TS_SKEW
        ):
            raise ValueError('HTS1 payload timestamp outside allowed skew')
        return payload

    async def send_payload(self, payload):
        seq = self.send_seq
        self.send_seq += 1
        ciphertext = seal(self.send_key, seq, json.dumps(payload, separators=(',', ':')).encode())
        await self.websocket.send(
            json.dumps(
                {
                    'v': 1,
                    'kid': self.kid,
                    'seq': str(seq),
                    'kind': 'ws',
                    'box': base64.b64encode(ciphertext).decode(),
                },
                separators=(',', ':'),
            )
        )

    async def send(self, payload):
        await self.send_payload(payload)


async def handshake(
    websocket,
    *,
    kid: str,
    server_x25519_private: x25519.X25519PrivateKey,
    server_ed25519_private: ed25519.Ed25519PrivateKey,
    client_x25519_public: x25519.X25519PublicKey,
    client_ed25519_public: ed25519.Ed25519PublicKey,
    replay_guard: ReplayGuard,
):
    """Perform authenticated HS1/HS2 and return an encrypted session."""
    nonce = replay_guard.issue()
    hs1, ephemeral, transcript = begin_handshake(kid, server_ed25519_private, nonce)
    await websocket.send(json.dumps(hs1))
    try:
        hs2 = json.loads(await websocket.receive())
    finally:
        fresh = replay_guard.consume(nonce)
    if not fresh:
        raise ValueError('invalid HS2')
    c2h, h2c = finish_handshake(
        kid, transcript, ephemeral, server_x25519_private, client_x25519_public, client_ed25519_public, hs2,
    )
    return SecureSession(websocket, kid, h2c, c2h)


class HarnessTransportFactory:
    """Load the active instance identity and negotiate a client session.

    Client key lookup is injected because device registration is a separate
    feature slice; it must return pinned static public keys for ``harness_id``.
    """

    def __init__(self, ap, client_key_lookup, replay_guard: ReplayGuard | None = None):
        self.ap = ap
        self.client_key_lookup = client_key_lookup
        self.replay_guard = replay_guard or ReplayGuard()

    async def load_identity(self, pinned_kid=None):
        from cryptography.fernet import Fernet
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from ...entity.persistence.harness_instance_key import HarnessInstanceKey

        ap = self.ap
        statement = select(HarnessInstanceKey).where(HarnessInstanceKey.status == 'active')
        if pinned_kid is not None:
            statement = statement.where(HarnessInstanceKey.kid == pinned_kid)
        async with async_sessionmaker(ap.persistence_mgr.get_db_engine(), expire_on_commit=False)() as db:
            row = (
                await db.execute(
                    statement.order_by(HarnessInstanceKey.created_at.desc()).limit(1)
                )
            ).scalar_one_or_none()
        if row is None:
            raise ValueError('No active Harness instance key')
        jwt_secret = ap.instance_config.data['system']['jwt']['secret']
        from ...api.http.service.totp import _derive_wrapping_key

        wrapping_key = _derive_wrapping_key(jwt_secret, 1)
        private_bundle = json.loads(Fernet(wrapping_key).decrypt(row.priv_ciphertext.encode()))
        server_x = x25519.X25519PrivateKey.from_private_bytes(base64.b64decode(private_bundle['x25519'], validate=True))
        server_ed = ed25519.Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(private_bundle['ed25519'], validate=True)
        )
        return row.kid, server_x, server_ed

    async def __call__(self, ap, websocket):
        import asyncio

        kid, server_x, server_ed = await self.load_identity()

        # Public selectors only: these identify which pinned keys must verify HS2.
        # Account credentials are read from encrypted frames after the handshake.
        harness_id = websocket.args.get('harness_id', '')
        device_kid = websocket.args.get('device_kid', '')
        if not 0 < len(harness_id) <= 128 or not 0 < len(device_kid) <= 128:
            raise ValueError('Harness device identity required')
        client_keys = await self.client_key_lookup(harness_id, device_kid)
        if client_keys is None:
            raise ValueError('Unregistered Harness device')
        async with asyncio.timeout(30):
            return await handshake(
                websocket,
                kid=kid,
                server_x25519_private=server_x,
                server_ed25519_private=server_ed,
                client_x25519_public=x25519.X25519PublicKey.from_public_bytes(
                    base64.b64decode(client_keys['x25519_pub'], validate=True)
                ),
                client_ed25519_public=ed25519.Ed25519PublicKey.from_public_bytes(
                    base64.b64decode(client_keys['ed25519_pub'], validate=True)
                ),
                replay_guard=self.replay_guard,
            )
