import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

for (const invitation of [false, true]) {
  test(`Cloud login starts standard OAuth, invitation=${invitation}`, async ({
    page,
  }) => {
    await installLangBotApiMocks(page);
    await page.route('**/api/v1/system/info', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            edition: 'cloud',
            deployment_mode: 'cloud',
            cloud_service_url: 'https://space.langbot.app',
            wizard_status: 'completed',
          },
        },
      }),
    );
    await page.route('**/api/v1/user/account-info', (route) =>
      route.fulfill({
        json: {
          code: 0,
          data: {
            initialized: true,
            password_login_enabled: false,
            space_login_enabled: true,
            authenticated_invitation_acceptance_enabled: true,
          },
        },
      }),
    );
    if (invitation)
      await page.addInitScript(() =>
        sessionStorage.setItem(
          'langbot_pending_invitation_token',
          'invited-token',
        ),
      );
    let redirectUri: string | null = null;
    await page.route('**/api/v1/user/space/authorize-url**', async (route) => {
      redirectUri = new URL(route.request().url()).searchParams.get(
        'redirect_uri',
      );
      await route.fulfill({
        json: { code: 0, data: { authorize_url: '/oauth-provider' } },
      });
    });
    await page.route('**/oauth-provider', (route) =>
      route.fulfill({
        contentType: 'text/html',
        body: '<h1>OAuth provider</h1>',
      }),
    );
    await page.goto(invitation ? '/login?invitation=1' : '/login');
    await page
      .getByRole('button', { name: 'Login with LangBot Account', exact: true })
      .click();
    await expect(page).toHaveURL(/\/oauth-provider$/);
    expect(redirectUri).toBe(new URL('/auth/space/callback', page.url()).href);
    expect(
      await page.evaluate(() =>
        sessionStorage.getItem('langbot_pending_invitation_token'),
      ),
    ).toBe(invitation ? 'invited-token' : null);
  });
}

for (const [code, title, message] of [
  [
    'space_account_not_registered',
    'Account not registered',
    'No local account is registered for this LangBot Account email. Ask the Workspace owner for an invitation.',
  ],
  [
    'space_account_binding_required',
    'LangBot Account connection required',
    'This local account must connect a LangBot Account from Account settings before using LangBot Account login.',
  ],
]) {
  test(`OAuth callback explains ${code}`, async ({ page }) => {
    await installLangBotApiMocks(page);
    await page.route('**/api/v1/user/space/callback', (route) =>
      route.fulfill({
        status: 403,
        json: { code, msg: 'Generic upstream message' },
      }),
    );
    await page.goto('/auth/space/callback?code=code&state=state');
    await expect(page.getByText(title, { exact: true })).toBeVisible();
    await expect(page.getByText(message, { exact: true })).toBeVisible();
    await expect(
      page.getByText('Generic upstream message', { exact: true }),
    ).toHaveCount(0);
    await page
      .getByRole('button', { name: 'Back to Login', exact: true })
      .click();
    await expect(page).toHaveURL(/\/login$/);
    expect(await page.evaluate(() => localStorage.getItem('token'))).toBeNull();
  });
}
