import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const transportUrl = pathToFileURL(process.env.HARNESS_TS_TRANSPORT);
const { createWebSocketSecureSocketFactory } = await import(transportUrl);
const { Hts1HttpRpcTransport } = await import(new URL('./rpc-transport.js', transportUrl));
const f = JSON.parse(process.env.HARNESS_RUNNER_FIXTURE);
const origin = f.clientOrigin;
const post = (path, body) => fetch(new URL(path, f.origin), {
  method: 'POST', headers: { 'Content-Type': 'application/json', Origin: origin }, body: JSON.stringify(body),
});
async function enroll({link, email, password}, deviceKid) {
const pin = JSON.parse(Buffer.from(new URL(link).hash.slice(1), 'base64url'));
const enrollment = await post('/api/v1/harness/register', { token: pin.token });
const enrollmentBody = await enrollment.json();
assert.equal(enrollment.status, 200, `Enrollment failed: ${enrollmentBody.code}`);
assert.equal(pin.base_url, f.origin);
const { harness_id: harnessId, enrollment_token } = enrollmentBody;
const x = await crypto.subtle.generateKey('X25519', true, ['deriveBits']);
const ed = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify']);
const raw = async (key) => Buffer.from(await crypto.subtle.exportKey('raw', key)).toString('base64');
const device = await post(`/api/v1/harness/bindings/${harnessId}/devices`, {
  enrollment_token, device_kid: deviceKid, x25519_pub: await raw(x.publicKey), ed25519_pub: await raw(ed.publicKey),
});
assert.equal(device.status, 200);
const key = (value, name, usages) => crypto.subtle.importKey('raw', Buffer.from(value, 'base64'), name, false, usages);
const keys = {
  expectedKid: pin.kid,
  serverStaticKey: await key(pin.pub_x25519, 'X25519', []),
  serverSigningKey: await key(pin.pub_ed25519, 'Ed25519', ['verify']),
  clientStaticKey: x.privateKey,
  clientSigningKey: ed.privateKey,
};
const rpc = new Hts1HttpRpcTransport({ baseUrl: f.origin, kid: pin.kid, harnessId, deviceKid }, keys);
const login = await rpc.request({ path: '/oauth/token', method: 'POST', body: {
  grant_type: 'password', email, password, workspace_uuid: f.workspace,
} });
assert.equal(login.status, 200, `Encrypted login failed: ${login.body?.code}`);
assert.ok(login.body.access_token);
return { rpc, keys, harnessId, deviceKid, token: login.body.access_token };
}
const { rpc, keys, harnessId, deviceKid, token } = await enroll(f, 'runner-check');
const directory = (token) => rpc.request({ path: '/api/v1/harness/processors', method: 'GET',
  auth: { kind: 'oauth', token } });
const listed = await directory(token);
assert.equal(listed.status, 200);
assert.equal(listed.body.workspace_uuid, f.workspace);
assert.deepEqual(listed.body.processors.map(p => p.id), f.processors);
const viewer = await rpc.request({ path: '/api/v1/harness/workspaces/select', method: 'POST',
  auth: { kind: 'oauth', token }, body: { workspace_uuid: f.viewerWorkspace } });
assert.equal(viewer.status, 200);
assert.deepEqual((await directory(viewer.body.access_token)).body.processors, []);
const url = new URL('/api/v1/harness/ws', f.origin);
url.protocol = 'wss:';
url.search = new URLSearchParams({ harness_id: harnessId, device_kid: deviceKid });
const { socket, channel } = await createWebSocketSecureSocketFactory(url.href, {
  ...keys,
  timeoutMs: 5000,
}, (endpoint) => new WebSocket(endpoint, { headers: { Origin: origin } }))();

function request(payload) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error(`Missing encrypted reply for ${payload.processor_uuid}`)), 8000);
    socket.onFrame((frame) => {
      clearTimeout(timer);
      try { resolve(channel.decode(frame)); } catch (error) { reject(error); }
    });
    socket.onClose(() => { clearTimeout(timer); reject(Error('WebSocket closed')); });
    socket.send(channel.encode(payload));
  });
}

try {
  const authenticated = await request({ type: 'authenticate', workspace_uuid: f.workspace,
    auth: { kind: 'oauth', token } });
  assert.equal(authenticated.type, 'authenticated');
  assert.equal(authenticated.workspace_uuid, f.workspace);
  const message = { type: 'message', workspace_uuid: f.workspace, conversation_id: 'runner-check', content: 'Reply through LocalAgent.' };
  assert.equal((await request({ ...message, processor_uuid: f.hiddenProcessor })).code, 'processor_forbidden');
  assert.equal((await request({ ...message, processor_uuid: 'missing-processor' })).code, 'processor_forbidden');
  assert.equal((await request({ ...message, workspace_uuid: 'other-workspace', processor_uuid: f.processors[0] })).code, 'workspace_forbidden');
  const executions = [];
  for (const processor of [...f.processors, f.processors[0]]) {
    const { execution, ...reply } = await request({ ...message, processor_uuid: processor });
    assert.deepEqual(reply, { type: 'message', role: 'assistant', content: 'Fake LLM response', final: true,
      conversation_id: message.conversation_id, processor_uuid: processor });
    assert.equal(execution?.source, 'agent');
    assert.ok(execution.id);
    executions.push({execution_id: execution.id, processor_uuid: processor,
      workspace_uuid: f.workspace, conversation_id: message.conversation_id});
  }
  const detail = await rpc.getExecutionDetail(executions[0], token);
  assert.equal(detail.status, 200, JSON.stringify(detail.body));
  assert.equal(detail.body.run.run_id, executions[0].execution_id);
  assert.equal(detail.body.run.status, 'completed');
  assert.match(JSON.stringify(detail.body.pages.outputs.items), /Fake LLM response/);
  const events = await rpc.getExecutionDetail({...executions[0], section: 'events', limit: 1}, token);
  assert.equal(events.status, 200);
  assert.equal(events.body.pages.events.items.length, 1);
  assert.ok(events.body.pages.events.has_more);
  assert.deepEqual(await rpc.getExecutionDetail({...executions[0], workspace_uuid: f.otherWorkspace}, token),
    { status: 403, body: { code: 'workspace_forbidden' } });
  assert.deepEqual(await rpc.getExecutionDetail({...executions[0], processor_uuid: f.processors[1]}, token),
    { status: 404, body: { code: 'execution_not_found' } });
  const other = await enroll(f.other, 'other-account');
  assert.deepEqual(await other.rpc.getExecutionDetail(executions[0], other.token),
    { status: 404, body: { code: 'execution_not_found' } });
  assert.deepEqual(await other.rpc.getExecutionDetail(executions[0], token),
    { status: 401, body: { code: 'invalid_grant' } });
} finally {
  socket.close();
}
