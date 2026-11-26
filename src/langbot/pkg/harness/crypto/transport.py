"""HTS1 authenticated WebSocket frame transport.

Key lookup and encrypted-at-rest key management are intentionally injected by
the application boundary; this module owns the wire-level cryptography.
"""

import base64
import hmac
import json
import secrets
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from .suite import TS_SKEW, WINDOW, derive, open_, seal


def _raw_public(key) -> bytes:
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _signature_input(label: bytes, eh: bytes, ec: bytes, kid: str, ts: int, nonce: bytes, transcript: bytes) -> bytes:
    return b'\x00'.join((label, eh, ec, kid.encode(), str(ts).encode(), nonce, transcript))


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
        if frame.get('v') != 1 or frame.get('kid') != self.kid or frame.get('kind') != 'ws':
            raise ValueError('invalid HTS1 frame header')
        seq = frame.get('seq')
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise ValueError('invalid HTS1 sequence')
        if seq in self.seen or seq <= self.highest - WINDOW or seq > self.highest + WINDOW:
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
                    'seq': seq,
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
    initial_hello: dict | None = None,
    issued_nonce: str | None = None,
):
    """Perform authenticated HS1/HS2 and return an encrypted session."""
    nonce = issued_nonce or replay_guard.issue()
    if initial_hello is None:
        await websocket.send(json.dumps({'type': 'challenge', 'v': 1, 'kid': kid, 'nonce_s': nonce}))
    challenge = initial_hello or json.loads(await websocket.receive())
    if not isinstance(challenge, dict) or challenge.get('type') != 'hello':
        raise ValueError('invalid client hello')
    client_nonce = challenge.get('nonce_s')
    if client_nonce != nonce or (issued_nonce is None and not replay_guard.consume(nonce)):
        raise ValueError('invalid or replayed server nonce')
    client_ephemeral_bytes = base64.b64decode(challenge.get('e_c', ''), validate=True)
    client_ephemeral = x25519.X25519PublicKey.from_public_bytes(client_ephemeral_bytes)
    transcript = json.dumps({'v': 1, 'kid': kid, 'nonce_s': nonce}, sort_keys=True, separators=(',', ':')).encode()
    server_ephemeral = x25519.X25519PrivateKey.generate()
    eh, ec = _raw_public(server_ephemeral.public_key()), client_ephemeral_bytes
    timestamp = int(time.time())
    sig_h = server_ed25519_private.sign(_signature_input(b'HS1', eh, ec, kid, timestamp, nonce.encode(), transcript))
    await websocket.send(
        json.dumps(
            {
                'v': 1,
                'kid': kid,
                'e_h': base64.b64encode(eh).decode(),
                'ts': timestamp,
                'nonce_s_echo': nonce,
                'sig_h': base64.b64encode(sig_h).decode(),
            }
        )
    )
    hs2 = json.loads(await websocket.receive())
    if hs2.get('v') != 1 or hs2.get('nonce_s_echo') != nonce:
        raise ValueError('invalid HS2')
    client_signature = base64.b64decode(hs2.get('sig_c', ''), validate=True)
    client_ed25519_public.verify(
        client_signature, _signature_input(b'HS2', eh, ec, kid, timestamp, nonce.encode(), transcript)
    )
    shared = (
        server_ephemeral.exchange(client_ephemeral)
        + server_ephemeral.exchange(client_x25519_public)
        + server_x25519_private.exchange(client_ephemeral)
    )
    c2h, h2c, confirm = derive(shared, kid, transcript)
    expected = hmac.digest(
        confirm, _signature_input(b'HS2', eh, ec, kid, timestamp, nonce.encode(), transcript), 'sha256'
    )
    if not hmac.compare_digest(base64.b64decode(hs2.get('confirm', ''), validate=True), expected):
        raise ValueError('invalid HS2 key confirmation')
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

    async def __call__(self, ap, websocket):
        from cryptography.fernet import Fernet
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from ...entity.persistence.harness_instance_key import HarnessInstanceKey

        async with async_sessionmaker(ap.persistence_mgr.get_db_engine(), expire_on_commit=False)() as db:
            row = (
                await db.execute(
                    select(HarnessInstanceKey)
                    .where(HarnessInstanceKey.status == 'active')
                    .order_by(HarnessInstanceKey.created_at.desc())
                    .limit(1)
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

        async def receive_client_keys():
            hello = json.loads(await websocket.receive())
            if not isinstance(hello, dict) or not isinstance(hello.get('harness_id'), str):
                raise ValueError('Harness device identity required')
            keys = await self.client_key_lookup(hello['harness_id'], hello.get('device_kid'))
            if keys is None:
                raise ValueError('Unregistered Harness device')
            return hello, keys

        # Start challenge and read the hello with pinned device identity.
        nonce = self.replay_guard.issue()
        await websocket.send(json.dumps({'type': 'challenge', 'v': 1, 'kid': row.kid, 'nonce_s': nonce}))
        hello, client_keys = await receive_client_keys()
        if hello.get('nonce_s') != nonce or not self.replay_guard.consume(nonce):
            raise ValueError('invalid or replayed server nonce')
        return await handshake(
            websocket,
            kid=row.kid,
            server_x25519_private=server_x,
            server_ed25519_private=server_ed,
            client_x25519_public=x25519.X25519PublicKey.from_public_bytes(base64.b64decode(client_keys['x25519_pub'])),
            client_ed25519_public=ed25519.Ed25519PublicKey.from_public_bytes(
                base64.b64decode(client_keys['ed25519_pub'])
            ),
            replay_guard=self.replay_guard,
            initial_hello=hello,
            issued_nonce=nonce,
        )
