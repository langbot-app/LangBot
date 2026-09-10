import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const failure of [
  {
    status: 400,
    code: 'invalid_bot_config',
    msg: 'Lark missing required config: app_id, app_secret, bot_name',
  },
  {
    status: 400,
    code: 'bot_apply_failed',
    msg: 'Lark missing required config: app_id, app_secret, bot_name',
  },
  {
    status: 500,
    code: 'internal_error',
    msg: 'Internal server error',
    request_id: 'bot-save-test-reference',
  },
]) {
  test(`bot save displays actionable ${failure.code}`, async ({ page }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    await page.goto('/home/bots?id=new');
    await page.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Playwright Adapter' }).click();
    await page.locator('input[name="name"]').fill('Error Test Bot');
    await page.getByRole('button', { name: /^Submit$/ }).click();
    await expect(page).toHaveURL(/\/home\/bots\?id=bot-1$/);
    await page.route('**/api/v1/platform/bots/bot-1', async (route) => {
      if (route.request().method() !== 'PUT') return route.fallback();
      await route.fulfill({
        status: failure.status,
        contentType: 'application/json',
        body: JSON.stringify(failure),
      });
    });
    await page.getByRole('button', { name: 'Edit basic information' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Name', { exact: true }).fill('Edited Bot');
    await dialog.getByRole('button', { name: /^Save$/ }).click();
    if (failure.code === 'internal_error') {
      await expect(
        page.getByText('Error reference: bot-save-test-reference'),
      ).toBeVisible();
    } else {
      await expect(page.getByText(failure.msg, { exact: true })).toBeVisible();
    }
    if (failure.code === 'bot_apply_failed') {
      await expect(
        page.getByText('Configuration saved, but could not be applied'),
      ).toBeVisible();
    }
  });
}
