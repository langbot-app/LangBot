import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

async function installApiKeyMocks(page: Page) {
  await installLangBotApiMocks(page, { authenticated: true });
  const state = {
    failDeletion: false,
    keys: [
      {
        id: 1,
        uuid: 'active-api-key',
        name: 'Active integration key',
        description: '',
        scopes: [],
        status: 'active',
        secret_available: false,
        created_at: '2026-01-01T00:00:00',
      },
      {
        id: 2,
        uuid: 'revoked-api-key',
        name: 'Previously revoked key',
        description: '',
        scopes: [],
        status: 'revoked',
        secret_available: false,
        created_at: '2026-01-01T00:00:00',
      },
    ],
  };
  await page.route('**/api/v1/apikeys**', async (route) => {
    if (route.request().method() === 'DELETE') {
      if (state.failDeletion) {
        return route.fulfill({
          status: 500,
          json: { code: 1, msg: 'Unable to revoke API key' },
        });
      }
      const id = Number(
        new URL(route.request().url()).pathname.split('/').pop(),
      );
      const key = state.keys.find((item) => item.id === id);
      expect(key).toBeDefined();
      // Match the backend: revocation keeps the key in subsequent list responses.
      key!.status = 'revoked';
      return route.fulfill({ json: { code: 0, data: {} } });
    }
    return route.fulfill({ json: { code: 0, data: { keys: state.keys } } });
  });
  await page.route('**/api/v1/webhooks', (route) =>
    route.fulfill({ json: { code: 0, data: { webhooks: [] } } }),
  );
  return state;
}

test('only active API keys appear in a mixed list', async ({ page }) => {
  await installApiKeyMocks(page);
  await page.goto('/home?action=showApiIntegrationSettings');
  await expect(
    page.getByRole('row', { name: /Active integration key/ }),
  ).toBeVisible();
  await expect(
    page.getByRole('row', { name: /Previously revoked key/ }),
  ).toHaveCount(0);
});

test('revoked API keys disappear after deletion and stay hidden on reload', async ({
  page,
}, testInfo) => {
  const state = await installApiKeyMocks(page);
  await page.goto('/home?action=showApiIntegrationSettings');
  const activeRow = page.getByRole('row', { name: /Active integration key/ });
  await expect(activeRow).toBeVisible();
  await activeRow.getByRole('button', { name: 'Delete', exact: true }).click();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  await expect(
    page.getByText('API key deleted successfully', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('after-revocation.png') });
  await expect(activeRow).toHaveCount(0);
  await expect(
    page.getByText('No API keys configured', { exact: true }),
  ).toBeVisible();
  expect(state.keys.map((key) => key.status)).toEqual(['revoked', 'revoked']);

  await page.reload();
  await page.goto('/home?action=showApiIntegrationSettings');
  await expect(
    page.getByText('No API keys configured', { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole('table')).toHaveCount(0);
});

test('failed revocation keeps the active API key visible', async ({ page }) => {
  const state = await installApiKeyMocks(page);
  state.failDeletion = true;
  await page.goto('/home?action=showApiIntegrationSettings');
  const activeRow = page.getByRole('row', { name: /Active integration key/ });
  await activeRow.getByRole('button', { name: 'Delete', exact: true }).click();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Delete', exact: true })
    .click();
  await expect(page.getByText(/Failed to delete API key:/)).toBeVisible();
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Cancel', exact: true })
    .click();
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await expect(activeRow).toBeVisible();
  expect(state.keys[0].status).toBe('active');
});
