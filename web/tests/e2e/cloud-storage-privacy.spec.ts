import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

function wrapped(data: unknown) {
  return JSON.stringify({
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  });
}

test('Cloud never exposes or requests storage analysis', async ({ page }) => {
  const workspace = makeWorkspaceEntry(
    'workspace-cloud',
    'Cloud Workspace',
    'cloud_projection',
  );
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  await page.route(
    /\/api\/v1\/workspaces\/workspace-cloud\/(members|invitations)$/,
    async (route) => {
      const collection = route.request().url().endsWith('/members')
        ? 'members'
        : 'invitations';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: wrapped({ [collection]: [] }),
      });
    },
  );

  let storageAnalysisRequests = 0;
  await page.route('**/api/v1/system/storage-analysis', async (route) => {
    storageAnalysisRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: wrapped({}),
    });
  });

  await page.goto('/home/bots');
  await page.getByRole('button', { name: /admin@example\.com/i }).click();
  await expect(page.getByText('Storage Analysis', { exact: true })).toHaveCount(
    0,
  );

  await page.goto('/home/bots?action=showStorageAnalysis');
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Workspace' })).toBeVisible();
  await expect(page.getByText('Storage Analysis', { exact: true })).toHaveCount(
    0,
  );
  expect(storageAnalysisRequests).toBe(0);
});

test('an OSS owner opens storage analysis from its storage-icon menu item', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let requests = 0;
  await page.route('**/api/v1/system/storage-analysis', async (route) => {
    requests++;
    await route.fulfill({
      json: {
        code: 0,
        data: {
          generated_at: '2026-10-17T00:00:00Z',
          total_size_bytes: 123,
          sections: [],
          cleanup_policy: {
            uploaded_file_retention_days: 7,
            log_retention_days: 14,
          },
          database: {
            type: 'sqlite',
            monitoring_counts: {},
            binary_storage: { count: 0, size_bytes: 0 },
          },
          cleanup_candidates: { uploaded_files: [], log_files: [] },
          tasks: {},
        },
      },
    });
  });
  await page.goto('/home/bots');
  await page.getByRole('button', { name: /admin@example\.com/i }).click();
  const menuItem = page.getByRole('menuitem', {
    name: 'Storage Analysis',
    exact: true,
  });
  await expect(menuItem).toBeVisible();
  await expect(menuItem.locator('svg.lucide-hard-drive')).toBeVisible();
  await menuItem.click();
  await expect(
    page
      .getByRole('dialog')
      .getByRole('button', { name: 'Refresh', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('dialog').getByText('123 B', { exact: true }),
  ).toBeVisible();
  await expect.poll(() => requests).toBeGreaterThan(0);
});
