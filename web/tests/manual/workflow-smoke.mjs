import { chromium, expect } from '@playwright/test';
import { createServer } from 'vite';

const server = await createServer({
  server: { host: '127.0.0.1', port: 15345, strictPort: true },
});
let browser;
try {
  await server.listen();
  browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    args: ['--no-sandbox'],
  });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  page.on('pageerror', (error) => console.error(error.message));
  await page.addInitScript((token) => {
    localStorage.setItem('token', token);
    localStorage.setItem('userEmail', 'workflow-smoke@example.com');
    localStorage.setItem('langbot_language', 'en-US');
    localStorage.setItem('langbot_sidebar_guide_v1', 'completed');
  }, process.env.WORKFLOW_SMOKE_TOKEN);
  await page.goto(
    `http://127.0.0.1:15345/home/workflows?id=${process.env.WORKFLOW_SMOKE_UUID}`,
  );
  await page.getByRole('tab', { name: /Execution/ }).click({ timeout: 60000 });
  const completed = page.getByRole('button', { name: /— completed/ });
  await expect(completed).toHaveCount(2);
  await completed.first().click();
  await expect(page.locator('summary')).toHaveCount(3);
  await page.screenshot({
    path: process.env.WORKFLOW_SMOKE_SCREENSHOT,
    fullPage: true,
  });
  console.log(
    'Real WebUI: two completed executions, three persisted node records',
  );
} finally {
  await browser?.close();
  await server.close();
}
