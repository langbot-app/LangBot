import { expect, test } from '@playwright/test';

import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

const members = [
  {
    uuid: 'membership-owner',
    workspace_uuid: 'workspace-email-test',
    account_uuid: 'account-playwright',
    display_name: 'RockChinQ',
    email: 'rock@example.com',
    role: 'owner',
    status: 'active',
    joined_at: '2026-08-01T00:00:00Z',
    created_at: '2026-08-01T00:00:00Z',
  },
  {
    uuid: 'membership-admin',
    workspace_uuid: 'workspace-email-test',
    account_uuid: 'account-admin',
    display_name: 'Junyan Qin',
    email: 'a.very.long.workspace.member.email.address@example-company.test',
    role: 'admin',
    status: 'active',
    joined_at: '2026-08-02T00:00:00Z',
    created_at: '2026-08-02T00:00:00Z',
  },
];

test.use({ viewport: { width: 390, height: 844 } });

test('workspace member list displays each member email without overlapping controls', async ({
  page,
}, testInfo) => {
  const workspace = makeWorkspaceEntry(
    'workspace-email-test',
    'Email Test Workspace',
    'cloud_projection',
  );
  workspace.membership.display_name = 'RockChinQ';
  workspace.membership.email = 'rock@example.com';

  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  await page.route(
    '**/api/v1/workspaces/workspace-email-test/members',
    (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ code: 0, message: 'ok', data: { members } }),
      }),
  );
  await page.route(
    '**/api/v1/workspaces/workspace-email-test/invitations',
    (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          code: 0,
          message: 'ok',
          data: { invitations: [] },
        }),
      }),
  );

  await page.goto('/home?action=showWorkspaceSettings');

  await expect(page.getByText('RockChinQ')).toBeVisible();
  await expect(page.getByText('rock@example.com')).toBeVisible();
  await expect(page.getByText('Junyan Qin')).toBeVisible();
  const longEmail = page.getByText(
    'a.very.long.workspace.member.email.address@example-company.test',
  );
  await expect(longEmail).toBeVisible();
  await longEmail.scrollIntoViewIfNeeded();

  const roleSelect = page.getByRole('combobox').last();
  const [emailBox, selectBox] = await Promise.all([
    longEmail.boundingBox(),
    roleSelect.boundingBox(),
  ]);
  expect(emailBox).not.toBeNull();
  expect(selectBox).not.toBeNull();
  const overlaps =
    emailBox!.x < selectBox!.x + selectBox!.width &&
    emailBox!.x + emailBox!.width > selectBox!.x &&
    emailBox!.y < selectBox!.y + selectBox!.height &&
    emailBox!.y + emailBox!.height > selectBox!.y;
  expect(overlaps).toBe(false);
  expect(selectBox!.y).toBeGreaterThanOrEqual(emailBox!.y + emailBox!.height);
  await roleSelect.scrollIntoViewIfNeeded();

  await page.screenshot({
    path: testInfo.outputPath('workspace-member-emails-mobile.png'),
    fullPage: true,
  });
});
