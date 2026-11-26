import base64
import hmac
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from langbot.pkg.harness.crypto.suite import derive
from langbot.pkg.harness.crypto.transport import ReplayGuard, SecureSession, handshake


class Socket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.outgoing = []

    async def receive(self):
        return self.incoming.pop(0)

    async def send(self, value):
        self.outgoing.append(value)


class HandshakeSocket:
    def __init__(self, hello, hs2_builder):
        self.incoming = [json.dumps(hello)]
        self.outgoing = []
        self.hs2_builder = hs2_builder

    async def receive(self):
        if not self.incoming:
            self.incoming.append(json.dumps(self.hs2_builder(json.loads(self.outgoing[-1]))))
        return self.incoming.pop(0)

    async def send(self, value):
        self.outgoing.append(value)
        sent = json.loads(value)
        if sent.get('type') == 'challenge':
            self.incoming[0] = json.dumps({**json.loads(self.incoming[0]), 'nonce_s': sent['nonce_s']})


def frame(key, seq, payload):
    from langbot.pkg.harness.crypto.suite import seal

    return json.dumps(
        {
            'v': 1,
            'kid': 'kid-1',
            'seq': seq,
            'kind': 'ws',
            'box': base64.b64encode(seal(key, seq, json.dumps(payload).encode())).decode(),
        }
    )


def test_replay_guard_consumes_nonce_once():
    guard = ReplayGuard()
    nonce = guard.issue()
    assert guard.consume(nonce)
    assert not guard.consume(nonce)


@pytest.mark.asyncio
async def test_secure_session_encrypts_and_rejects_replayed_sequences():
    c2h, h2c, _ = derive(b'k' * 32, 'kid-1', b'transcript')
    inbound = frame(c2h, 0, {'message': 'hello'})
    socket = Socket([inbound, inbound])
    session = SecureSession(socket, 'kid-1', h2c, c2h)
    assert await session.receive_payload() == {'message': 'hello'}
    await session.send_payload({'message': 'reply'})
    outbound = json.loads(socket.outgoing[0])
    assert outbound['seq'] == 0
    assert outbound['kid'] == 'kid-1'
    with pytest.raises(ValueError, match='replay window'):
        await session.receive_payload()


@pytest.mark.asyncio
async def test_hs1_hs2_authentication_and_nonce_replay_rejection():
    guard = ReplayGuard()
    nonce = guard.issue()
    client_x = x25519.X25519PrivateKey.generate()
    client_static_x = x25519.X25519PrivateKey.generate()
    client_ed = ed25519.Ed25519PrivateKey.generate()
    server_x = x25519.X25519PrivateKey.generate()
    server_ed = ed25519.Ed25519PrivateKey.generate()
    ec = client_x.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    hello = {'type': 'hello', 'nonce_s': nonce, 'e_c': base64.b64encode(ec).decode()}

    def make_hs2(hs1):
        nonce = hs1['nonce_s_echo']
        eh = base64.b64decode(hs1['e_h'])
        transcript = json.dumps(
            {'v': 1, 'kid': 'kid-1', 'nonce_s': nonce}, sort_keys=True, separators=(',', ':')
        ).encode()
        signature_input = b'\x00'.join((b'HS2', eh, ec, b'kid-1', str(hs1['ts']).encode(), nonce.encode(), transcript))
        ikm = (
            client_x.exchange(x25519.X25519PublicKey.from_public_bytes(eh))
            + client_static_x.exchange(x25519.X25519PublicKey.from_public_bytes(eh))
            + client_x.exchange(server_x.public_key())
        )
        _, _, confirm_key = derive(ikm, 'kid-1', transcript)
        return {
            'v': 1,
            'nonce_s_echo': nonce,
            'sig_c': base64.b64encode(client_ed.sign(signature_input)).decode(),
            'confirm': base64.b64encode(hmac.digest(confirm_key, signature_input, 'sha256')).decode(),
        }

    socket = HandshakeSocket(hello, make_hs2)
    session = await handshake(
        socket,
        kid='kid-1',
        server_x25519_private=server_x,
        server_ed25519_private=server_ed,
        client_x25519_public=client_static_x.public_key(),
        client_ed25519_public=client_ed.public_key(),
        replay_guard=guard,
    )
    hs1 = json.loads(socket.outgoing[1])
    nonce = hs1['nonce_s_echo']
    server_signature_input = b'\x00'.join(
        (
            b'HS1',
            base64.b64decode(hs1['e_h']),
            ec,
            b'kid-1',
            str(hs1['ts']).encode(),
            nonce.encode(),
            json.dumps({'v': 1, 'kid': 'kid-1', 'nonce_s': nonce}, sort_keys=True, separators=(',', ':')).encode(),
        )
    )
    server_ed.public_key().verify(base64.b64decode(hs1['sig_h']), server_signature_input)
    assert session.kid == 'kid-1'
