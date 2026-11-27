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
  await page.routeWebSocket('**/api/v1/harness/ws?**', route => {
    sockets++;
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
  assert.equal(sockets, 3);
  hold = false;
  await switchTo(f.workspace);
  await choose(f.processors[0]);
  await transcript.getByText('Fake LLM response', { exact: true }).waitFor();
  await send('Back in the original workspace on a new connection.');
  await transcript.getByText('Fake LLM response', { exact: true }).nth(1).waitFor();
  assert.equal(sockets, 4);
} finally { await browser.close(); }
