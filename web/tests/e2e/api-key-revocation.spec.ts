import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

function apiKey(id: number, name: string, status: 'active' | 'revoked') {
  return {
    id,
    uuid: `key-${id}`,
    name,
    description: '',
    scopes: [],
    status,
    secret_available: false,
    created_at: '2026-10-18T00:00:00Z',
  };
}

async function installKeyMocks(
  page: Page,
  keys: ReturnType<typeof apiKey>[],
  deleteFails = false,
) {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route(/\/api\/v1\/apikeys(?:\/\d+)?$/, async (route) => {
    if (route.request().method() === 'DELETE') {
      if (deleteFails) {
        await route.fulfill({
          status: 500,
          json: { code: 500, message: 'Could not revoke key' },
        });
        return;
      }
      const id = Number(
        new URL(route.request().url()).pathname.split('/').pop(),
      );
      keys.find((key) => key.id === id)!.status = 'revoked';
      await route.fulfill({ json: { code: 0, data: {} } });
      return;
    }
    // Revocation retains the audit record in every subsequent list response.
    await route.fulfill({ json: { code: 0, data: { keys } } });
  });
  await page.route('**/api/v1/webhooks', (route) =>
    route.fulfill({ json: { code: 0, data: { webhooks: [] } } }),
  );
}

test('API key list hides revoked records while keeping active keys after reload', async ({
  page,
}) => {
  await installKeyMocks(page, [
    apiKey(1, 'Current integration', 'active'),
    apiKey(2, 'Revoked integration', 'revoked'),
  ]);
  await page.goto('/home/bots?action=showApiIntegrationSettings');

  await expect(
    page.getByRole('cell', { name: 'Current integration' }),
  ).toBeVisible();
  await expect(
    page.getByRole('cell', { name: 'Revoked integration' }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole('cell', { name: 'Current integration' }),
  ).toBeVisible();
  await expect(
    page.getByRole('cell', { name: 'Revoked integration' }),
  ).toHaveCount(0);
});

test('deleting the last active API key shows the empty state after soft deletion and reload', async ({
  page,
}) => {
  const keys = [apiKey(1, 'Disposable integration', 'active')];
  await installKeyMocks(page, keys);
  await page.goto('/home/bots?action=showApiIntegrationSettings');

  await page
    .getByRole('row', { name: /Disposable integration/ })
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Delete', exact: true })
    .click();

  await expect(
    page.getByText('API key deleted successfully', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('No API keys configured', { exact: true }),
  ).toBeVisible();
  expect(keys).toHaveLength(1);
  expect(keys[0].status).toBe('revoked');

  await page.reload();
  await expect(
    page.getByText('No API keys configured', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('cell', { name: 'Disposable integration' }),
  ).toHaveCount(0);
});

test('a failed revocation keeps the active API key visible', async ({
  page,
}) => {
  const keys = [apiKey(1, 'Still active integration', 'active')];
  await installKeyMocks(page, keys, true);
  await page.goto('/home/bots?action=showApiIntegrationSettings');

  const row = page.getByRole('row', { name: /Still active integration/ });
  await row.getByRole('button', { name: 'Delete', exact: true }).click();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Delete', exact: true })
    .click();

  await expect(page.getByText(/Failed to delete API key:/)).toBeVisible();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Cancel', exact: true })
    .click();
  await expect(row).toBeVisible();
  expect(keys[0].status).toBe('active');
});
