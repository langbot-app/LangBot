import assert from 'node:assert/strict';
import { X509Certificate, createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const { chromium } = await import(pathToFileURL(process.env.HARNESS_PLAYWRIGHT));
const f = JSON.parse(process.env.HARNESS_RUNNER_FIXTURE);
const certs = [process.env.NODE_EXTRA_CA_CERTS, process.env.HARNESS_WEB_CERT];
const pins = certs.map(path => createHash('sha256').update(new X509Certificate(readFileSync(path))
  .publicKey.export({ type: 'spki', format: 'der' })).digest('base64')).join(',');
const browser = await chromium.launch({ executablePath: process.env.HARNESS_CHROMIUM,
  args: [`--ignore-certificate-errors-spki-list=${pins}`] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 960 }, locale: 'en-US' });
  page.setDefaultTimeout(8000);
  let hold = false;
  let held;
  const heldMessage = new Promise(resolve => { held = resolve; });
  let closed;
  const closedSocket = new Promise(resolve => { closed = resolve; });
  let sockets = 0;
  const socketUrls = [];
  const harnessRequests = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/v1/harness/')) harnessRequests.push(request);
  });
  await page.routeWebSocket('**/api/v1/harness/ws?**', route => {
    sockets++;
    socketUrls.push(new URL(route.url()));
    const server = route.connectToServer();
    if (!hold) return;
    route.onClose(() => { server.close(); closed(); });
    route.onMessage(frame => {
      if (JSON.parse(frame).seq === '1') held();
      else server.send(frame);
    });
  });
  await page.goto(f.clientOrigin);
  await page.getByRole('button', { name: 'Self-hosted', exact: true }).click();
  await page.locator('#link').fill(f.link);
  await page.locator('#bind-email').fill(f.email);
  await page.locator('#bind-password').fill(f.password);
  await page.locator('#bind-workspace').fill(f.workspace);
  await page.getByRole('button', { name: 'Sign in and bind' }).click();
  await page.getByRole('button', { name: 'Workspace & processor' }).click();
  const agents = page.locator('#chat-processor');
  const choose = async (id) => {
    await agents.locator(`option[value="${id}"]`).waitFor({ state: 'attached' });
    await agents.selectOption(id);
  };
  const send = async (text) => {
    await page.locator('#chat-message').fill(text);
    await page.getByRole('button', { name: 'Send', exact: true }).click();
  };
  const transcript = page.getByRole('list', { name: 'Chat transcript' });
  await choose(f.processors[0]);
  assert.deepEqual(await agents.locator('option').evaluateAll(rows => rows.map(row => row.value).filter(Boolean)), f.processors);
  await send('Hello from Harness Web. Please reply through LocalAgent.');
  await transcript.getByText('Fake LLM response', { exact: true }).waitFor();
  if (process.env.HARNESS_WEB_SCREENSHOT) await page.screenshot({ path: process.env.HARNESS_WEB_SCREENSHOT });

  await transcript.getByRole('button', { name: 'Inspect execution' }).first().click();
  const inspector = page.getByRole('dialog', { name: 'Execution Inspector' });
  await inspector.getByText(/Fake LLM response/).first().waitFor();
  await inspector.getByLabel('Section').selectOption('events');
  await inspector.getByLabel('Records per page').selectOption('1');
  await inspector.getByText('Records 1–1', { exact: true }).waitFor();
  const first = JSON.parse(await inspector.locator('pre').textContent());
  await inspector.getByRole('button', { name: 'Next' }).click();
  await inspector.getByText('Records 2–2', { exact: true }).waitFor();
  const second = JSON.parse(await inspector.locator('pre').textContent());
  assert.ok(first[0].sequence < second[0].sequence);
  if (process.env.HARNESS_INSPECTOR_SCREENSHOT) await page.screenshot({ path: process.env.HARNESS_INSPECTOR_SCREENSHOT });
  await inspector.getByRole('button', { name: 'Previous' }).click();
  await inspector.getByText('Records 1–1', { exact: true }).waitFor();
  assert.deepEqual(JSON.parse(await inspector.locator('pre').textContent()), first);
  await inspector.getByRole('button', { name: 'Close' }).click();
  await page.locator('#chat-attachments').setInputFiles({ name: 'remove-me.txt', mimeType: 'text/plain', buffer: Buffer.from('discard-test-payload') });
  const transfer = await page.evaluateHandle(() => {
    const files = new DataTransfer();
    files.items.add(new File(['keep-test-payload'], 'keep-me.txt', { type: 'text/plain' }));
    return files;
  });
  await page.locator('#chat-message').dispatchEvent('drop', { dataTransfer: transfer });
  await transfer.dispose();
  const remove = page.getByRole('button', { name: /remove.*remove-me\.txt/i });
  await remove.click();
  await page.getByRole('button', { name: 'Remove keep-me.txt' }).waitFor();
  assert.equal(await remove.count(), 0);
  if (process.env.HARNESS_ATTACHMENT_SCREENSHOT) await page.screenshot({ path: process.env.HARNESS_ATTACHMENT_SCREENSHOT });
  await send('This message carries keep-me.txt to the Runner.');
  await transcript.getByText('Fake LLM response', { exact: true }).nth(1).waitFor();
  await transcript.getByText('keep-me.txt', { exact: true }).waitFor();
  assert.equal(await transcript.getByText('remove-me.txt', { exact: true }).count(), 0);
  await transcript.getByRole('button', { name: 'Inspect execution' }).nth(1).click();
  const attachmentInspector = page.getByRole('dialog', { name: 'Execution Inspector' });
  await attachmentInspector.getByText(/keep-me.txt/).first().waitFor();
  assert.equal(await attachmentInspector.getByText(/remove-me\.txt/).count(), 0);
  await attachmentInspector.getByRole('button', { name: 'Close' }).click();
  await choose(f.processors[1]);
  assert.equal(await transcript.getByText('Fake LLM response').count(), 0);
  await send('Second processor, please reply.');
  await transcript.getByText('Fake LLM response', { exact: true }).waitFor();

  // Keep one authenticated socket pending by holding the outbound turn at the browser boundary.
  hold = true;
  await send('Pending turn for workspace switch check.');
  await heldMessage;
  const switchTo = async (id) => {
    await page.locator('#directory-workspace').selectOption(id);
    await page.getByRole('button', { name: 'Switch workspace' }).click();
    await agents.waitFor();
  };
  await switchTo(f.viewerWorkspace);
  await closedSocket;
  await agents.getByText('No agents available for chat in this workspace.').waitFor({ state: 'attached' });
  assert.equal(await page.locator('#chat-message').count(), 0);
  assert.equal(sockets, 4);
  hold = false;
  await switchTo(f.workspace);
  await choose(f.processors[0]);
  await transcript.getByText('Fake LLM response', { exact: true }).nth(1).waitFor();
  await send('Back in the original workspace on a new connection.');
  await transcript.getByText('Fake LLM response', { exact: true }).nth(2).waitFor();
  assert.equal(sockets, 5);
  if (f.relayOrigin) {
    assert.ok(socketUrls.every(url => `https://${url.host}` === f.relayOrigin));
    const rpcPaths = new Set();
    const enrollmentPaths = new Set();
    for (const request of harnessRequests) {
      const { origin, pathname } = new URL(request.url());
      if (pathname === '/api/v1/harness/rpc' || pathname === '/api/v1/harness/rpc/handshake') {
        assert.equal(origin, f.relayOrigin);
        rpcPaths.add(pathname);
        if (pathname.endsWith('/rpc')) {
          const frame = request.postDataJSON();
          assert.ok(frame.frame.box);
          assert.deepEqual(Object.keys(frame).sort(), ['device_kid', 'frame', 'harness_id', 'hs2', 'nonce_s', 'pinned_kid', 'v']);
          // Do not log the body even if an unexpected plaintext field appears.
          assert.ok(!request.postData().includes(f.password));
        }
      } else {
        assert.equal(origin, f.origin);
        enrollmentPaths.add(pathname);
      }
    }
    assert.equal(rpcPaths.size, 2);
    assert.ok(enrollmentPaths.has('/api/v1/harness/register'));
    assert.ok([...enrollmentPaths].some(path => path.endsWith('/devices')));
  }
} finally { await browser.close(); }
