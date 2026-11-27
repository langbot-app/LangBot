import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const { Hts1HttpRpcTransport } = await import(pathToFileURL(process.env.HARNESS_TS_RPC_TRANSPORT));
const { origin, links, email, password, workspace, scenario, rotationToken, observerOrigin, browserAccountToken } = JSON.parse(process.env.HARNESS_RPC_TEST);

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
  const connect = async (identity, intercept) => {
    const keys = {
    expectedKid: identity.kid,
    serverStaticKey: await crypto.subtle.importKey('raw', Buffer.from(identity.pub_x25519, 'base64'), 'X25519', false, []),
    serverSigningKey: await crypto.subtle.importKey('raw', Buffer.from(identity.pub_ed25519, 'base64'), 'Ed25519', false, ['verify']),
    clientStaticKey: x.privateKey, clientSigningKey: ed.privateKey,
    fetch: async (url, init) => {
      const body = JSON.parse(init.body);
      assert.ok(!init.body.includes(password) && !init.body.includes(email));
      if (url.pathname === '/api/v1/harness/rpc') lastEnvelope = body;
      const response = await (intercept ?? fetch)(url, init);
      assert.equal(response.headers.get('Cache-Control'), 'no-store');
      return response;
    },
    };
    return { keys, rpc: new Hts1HttpRpcTransport({ baseUrl: origin, kid: identity.kid, harnessId, deviceKid }, keys) };
  };
  return { ...await connect(pin), connect, pin, harnessId, deviceKid };
}

