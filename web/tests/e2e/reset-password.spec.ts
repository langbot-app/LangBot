import { expect, test, type Page } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const resetEndpoint = '**/api/v1/user/reset-password';
const email = 'reset-password@example.com';
const newPassword = 'Regression-password-2026!';
const successMessage = 'Password reset successfully, please login';
const failureMessage =
  'Password reset failed, please check your email and recovery key';

async function fillResetForm(page: Page, recoveryKey: string) {
  await page.goto('/reset-password');
  await page.getByPlaceholder('Enter email address').fill(email);
  const recoveryInput = page.getByPlaceholder('Enter recovery key');
  await recoveryInput.fill(recoveryKey);
  await expect(recoveryInput).toHaveValue(recoveryKey);
  await page.getByPlaceholder('Enter new password').fill(newPassword);
}

test.beforeEach(async ({ page }) => {
  await installLangBotApiMocks(page, { authenticated: false });
});

const recoveryKeys = [
  { name: 'eight-character recovery code', value: '2A3B4C5D' },
  { name: 'six-character legacy recovery key', value: 'ABC123' },
  {
    name: '43-character mixed-case base64url recovery key',
    value: 'aB-_'.repeat(10) + 'xYz',
  },
];

for (const { name, value } of recoveryKeys) {
  test(`submits the ${name} verbatim and returns to login`, async ({
    page,
  }) => {
    const requests: { method: string; body: unknown }[] = [];
    await page.route(resetEndpoint, async (route) => {
      requests.push({
        method: route.request().method(),
        body: route.request().postDataJSON(),
      });
      await route.fulfill({
        status: 200,
        json: { code: 0, msg: 'ok', data: { user: email } },
      });
    });

    await fillResetForm(page, value);
    await page
      .getByRole('button', { name: 'Reset Password', exact: true })
      .click();

    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByText(successMessage, { exact: true })).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Login with password', exact: true }),
    ).toBeVisible();
    expect(requests).toEqual([
      {
        method: 'POST',
        body: { user: email, recovery_key: value, new_password: newPassword },
      },
    ]);
    await expect(page.getByText(failureMessage, { exact: true })).toHaveCount(
      0,
    );
  });
}

test('HTTP 429 shows failure, stays on reset-password, and reenables submission', async ({
  page,
}) => {
  const recoveryKey = '2A3B4C5D';
  const requests: { method: string; body: unknown }[] = [];
  let releaseResponse!: () => void;
  const responseGate = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  await page.route(resetEndpoint, async (route) => {
    requests.push({
      method: route.request().method(),
      body: route.request().postDataJSON(),
    });
    await responseGate;
    await route.fulfill({
      status: 429,
      json: { code: -1, msg: 'Too many attempts, try again later' },
    });
  });

  await fillResetForm(page, recoveryKey);
  const submit = page.locator('button[type="submit"]');
  await submit.click();
  try {
    await expect.poll(() => requests.length).toBe(1);
    await expect(submit).toBeDisabled();
    await expect(submit).toHaveText('Resetting...');
  } finally {
    releaseResponse();
  }

  await expect(page.getByText(failureMessage, { exact: true })).toBeVisible();
  await expect(submit).toBeEnabled();
  await expect(submit).toHaveText('Reset Password');
  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.getByText(successMessage, { exact: true })).toHaveCount(0);
  await expect(page.getByPlaceholder('Enter recovery key')).toHaveValue(
    recoveryKey,
  );
  expect(requests).toEqual([
    {
      method: 'POST',
      body: {
        user: email,
        recovery_key: recoveryKey,
        new_password: newPassword,
      },
    },
  ]);
});
