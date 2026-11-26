import base64
import json

import pytest

from langbot.pkg.harness.crypto.suite import derive
from langbot.pkg.harness.crypto.transport import ReplayGuard, SecureSession


class Socket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.outgoing = []

    async def receive(self):
        return self.incoming.pop(0)

    async def send(self, value):
        self.outgoing.append(value)


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
