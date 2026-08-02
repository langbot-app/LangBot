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

test('login preserves an explicit invitation email mismatch error', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: false });
  await page.route('**/api/v1/invitations/inspect', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          invitation: {
            uuid: 'mismatch-invitation',
            workspace_uuid: 'workspace-playwright',
            normalized_email: 'invited@example.com',
            role: 'viewer',
            status: 'pending',
          },
          workspace: {
            uuid: 'workspace-playwright',
            name: 'Playwright Workspace',
          },
        },
        msg: 'ok',
      }),
    });
  });
  await page.route('**/api/v1/invitations/accept', async (route) => {
    await route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 'invitation_email_mismatch',
        msg: 'Invitation email does not match the Account',
      }),
    });
  });

  await page.goto('/invitations/accept#token=mismatch-invitation');
  await page.getByRole('button', { name: 'I already have an account' }).click();
  await page.getByPlaceholder('Enter email address').fill('other@example.com');
  await page.getByPlaceholder('Enter password').fill('password');
  await page.getByRole('button', { name: 'Login with password' }).click();

  await expect(page).toHaveURL(
    /\/invitations\/accept\?error=invitation_email_mismatch$/,
  );
  await expect(
    page.getByText('This invitation belongs to a different email address.'),
  ).toBeVisible();
  await expect(page.getByText('Login successful')).toHaveCount(0);
});

test('an authenticated OSS invitation requires logout before registration', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    storage: {
      token: 'playwright-token',
      userEmail: 'invited@example.com',
    },
  });
  await page.route('**/api/v1/invitations/inspect', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          invitation: {
            uuid: 'logout-invitation',
            workspace_uuid: 'workspace-playwright',
            normalized_email: 'invited@example.com',
            role: 'viewer',
            status: 'pending',
          },
          workspace: {
            uuid: 'workspace-playwright',
            name: 'Playwright Workspace',
          },
        },
        msg: 'ok',
      }),
    });
  });

  await page.goto('/invitations/accept#token=logout-invitation');
  await expect(
    page.getByText(
      'Sign out first, then sign in with the invited account. Your invitation will be preserved.',
    ),
  ).toBeVisible();
  await page
    .getByRole('button', {
      name: 'Sign out and return to this invitation',
    })
    .click();

  await expect(page).toHaveURL(/\/login\?invitation=1$/);
  expect(
    await page.evaluate(() => ({
      token: localStorage.getItem('token'),
      userEmail: localStorage.getItem('userEmail'),
      invitation: sessionStorage.getItem('langbot_pending_invitation_token'),
    })),
  ).toEqual({
    token: null,
    userEmail: null,
    invitation: 'logout-invitation',
  });
});

test('Space OAuth accepts a pending invitation with the freshly authenticated account', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: false,
    storage: {
      token: 'stale-other-account-token',
      userEmail: 'other@example.com',
    },
  });
  await page.addInitScript(() => {
    sessionStorage.setItem(
      'langbot_pending_invitation_token',
      'matching-invitation',
    );
  });

  await page.route('**/api/v1/user/space/callback', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          token: 'fresh-invited-account-token',
          user: 'invited@example.com',
        },
        msg: 'ok',
      }),
    });
  });
  await page.route('**/api/v1/user/info', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          account_uuid: 'invited-account',
          user: 'invited@example.com',
          account_type: 'space',
          has_password: false,
        },
        msg: 'ok',
      }),
    });
  });

  let acceptanceAuthorization = '';
  await page.route('**/api/v1/invitations/accept', async (route) => {
    acceptanceAuthorization = route.request().headers().authorization ?? '';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          token: 'accepted-invited-account-token',
          workspace_uuid: 'workspace-playwright',
        },
        msg: 'ok',
      }),
    });
  });

  await page.goto('/auth/space/callback?code=oauth-code&state=oauth-state');

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/, {
    timeout: 5_000,
  });
  expect(acceptanceAuthorization).toBe('Bearer fresh-invited-account-token');
  expect(
    await page.evaluate(() => ({
      token: localStorage.getItem('token'),
      userEmail: localStorage.getItem('userEmail'),
      invitation: sessionStorage.getItem('langbot_pending_invitation_token'),
    })),
  ).toEqual({
    token: 'accepted-invited-account-token',
    userEmail: 'invited@example.com',
    invitation: null,
  });
});
