import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const { Hts1HttpRpcTransport } = await import(pathToFileURL(process.env.HARNESS_TS_RPC_TRANSPORT));
const { origin, links, email, password, workspace } = JSON.parse(process.env.HARNESS_RPC_TEST);

async function post(path, body) {
  return fetch(new URL(path, origin), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
}

let lastEnvelope;
async function enroll(link, deviceKid) {
  const pin = JSON.parse(Buffer.from(new URL(link).hash.slice(1), 'base64url'));
  const registered = await post('/api/v1/harness/register', { token: pin.token });
  assert.equal(registered.status, 200);
  const { harness_id: harnessId, enrollment_token } = await registered.json();
  const x = await crypto.subtle.generateKey('X25519', true, ['deriveBits']);
  const ed = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify']);
  const raw = async key => Buffer.from(await crypto.subtle.exportKey('raw', key)).toString('base64');
  const device = await post(`/api/v1/harness/bindings/${harnessId}/devices`, {
    enrollment_token, device_kid: deviceKid, x25519_pub: await raw(x.publicKey), ed25519_pub: await raw(ed.publicKey),
  });
  assert.equal(device.status, 200);
  return new Hts1HttpRpcTransport({ baseUrl: origin, kid: pin.kid, harnessId, deviceKid }, {
    expectedKid: pin.kid,
    serverStaticKey: await crypto.subtle.importKey('raw', Buffer.from(pin.pub_x25519, 'base64'), 'X25519', false, []),
    serverSigningKey: await crypto.subtle.importKey('raw', Buffer.from(pin.pub_ed25519, 'base64'), 'Ed25519', false, ['verify']),
    clientStaticKey: x.privateKey, clientSigningKey: ed.privateKey,
    fetch: async (url, init) => {
      const body = JSON.parse(init.body);
      assert.ok(!init.body.includes(password) && !init.body.includes(email));
      if (url.pathname === '/api/v1/harness/rpc') lastEnvelope = body;
      const response = await fetch(url, init);
      assert.equal(response.headers.get('Cache-Control'), 'no-store');
      return response;
    },
  });
}

const exchange = (rpc, body) => rpc.request({ path: '/oauth/token', method: 'POST', body });
const login = (rpc, ws, pwd = password) => exchange(rpc, { grant_type: 'password', email, password: pwd, workspace_uuid: ws });
const refresh = (rpc, token) => exchange(rpc, { grant_type: 'refresh_token', refresh_token: token });
const first = await enroll(links[0], 'device-one');
assert.deepEqual(await login(first, workspace, 'incorrect'), { status: 401, body: { code: 'invalid_grant' } });
const signedIn = await login(first, workspace);
assert.equal(signedIn.status, 200);
assert.ok(signedIn.body.access_token);
const crossWorkspace = await login(first, 'unjoined');
assert.deepEqual(crossWorkspace, { status: 403, body: { code: 'workspace_forbidden' } });
const oldToken = signedIn.body.refresh_token;
const repeatedEnvelope = await post('/api/v1/harness/rpc', lastEnvelope);
assert.equal(repeatedEnvelope.status, 400);
assert.deepEqual(await repeatedEnvelope.json(), { code: 'invalid_hs2' });

const other = await enroll(links[1], 'device-two');
assert.deepEqual(await refresh(other, oldToken), { status: 401, body: { code: 'invalid_grant' } });
const list = (rpc, token) => rpc.request({ path: '/api/v1/harness/workspaces', method: 'GET', auth: { kind: 'oauth', token } });
const select = (rpc, token, id) => rpc.request({ path: '/api/v1/harness/workspaces/select', method: 'POST',
  auth: { kind: 'oauth', token }, body: { workspace_uuid: id } });
assert.equal((await list(other, signedIn.body.access_token)).status, 401);
const directory = await list(first, signedIn.body.access_token);
assert.equal(directory.body.workspace_uuid, workspace);
assert.deepEqual(directory.body.workspaces.map(item => item.id).sort(), [workspace, 'shared'].sort());
assert.equal((await select(first, signedIn.body.access_token, 'private')).status, 403);
const switched = await select(first, signedIn.body.access_token, 'shared');
assert.equal(switched.status, 200);
assert.ok(!switched.body.scope.split(' ').includes('agent.run'));
const scopedRefresh = await refresh(first, switched.body.refresh_token);
assert.equal(scopedRefresh.status, 200);
assert.equal((await list(first, scopedRefresh.body.access_token)).body.workspace_uuid, 'shared');
const resumed = await login(first, workspace);
assert.equal(resumed.status, 200);
assert.equal((await list(first, resumed.body.access_token)).body.workspace_uuid, workspace);
const rotated = await refresh(first, oldToken);
assert.equal(rotated.status, 200);
assert.ok(rotated.body.refresh_token && rotated.body.refresh_token !== oldToken);
assert.deepEqual(await refresh(first, oldToken), { status: 401, body: { code: 'refresh_token_reuse' } });
assert.deepEqual(await refresh(first, rotated.body.refresh_token), { status: 401, body: { code: 'invalid_grant' } });
for (const body of [{ grant_type: 'password', username: email, password },
  { grant_type: 'refresh_token', refresh_token: oldToken }]) {
  const legacy = await post('/api/v1/harness/oauth/token', body);
  assert.equal(legacy.status, 415);
  assert.deepEqual(await legacy.json(), { error: 'encrypted_transport_required' });
}
