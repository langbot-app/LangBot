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
