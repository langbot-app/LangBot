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

test('a temporary accept failure keeps the authenticated invitation retryable', async ({
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
            uuid: 'retryable-invitation',
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
  let acceptAttempts = 0;
  await page.route('**/api/v1/invitations/accept', async (route) => {
    acceptAttempts += 1;
    if (acceptAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'temporary_failure',
          msg: 'Please retry',
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        data: {
          token: 'accepted-token',
          workspace_uuid: 'workspace-playwright',
        },
        msg: 'ok',
      }),
    });
  });

  await page.goto('/invitations/accept#token=retryable-invitation');
  await page.getByRole('button', { name: 'I already have an account' }).click();
  await page
    .getByPlaceholder('Enter email address')
    .fill('invited@example.com');
  await page.getByPlaceholder('Enter password').fill('password');
  await page.getByRole('button', { name: 'Login with password' }).click();

  await expect(page).toHaveURL(/\/invitations\/accept$/);
  await expect(
    page.getByRole('button', { name: 'Accept with current account' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Accept with current account' })
    .click();
  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/);
  expect(acceptAttempts).toBe(2);
});
