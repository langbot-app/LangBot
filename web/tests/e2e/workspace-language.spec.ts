import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

test('workspace language persists independently of personal UI language', async ({
  page,
}, testInfo) => {
  const workspace = makeWorkspaceEntry(
    'workspace-language',
    'Language Workspace',
    'local',
  );
  workspace.permissions = ['workspace.view', 'workspace.update'];
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  let language = 'en_US';
  await page.route('**/api/v1/workspaces/current/language', async (route) => {
    if (route.request().method() === 'PUT') {
      expect(route.request().headers()['x-workspace-id']).toBe(
        'workspace-language',
      );
      language = route.request().postDataJSON().language;
    }
    await route.fulfill({
      json: {
        code: 0,
        msg: 'ok',
        data: {
          language,
          supported_languages: ['en_US', 'zh_Hans', 'ja_JP'],
        },
      },
    });
  });
  await page.goto('/home?action=showWorkspaceSettings');
  const select = page.getByRole('combobox', {
    name: 'Workspace language',
    exact: true,
  });
  await expect(select).toHaveText('English');
  await select.click();
  await page.getByRole('option', { name: '日本語', exact: true }).click();
  await expect(select).toHaveText('日本語');
  await expect(page.getByText('Language saved', { exact: true })).toBeVisible();
  await page.reload();
  await page.goto('/home?action=showWorkspaceSettings');
  await expect(select).toHaveText('日本語');
  await expect(
    page.getByText('Workspace language', { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: testInfo.outputPath('workspace-language.png'),
    fullPage: true,
  });
});

test('viewer can read but cannot edit workspace language', async ({ page }) => {
  const workspace = makeWorkspaceEntry(
    'workspace-language',
    'Language Workspace',
    'local',
  );
  workspace.membership.role = 'viewer';
  workspace.permissions = ['workspace.view'];
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  await page.goto('/home?action=showWorkspaceSettings');
  const select = page.getByRole('combobox', {
    name: 'Workspace language',
    exact: true,
  });
  await expect(select).toHaveText('English');
  await expect(select).toBeDisabled();
});
