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

const { socket, channel } = await factory();
function request(payload) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error('Missing encrypted reply')), 3000);
    socket.onFrame((frame) => {
      clearTimeout(timer);
      try { resolve(channel.decode(frame)); } catch (error) { reject(error); }
    });
    socket.send(channel.encode(payload));
  });
}
try {
  const authenticated = await request({ type: 'authenticate', auth: { kind: 'user_token', token }, workspace_uuid: 'workspace' });
  assert.equal(authenticated.type, 'authenticated');
  assert.equal(authenticated.account_uuid, 'account');
  assert.equal(authenticated.workspace_uuid, 'workspace');
  assert.equal(typeof authenticated.csrf_token, 'string');
  const message = { type: 'message', conversation_id: 'thread-1', content: 'ping', workspace_uuid: 'workspace' };
  assert.deepEqual(await request({ ...message, csrf_token: authenticated.csrf_token, processor_uuid: 'other-agent' }),
    { type: 'error', code: 'processor_forbidden' });
  assert.deepEqual(await request({ ...message, csrf_token: authenticated.csrf_token, processor_uuid: 'agent' }),
    { type: 'message', role: 'assistant', content: 'pong', final: true, conversation_id: 'thread-1', processor_uuid: 'agent' });
} finally {
  socket.close();
}
