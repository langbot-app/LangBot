import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const { chromium } = createRequire(import.meta.url)(process.env.HARNESS_PLAYWRIGHT_MODULE ?? 'playwright-core');
const { origin, links, account, workspace, email, password, scenario, probe } = JSON.parse(process.env.HARNESS_TOTP_TEST);
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_BIN, args: ['--no-sandbox'] });
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, locale: 'en-US' });
  const page = await context.newPage();
  const api = async (action) => {
    const response = await context.request.post(`${origin}/_test/${action}`, { headers: { Authorization: `Bearer ${probe}` } });
    assert.equal(response.status(), 200);
    return response.json();
  };
  const zero = async () => assert.deepEqual(await api('count'), { harness_bindings: 0, harness_oauth_grants: 0 });
  const screenshot = async (target, name) => {
    if (!process.env.HARNESS_SCREENSHOTS) return;
    await mkdir(process.env.HARNESS_SCREENSHOTS, { recursive: true });
    await target.screenshot({ path: join(process.env.HARNESS_SCREENSHOTS, `${name}.png`) });
  };
  const instances = () => page.evaluate(() => new Promise((resolve, reject) => {
    const open = indexedDB.open('langbot-harness-registry');
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result;
      const request = db.transaction('instances').objectStore('instances').getAll();
      request.onerror = () => reject(request.error);
      request.onsuccess = () => { db.close(); resolve(request.result); };
    };
  }));
  await page.goto(origin);
  await page.getByRole('button', { name: 'Self-hosted' }).click();
  await page.locator('#link').fill(links[0]);
  await page.locator('#bind-email').fill(email);
  await page.locator('#bind-password').fill(password);
  await page.locator('#bind-workspace').fill(workspace);
  await page.getByRole('button', { name: 'Sign in and bind' }).click();
  const approvalLink = page.getByRole('link', { name: 'Open browser authorization' });
  await approvalLink.waitFor();
  const url = new URL(await approvalLink.getAttribute('href'));
  assert.equal(url.origin, origin);
  await zero();
  assert.deepEqual(await instances(), []);
  const popup = context.waitForEvent('page');
  await approvalLink.click();
  const approval = await popup;
  await approval.getByRole('heading', { name: 'Approve Harness sign-in' }).waitFor();
  const approve = async () => {
    await approval.getByLabel('Authenticator code').fill((await api('code')).code);
    await approval.getByRole('button', { name: 'Approve', exact: true }).click();
  };
  const poll = (link, ticket, existing) => page.evaluate(async ({ link, ticket, existing }) => {
    const { BrowserDeviceKeys, parseRegistrationLink, registerDeviceDirect, importInstancePin, Hts1HttpRpcTransport } = await import('/_test/core.js');
    const store = await BrowserDeviceKeys.open();
    const binding = existing ?? await registerDeviceDirect(parseRegistrationLink(link), store);
    const keys = await store.load(binding, binding.deviceKid);
    const rpc = new Hts1HttpRpcTransport({ baseUrl: binding.base_url, harnessId: binding.harness_id,
      deviceKid: binding.deviceKid, kid: binding.kid }, { ...await importInstancePin(binding), ...keys, fetch: window.fetch.bind(window) });
    return rpc.request({ method: 'POST', path: '/oauth/token', body: { grant_type: 'urn:langbot:handoff', handoff_ticket: ticket } });
  }, { link, ticket, existing });
  if (scenario === 'cancel') {
    await approval.getByRole('button', { name: 'Cancel', exact: true }).click();
    await approval.getByText('Approval cancelled.', { exact: false }).waitFor();
    await screenshot(approval, 'handoff-cancelled');
  } else if (scenario === 'expire') {
    await api('expire');
    await approve();
    await approval.getByText('This approval request is unavailable or has expired.').waitFor();
    await screenshot(approval, 'handoff-expired');
  } else {
    // Pause only the UI poller so approval alone can be checked before redemption.
    if (scenario === 'other-device') await page.getByRole('button', { name: 'Cancel' }).first().click();
    await approve();
    await approval.getByText('Approved. Return to Harness', { exact: false }).waitFor();
    if (scenario === 'other-device') {
      const other = await poll(links[1], url.searchParams.get('ticket'));
      assert.equal(other.body.code, 'invalid_grant');
    } else {
      await screenshot(approval, 'handoff-approved');
      await page.getByText('Local TOTP instance', { exact: true }).first().waitFor();
      let saved;
      for (let i = 0; i < 50 && !saved; i++) {
        [saved] = await instances();
        if (!saved) await new Promise((resolve) => setTimeout(resolve, 100));
      }
      assert.equal(saved?.accountAuthorized, true);
      const replay = await poll(null, url.searchParams.get('ticket'), saved);
      assert.equal(replay.body.code, 'invalid_grant');
      const { token } = await api('grant');
      await page.evaluate(async ({ saved, token, account, workspace }) => {
        const { BrowserDeviceKeys, createBoundChatTransport } = await import('/_test/core.js');
        const keys = await (await BrowserDeviceKeys.open()).load(saved, saved.deviceKid);
        const chat = await createBoundChatTransport(saved, keys, {
          instanceId: saved.instance_uuid, accountUuid: account, workspaceUuid: workspace,
          processorUuid: 'auth-probe', processorKind: 'local',
        }, async () => token);
        await chat.reconnect(); // Requires a decrypted `authenticated` frame for this account/Workspace.
        chat.close();
      }, { saved, token, account, workspace });
      await screenshot(page, 'handoff-bound-instance');
      console.log('Chromium: TOTP approved, enrollment saved, replay rejected, WSS authenticated');
    }
  }
  if (scenario !== 'approve') {
    if (scenario !== 'other-device') await approvalLink.waitFor({ state: 'hidden' });
    await page.reload();
    assert.deepEqual(await instances(), []);
    await zero();
    console.log(`Chromium: ${scenario}; no saved instance, binding, or grant`);
  }
} finally {
  await browser.close();
}
