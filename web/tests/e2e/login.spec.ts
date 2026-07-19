import { expect, test } from '@playwright/test';

import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

test('local account login reaches the authenticated home shell', async ({
  page,
}) => {
  await installLangBotApiMocks(page);

  await page.goto('/login');

  await expect(page.getByText('Welcome')).toBeVisible();
  await page.getByPlaceholder('Enter email address').fill('admin@example.com');
  await page.getByPlaceholder('Enter password').fill('password');
  await page.getByRole('button', { name: 'Login with password' }).click();

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/);
  await expect(page.getByText('Home').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('Total Messages').first()).toBeVisible();
  await expect(page.getByText('Unable to connect to server')).toHaveCount(0);
});

test('an existing Account token bootstraps the singleton without a selector loop', async ({
  page,
}) => {
  const bootstrapWorkspaceHeaders: Array<string | undefined> = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/workspaces/bootstrap') {
      bootstrapWorkspaceHeaders.push(request.headers()['x-workspace-id']);
    }
  });

  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto('/login');

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/);
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
  expect(bootstrapWorkspaceHeaders.length).toBeGreaterThan(0);
  expect(bootstrapWorkspaceHeaders.every((header) => !header)).toBe(true);
});

test('multi-Workspace login waits for an explicit selection', async ({
  page,
}) => {
  const accountScopedRequests: { path: string; workspace?: string }[] = [];
  const selectedWorkspaceHeaders: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    const workspace = request.headers()['x-workspace-id'];
    if (
      path === '/api/v1/user/auth' ||
      path === '/api/v1/user/check-token' ||
      path === '/api/v1/workspaces/bootstrap'
    ) {
      accountScopedRequests.push({ path, workspace });
    }
    if (path === '/api/v1/workspaces/current' && workspace) {
      selectedWorkspaceHeaders.push(workspace);
    }
  });

  await installLangBotApiMocks(page, {
    storage: {
      langbot_active_workspace_uuid: 'workspace-from-another-account',
    },
    workspaces: [
      makeWorkspaceEntry('workspace-alpha', 'Alpha Workspace'),
      makeWorkspaceEntry('workspace-beta', 'Beta Workspace'),
    ],
  });

  await page.goto('/login');
  await page.getByPlaceholder('Enter email address').fill('admin@example.com');
  await page.getByPlaceholder('Enter password').fill('password');
  await page.getByRole('button', { name: 'Login with password' }).click();

  await expect(page).toHaveURL(/\/workspaces\/select/);
  await expect(
    page.getByRole('heading', { name: 'Choose a Workspace' }),
  ).toBeVisible();
  await expect(page.getByText('Alpha Workspace')).toBeVisible();
  await expect(page.getByText('Beta Workspace')).toBeVisible();

  await page.getByRole('button', { name: /Beta Workspace/ }).click();

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/);
  await expect(
    page.getByRole('combobox', { name: 'Switch Workspace' }),
  ).toBeVisible();
  expect(selectedWorkspaceHeaders).toContain('workspace-beta');
  expect(accountScopedRequests.length).toBeGreaterThan(0);
  expect(accountScopedRequests.every((request) => !request.workspace)).toBe(
    true,
  );
});

test('Space OAuth bootstraps a singleton before entering home', async ({
  page,
}) => {
  const selectedWorkspaceHeaders: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    const workspace = request.headers()['x-workspace-id'];
    if (path === '/api/v1/workspaces/current' && workspace) {
      selectedWorkspaceHeaders.push(workspace);
    }
  });

  await installLangBotApiMocks(page);
  await page.goto('/auth/space/callback?code=oauth-code&state=oauth-state');

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/, {
    timeout: 5_000,
  });
  expect(selectedWorkspaceHeaders).toContain('workspace-playwright');
});

test('Space OAuth sends a multi-Workspace Account to the chooser', async ({
  page,
}) => {
  const bootstrapWorkspaceHeaders: Array<string | undefined> = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/workspaces/bootstrap') {
      bootstrapWorkspaceHeaders.push(request.headers()['x-workspace-id']);
    }
  });

  await installLangBotApiMocks(page, {
    workspaces: [
      makeWorkspaceEntry('workspace-alpha', 'Alpha Workspace'),
      makeWorkspaceEntry('workspace-beta', 'Beta Workspace'),
    ],
  });
  await page.goto('/auth/space/callback?code=oauth-code&state=oauth-state');

  await expect(page).toHaveURL(/\/workspaces\/select/, { timeout: 5_000 });
  await expect(page.getByText('Alpha Workspace')).toBeVisible();
  await expect(page.getByText('Beta Workspace')).toBeVisible();
  expect(bootstrapWorkspaceHeaders.length).toBeGreaterThan(0);
  expect(bootstrapWorkspaceHeaders.every((header) => !header)).toBe(true);
});
