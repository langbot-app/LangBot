import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

test('terminal invitation errors refresh on a new fragment and allow account switching', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    storage: {
      token: 'playwright-token',
      userEmail: 'another-account@example.com',
    },
  });
  await page.route('**/api/v1/invitations/inspect', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}') as {
      token?: string;
    };
    const code =
      body.token === 'revoked-invitation'
        ? 'invitation_revoked'
        : 'invitation_used';
    await route.fulfill({
      status: 410,
      contentType: 'application/json',
      body: JSON.stringify({ code, msg: code }),
    });
  });

  await page.goto('/invitations/accept#token=used-invitation');
  await expect(
    page.getByText('This invitation was already used.'),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        sessionStorage.getItem('langbot_pending_invitation_token'),
      ),
    )
    .toBeNull();

  await page.evaluate(() => {
    window.location.hash = 'token=revoked-invitation';
  });
  await expect(page.getByText('This invitation was revoked.')).toBeVisible();

  await page.getByRole('button', { name: 'Back to sign in' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Welcome')).toBeVisible();
  expect(
    await page.evaluate(() => ({
      token: localStorage.getItem('token'),
      userEmail: localStorage.getItem('userEmail'),
    })),
  ).toEqual({ token: null, userEmail: null });
});
