import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

test('local account login reaches the authenticated home shell', async ({
  page,
}) => {
  await installLangBotApiMocks(page);

  await page.goto('/login');

  await expect(page.getByText('Welcome')).toBeVisible();
  await page.getByPlaceholder('Enter email address').fill('admin@example.com');
  await page.getByPlaceholder('Enter password').fill('password');
  await page.getByRole('button', { name: 'Login with password' }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText('Home').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('Total Messages').first()).toBeVisible();
  await expect(page.getByText('Unable to connect to server')).toHaveCount(0);
});
