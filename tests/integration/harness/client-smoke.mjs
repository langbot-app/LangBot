import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const { createWebSocketSecureSocketFactory } = await import(pathToFileURL(process.env.HARNESS_TS_TRANSPORT));
const { url, clientX, clientEd, serverX, serverEd, token } = JSON.parse(process.env.HARNESS_TEST_FIXTURE);
const bytes = (value) => Buffer.from(value, 'base64');
const factory = createWebSocketSecureSocketFactory(url, {
  clientStaticKey: await crypto.subtle.importKey('pkcs8', bytes(clientX), 'X25519', false, ['deriveBits']),
  clientSigningKey: await crypto.subtle.importKey('pkcs8', bytes(clientEd), 'Ed25519', false, ['sign']),
  serverStaticKey: await crypto.subtle.importKey('raw', bytes(serverX), 'X25519', false, []),
  serverSigningKey: await crypto.subtle.importKey('raw', bytes(serverEd), 'Ed25519', false, ['verify']),
  timeoutMs: 4000,
}, (endpoint) => new WebSocket(endpoint, { headers: { Origin: 'http://127.0.0.1' } }));

function request({ socket, channel }, payload) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Missing encrypted reply')), 3000);
    socket.onFrame((frame) => {
      clearTimeout(timer);
      try { resolve(channel.decode(frame)); } catch (error) { reject(error); }
    });
    socket.send(channel.encode(payload));
  });
}

async function authenticate(connection) {
  const authenticated = await request(connection, { type: 'authenticate', auth: { kind: 'user_token', token }, workspace_uuid: 'workspace' });
  assert.equal(authenticated.type, 'authenticated');
  assert.equal(authenticated.account_uuid, 'account');
  assert.equal(authenticated.workspace_uuid, 'workspace');
  assert.equal(typeof authenticated.csrf_token, 'string');
  return authenticated.csrf_token;
}

const message = { type: 'message', conversation_id: 'thread-1', content: 'ping', workspace_uuid: 'workspace' };
const reply = { type: 'message', role: 'assistant', content: 'pong', final: true, conversation_id: 'thread-1', processor_uuid: 'agent' };
const initial = await factory();
let firstProof;
try {
  firstProof = await authenticate(initial);
  assert.deepEqual(await request(initial, { ...message, csrf_token: firstProof, processor_uuid: 'other-agent' }),
    { type: 'error', code: 'processor_forbidden' });
  const closed = new Promise((resolve) => initial.socket.onClose(resolve));
  assert.deepEqual(await request(initial, { ...message, csrf_token: firstProof, processor_uuid: 'agent' }), reply);
  let timer;
  try {
    await Promise.race([closed, new Promise((_, reject) => {
      timer = setTimeout(() => reject(Error('Server did not close first connection')), 3000);
    })]);
  } finally {
    clearTimeout(timer);
  }
} finally {
  initial.socket.close();
}

const resumed = await factory();
try {
  const secondProof = await authenticate(resumed);
  assert.notEqual(secondProof, firstProof);
  assert.deepEqual(await request(resumed, { ...message, csrf_token: secondProof, processor_uuid: 'agent' }), reply);
} finally {
  resumed.socket.close();
}
