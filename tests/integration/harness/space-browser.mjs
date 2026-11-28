// Chromium exercises the real Space and Core HTTPS endpoints and pinned WSS.
// The consent page and the callback bridge are isolated test UI.
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(pathToFileURL(process.env.HARNESS_PLAYWRIGHT));
const { origin, links, workspace } = JSON.parse(process.env.HARNESS_RPC_TEST);
const space = process.env.SPACE_TEST_ORIGIN;
const callback = process.env.SPACE_TEST_CALLBACK;
const browser = await chromium.launch({ executablePath: process.env.HARNESS_CHROMIUM });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const harness = await context.newPage();
  await harness.goto(`${origin}/_test/harness`);
  const target = await harness.evaluate(async ({ link, workspace, callback }) => {
    const { Hts1HttpRpcTransport, createWebSocketSecureSocketFactory } = await import('/_test/core.js');
    const decode = value => Uint8Array.from(atob(value), c => c.charCodeAt(0));
    const encode = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)));
    const nonce = () => encode(crypto.getRandomValues(new Uint8Array(32))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const pin = JSON.parse(atob(new URL(link).hash.slice(1).replace(/-/g, '+').replace(/_/g, '/')));
    async function post(path, body) {
      const reply = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!reply.ok) throw new Error(`Enrollment HTTP ${reply.status}`);
      return reply.json();
    }
    const { harness_id, enrollment_token } = await post('/api/v1/harness/register', { token: pin.token });
    const x = await crypto.subtle.generateKey('X25519', true, ['deriveBits']);
    const ed = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify']);
    const raw = async key => encode(await crypto.subtle.exportKey('raw', key));
    const deviceKid = 'browser-device';
    const { data } = await post(`/api/v1/harness/bindings/${harness_id}/devices`, {
      enrollment_token, device_kid: deviceKid, x25519_pub: await raw(x.publicKey), ed25519_pub: await raw(ed.publicKey),
    });
    const keys = {
      expectedKid: pin.kid, clientStaticKey: x.privateKey, clientSigningKey: ed.privateKey,
      serverStaticKey: await crypto.subtle.importKey('raw', decode(pin.pub_x25519), 'X25519', false, []),
      serverSigningKey: await crypto.subtle.importKey('raw', decode(pin.pub_ed25519), 'Ed25519', false, ['verify']),
    };
    const verifier = nonce();
    const state = nonce();
    const challenge = encode(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)))
      .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    window.finishHarnessConsent = async result => {
      if (result.state !== state || result.redirect_uri !== callback) throw new Error('Callback mismatch');
      const rpc = new Hts1HttpRpcTransport({ baseUrl: location.origin, kid: pin.kid, harnessId: harness_id, deviceKid }, keys);
      const grant = await rpc.exchangeSpaceCode({ code: result.code, code_verifier: verifier, redirect_uri: callback,
        workspace_uuid: workspace, account_uuid: result.account_uuid });
      if (grant.status !== 200) throw new Error(`HTS1 rejected: ${grant.body.code}`);
      const url = new URL('/api/v1/harness/ws', location.origin);
      url.protocol = 'wss:';
      url.search = new URLSearchParams({ harness_id, device_kid: deviceKid, pinned_kid: pin.kid });
      const { socket, channel } = await createWebSocketSecureSocketFactory(url.href, { ...keys, timeoutMs: 3000 })();
      try {
        return await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('WSS authentication timed out')), 3000);
          socket.onFrame(frame => { clearTimeout(timer); resolve(channel.decode(frame).type); });
          socket.send(channel.encode({ type: 'authenticate', workspace_uuid: workspace,
            auth: { kind: 'oauth', token: grant.body.access_token } }));
        });
      } finally { socket.close(); }
    };
    return { client_id: 'harness', instance_id: pin.instance_uuid, binding_id: harness_id, device_id: data.device_id,
      workspace_uuid: workspace, redirect_uri: callback, response_type: 'code', code_challenge_method: 'S256',
      code_challenge: challenge, state };
  }, { link: links[0], workspace, callback });

  const consent = await context.newPage();
  await consent.goto(`${space}/_test/consent`);
  await consent.evaluate(({ target, session }) => {
    document.querySelector('#cancel').onclick = () => { document.title = 'Cancelled'; };
    document.querySelector('#approve').onclick = () => {
      window.consentResult = fetch('/api/v1/accounts/harness/oauth/authorize', {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session}` },
        body: JSON.stringify(target),
      }).then(async reply => {
        if (!reply.ok) throw new Error(`Consent HTTP ${reply.status}`);
        return (await reply.json()).data;
      });
    };
  }, { target, session: process.env.SPACE_TEST_SESSION });
  await consent.locator('#cancel').click();
  assert.equal(await consent.title(), 'Cancelled');
  assert.equal(await consent.evaluate(() => window.consentResult === undefined), true);
  assert.equal(await harness.evaluate(async () => (await fetch('/_test/binding-count')).text()), '0');
  await consent.locator('#approve').click();
  const result = await consent.evaluate(() => window.consentResult);
  assert.equal(result.redirect_uri, callback);
  const callbackURL = new URL(callback);
  callbackURL.search = new URLSearchParams({ code: result.code, state: result.state, account_uuid: result.account_uuid });
  await consent.goto(callbackURL.href);
  const response = await consent.evaluate(() => Object.fromEntries(new URL(location.href).searchParams));
  assert.equal(await harness.evaluate(result => window.finishHarnessConsent(result), { ...response, redirect_uri: callback }), 'authenticated');
} finally {
  await browser.close();
}