const exchange = (rpc, body) => rpc.request({ path: '/oauth/token', method: 'POST', body });
const login = (rpc, ws, pwd = password) => exchange(rpc, { grant_type: 'password', email, password: pwd, workspace_uuid: ws });
const refresh = (rpc, token) => exchange(rpc, { grant_type: 'refresh_token', refresh_token: token });
if (scenario !== 'oauth') {
  const a = await enroll(links[0], 'device-one');
  const b = await enroll(links[1], 'device-two');
  assert.notEqual(a.harnessId, b.harnessId);
  const aLogin = await login(a.rpc, workspace);
  const bLogin = await login(b.rpc, workspace);
  assert.equal(aLogin.status, 200);
  assert.equal(bLogin.status, 200);
  const { createWebSocketSecureSocketFactory } = await import(new URL('./transport.js', pathToFileURL(process.env.HARNESS_TS_RPC_TRANSPORT)));
  async function ws(device, keys, token) {
    const url = new URL('/api/v1/harness/ws', observerOrigin);
    url.protocol = 'wss:';
    url.search = new URLSearchParams({ harness_id: device.harnessId, device_kid: device.deviceKid, pinned_kid: keys.expectedKid });
    const { socket, channel } = await createWebSocketSecureSocketFactory(url.href, { ...keys, timeoutMs: 3000 },
      endpoint => new WebSocket(endpoint, { headers: { Origin: origin } }))();
    const closed = new Promise(resolve => socket.onClose(resolve));
    let frame;
    try {
      frame = await deadline(new Promise(resolve => {
        socket.onFrame(resolve);
        socket.send(channel.encode({ type: 'authenticate', workspace_uuid: workspace, auth: { kind: 'oauth', token } }));
      }));
      assert.equal(channel.decode(frame).type, 'authenticated');
    } catch (error) { socket.close(); throw error; }
    return { socket, closed };
  }
  async function deadline(promise) {
    let timer;
    try {
      return await Promise.race([promise, new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('Timed out waiting for WS event')), 3000);
      })]);
    } finally { clearTimeout(timer); }
  }
  const admin = (mode, kid, secret = rotationToken) => fetch(new URL('/api/v1/harness/instance/key-rotation', origin), {
    method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${secret}` },
    body: JSON.stringify({ mode, kid }),
  });
  assert.equal((await admin('planned', a.pin.kid, aLogin.body.access_token)).status, 404);
  const stale = await ws(a, a.keys, aLogin.body.access_token);
  try {
    const planned = await admin('planned', a.pin.kid);
    assert.equal(planned.status, 200);
    const transition = await planned.json();
    const { fields, sig_old } = transition;
    assert.deepEqual(await a.rpc.getKeyRotation(), { status: 200, body: transition });
    const transcript = ['HTS1/KEY-ROTATION', ...['v', 'rotation_id', 'instance_uuid', 'base_url', 'old_kid',
      'new_kid', 'pub_x25519', 'pub_ed25519', 'created_at'].map(field => fields[field])].join('\n');
    assert.ok(await crypto.subtle.verify('Ed25519', a.keys.serverSigningKey, Buffer.from(sig_old, 'base64'), Buffer.from(transcript)));
    assert.equal(fields.instance_uuid, a.pin.instance_uuid);
    assert.equal(fields.base_url, origin);
    assert.equal(fields.old_kid, a.pin.kid);
    assert.equal((await admin('planned', fields.new_kid)).status, 409);
    assert.equal((await a.rpc.acknowledgeKeyRotation(fields.rotation_id)).status, 400);
    const newPin = { ...fields, kid: fields.new_kid };
    // The fixture obtained this pin independently via the operator request above.
    const nextA = await a.connect(newPin);
    const ackA = () => nextA.rpc.acknowledgeKeyRotation(fields.rotation_id);
    if (scenario === 'planned') {
      const pending = { status: 200, body: { acknowledged: true, retired: false } };
      assert.deepEqual(await ackA(), pending);
      assert.deepEqual(await ackA(), pending);
      const nextSocket = await ws(a, nextA.keys, aLogin.body.access_token);
      try {
        // B has had no open socket or RPC activity since the pre-rotation login.
        assert.deepEqual(await a.rpc.getKeyRotation(), { status: 200, body: transition });
        assert.deepEqual(await b.rpc.getKeyRotation(), { status: 200, body: transition });
        const nextB = await b.connect(newPin);
        const final = { status: 200, body: { acknowledged: true, retired: true } };
        assert.deepEqual(await nextB.rpc.acknowledgeKeyRotation(fields.rotation_id), final);
        assert.deepEqual(await ackA(), final);
        await deadline(stale.closed);
        await assert.rejects(b.rpc.getKeyRotation(), /key_retired/);
        await assert.rejects(ws(b, b.keys, bLogin.body.access_token));
      } finally { nextSocket.socket.close(); }
    } else {
      let replacement;
      const overlapSocket = await ws(a, nextA.keys, aLogin.body.access_token);
      try {
        const challenge = await a.connect(a.pin, async (url, init) => {
          if (url.pathname.endsWith('/rpc')) {
            const emergency = await admin('emergency', a.pin.kid);
            assert.equal(emergency.status, 200);
            replacement = await emergency.json();
          }
          return fetch(url, init);
        });
        await assert.rejects(challenge.rpc.getKeyRotation(), /key_retired/);
        await deadline(Promise.all([stale.closed, overlapSocket.closed]));
        await assert.rejects(b.rpc.getKeyRotation(), /key_retired/);
        await assert.rejects(nextA.rpc.getKeyRotation(), /key_retired/);
        await assert.rejects(ws(b, b.keys, bLogin.body.access_token));
        assert.notEqual(replacement.kid, fields.new_kid);
        assert.equal(replacement.old_kid, undefined);
        assert.equal(replacement.sig_old, undefined);
        // Simulated separately trusted operator delivery, no in-band pin fallback.
        const recovered = await b.connect(replacement);
        assert.deepEqual(await recovered.rpc.getKeyRotation(), { status: 200, body: null });
        const recoveredSocket = await ws(b, recovered.keys, bLogin.body.access_token);
        recoveredSocket.socket.close();
      } finally { overlapSocket.socket.close(); }
    }
  } finally { stale.socket.close(); }
  process.exit(0);
}
const { rpc: first } = await enroll(links[0], 'device-one');
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

const { rpc: other } = await enroll(links[1], 'device-two');
assert.deepEqual(await refresh(other, oldToken), { status: 401, body: { code: 'invalid_grant' } });
const list = (rpc, token) => rpc.request({ path: '/api/v1/harness/workspaces', method: 'GET', auth: { kind: 'oauth', token } });
// Space's Core browser callback issues this same account-token format. A
// valid Core signature and a real enrolled device do not make it a grant.
assert.deepEqual(await list(first, browserAccountToken), { status: 401, body: { code: 'invalid_grant' } });
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
