import base64
import hmac
import json
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from nacl.exceptions import CryptoError

from langbot.pkg.harness.crypto.suite import derive, seal
from langbot.pkg.harness.crypto.transport import ReplayGuard, SecureSession, handshake, hs1_transcript


def b64(value):
    return base64.b64encode(value).decode()


class Socket:
    def __init__(self, incoming=(), respond=None):
        self.incoming = list(incoming)
        self.outgoing = []
        self.respond = respond

    async def receive(self):
        if self.incoming:
            return self.incoming.pop(0)
        return json.dumps(self.respond(json.loads(self.outgoing[-1])))

    async def send(self, value):
        self.outgoing.append(value)


def test_shared_protocol_transcript_vector():
    # Keep this fixture byte-identical to LangBot-Harness's shared vector.
    vector = json.loads(Path(__file__).with_name('protocol-vectors.json').read_text())
    hs1 = vector['hts1_handshake']['hs1']
    assert (
        hs1_transcript(hs1['v'], hs1['kid'], hs1['ts'], hs1['nonce_s'], hs1['e_h']).decode()
        == (vector['hts1_handshake']['signed_transcript'])
    )
    assert vector['encrypted_frame']['seq'] == '1042'


async def test_secure_session_uses_uint64_strings_and_authenticates_before_replay_commit():
    c2h, h2c, _ = derive(b'k' * 32, 'kid-1', b'transcript')

    def frame(seq, key):
        return json.dumps({'v': 1, 'kid': 'kid-1', 'seq': str(seq), 'kind': 'ws', 'box': b64(seal(key, seq, b'{}'))})

    ordinary = frame(0, c2h)
    high = frame(2**64 - 1, c2h)
    socket = Socket([frame(2**64 - 1, h2c), ordinary, ordinary, high])
    session = SecureSession(socket, 'kid-1', h2c, c2h)
    with pytest.raises(CryptoError):
        await session.receive_payload()
    assert await session.receive_payload() == {}
    with pytest.raises(ValueError, match='replay window'):
        await session.receive_payload()
    assert await session.receive_payload() == {}
    await session.send_payload({'message': 'reply'})
    assert json.loads(socket.outgoing[0])['seq'] == '0'


async def test_hs1_hs2_pin_confirmation_and_cross_connection_replay():
    guard = ReplayGuard()
    client_x = x25519.X25519PrivateKey.generate()
    client_static_x = x25519.X25519PrivateKey.generate()
    client_ed = ed25519.Ed25519PrivateKey.generate()
    server_x = x25519.X25519PrivateKey.generate()
    server_ed = ed25519.Ed25519PrivateKey.generate()
    ec = b64(client_x.public_key().public_bytes_raw())
    client_keys = None
    response = None

    def make_hs2(hs1):
        nonlocal client_keys, response
        assert set(hs1) == {'v', 'kid', 'e_h', 'ts', 'nonce_s', 'sig_h'}
        first = ('HTS1/HS1\n1\nkid-1\n{ts}\n{nonce_s}\n{e_h}'.format(**hs1)).encode()
        server_ed.public_key().verify(base64.b64decode(hs1['sig_h']), first)
        full = first + b'\n' + ec.encode()
        eh = x25519.X25519PublicKey.from_public_bytes(base64.b64decode(hs1['e_h']))
        ikm = client_x.exchange(eh) + client_x.exchange(server_x.public_key()) + client_static_x.exchange(eh)
        client_keys = derive(ikm, 'kid-1', full)
        response = {
            'v': 1,
            'e_c': ec,
            'sig_c': b64(client_ed.sign(b'HTS1/HS2\n' + full)),
            'confirm': b64(hmac.digest(client_keys[2], b'langbot-harness-hts1' + full, 'sha256')),
        }
        return response

    async def connect(respond, signing_key=client_ed.public_key()):
        return await handshake(
            Socket(respond=respond),
            kid='kid-1',
            server_x25519_private=server_x,
            server_ed25519_private=server_ed,
            client_x25519_public=client_static_x.public_key(),
            client_ed25519_public=signing_key,
            replay_guard=guard,
        )

    session = await connect(make_hs2)
    assert (session.receive_key, session.send_key) == client_keys[:2]
    old_response = response
    with pytest.raises(InvalidSignature):
        await connect(lambda _: old_response)
    with pytest.raises(InvalidSignature):
        await connect(make_hs2, ed25519.Ed25519PrivateKey.generate().public_key())
    with pytest.raises(ValueError, match='key confirmation'):
        await connect(lambda first: {**make_hs2(first), 'confirm': b64(bytes(32))})
