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
  const rows = page.getByTestId('workflow-execution-row');
  await expect(rows).toHaveCount(3);
  await expect(rows.filter({ hasText: 'Completed' })).toHaveCount(3);
  await rows.nth(1).click();
  const detail = page.getByTestId('workflow-execution-detail');
  await expect(detail.getByText('Bot message')).toBeVisible();
  await expect(detail.getByText('Steps (3)')).toBeVisible();
  await page.screenshot({
    path: process.env.WORKFLOW_SMOKE_SCREENSHOT,
    fullPage: true,
  });
  // Messages a bot route delivered to the Workflow are named in monitoring.
  await page.goto('http://127.0.0.1:15345/home/monitoring');
  const workflowRows = page.getByTestId('execution-kind-workflow');
  await expect(workflowRows.first()).toBeVisible({ timeout: 60000 });
  await expect(
    page.getByText('Workflow EBA smoke', { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({
    path: process.env.WORKFLOW_SMOKE_SCREENSHOT.replace(
      /\.png$/,
      '-monitoring.png',
    ),
  });
  console.log(
    'Real WebUI: three completed executions, three persisted node records, Workflow rows named in monitoring',
  );
} finally {
  await browser?.close();
  await server.close();
}
