import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
const require = createRequire(new URL('../../web/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const { token } = JSON.parse(await readFile('browser-auth.json', 'utf8'));
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  const responses = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => {
    if (r.url().includes('/monitoring/')) responses.push({ path: new URL(r.url()).pathname, status: r.status() });
  });
  await page.addInitScript(token => { localStorage.setItem('token', token); localStorage.setItem('i18nextLng', 'en-US'); }, token);
  const dataReady = page.waitForResponse(r => r.url().includes('/api/v1/monitoring/executions?') && r.status() === 200, { timeout: 20000 });
  await page.goto('http://127.0.0.1:14000/home/monitoring', { waitUntil: 'domcontentloaded', timeout: 20000 });
  try {
    await dataReady;
    await page.locator('#monitoring-filter-bot').waitFor({ timeout: 20000 });
    const skipGuide = page.getByRole('button', { name: 'Skip', exact: true });
    if (await skipGuide.isVisible()) await skipGuide.click();
    await page.getByText('LANG17 response gate', { exact: true }).first().waitFor({ timeout: 10000 });
  } finally {
    await page.screenshot({ path: 'monitoring.png', fullPage: true });
    await writeFile('browser-result.json', JSON.stringify({ url: page.url(), body: await page.locator('body').innerText(), errors, responses }, null, 2));
  }
  if (errors.length) throw new Error('Browser errors; inspect browser-result.json');
} finally {
  await browser.close();
}
