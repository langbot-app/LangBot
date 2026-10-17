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
  await expect(page.getByText('Execution Success Rate').first()).toBeVisible();
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
  const workspaceSwitcher = page
    .getByRole('button', {
      name: /Switch Workspace/,
    })
    .first();
  await expect(workspaceSwitcher).toBeVisible();
  await workspaceSwitcher.click();
  await expect(
    page.getByRole('menuitem', { name: 'Workspace Settings' }),
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

test('support-admin launch keeps its Workspace scope without Account bootstrap', async ({
  page,
}) => {
  const workspaceUuid = 'workspace-support-admin';
  const currentWorkspaceRequests: {
    workspace?: string;
    authorization?: string;
  }[] = [];
  let accountBootstrapRequests = 0;
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === '/api/v1/workspaces/current') {
      currentWorkspaceRequests.push({
        workspace: request.headers()['x-workspace-id'],
        authorization: request.headers().authorization,
      });
    }
  });
  await installLangBotApiMocks(page, {
    authenticated: true,
    storage: {
      langbot_active_workspace_uuid: 'workspace-from-another-account',
    },
    workspaces: [makeWorkspaceEntry(workspaceUuid, 'Support Workspace')],
  });
  await page.route('**/api/v1/user/space/callback', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          token: 'support-admin-token',
          principal_type: 'support_admin',
          workspace_uuid: workspaceUuid,
        },
      },
    }),
  );
  await page.route('**/api/v1/workspaces/bootstrap', (route) => {
    accountBootstrapRequests += 1;
    return route.fulfill({ status: 403, json: { code: 403 } });
  });
  await page.route('**/api/v1/system/info', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          edition: 'cloud',
          cloud_service_url: 'https://space.langbot.app',
          wizard_status: 'none',
          limitation: { max_bots: -1, max_pipelines: -1, max_extensions: -1 },
        },
      },
    }),
  );

  await page.goto(
    `/auth/space/callback#workspace_uuid=${workspaceUuid}&launch_assertion=support-launch`,
  );

  await expect(page).toHaveURL(/\/home(?:\/monitoring)?$/);
  await expect(page.getByRole('button', { name: 'Dashboard' })).toBeVisible();
  expect(currentWorkspaceRequests.length).toBeGreaterThan(0);
  for (const request of currentWorkspaceRequests) {
    expect(request).toEqual({
      workspace: workspaceUuid,
      authorization: 'Bearer support-admin-token',
    });
  }
  expect(accountBootstrapRequests).toBe(0);
  expect(
    await page.evaluate(() => ({
      token: localStorage.getItem('token'),
      principalType: localStorage.getItem('authPrincipalType'),
      workspace: localStorage.getItem('langbot_active_workspace_uuid'),
    })),
  ).toEqual({
    token: 'support-admin-token',
    principalType: 'support_admin',
    workspace: workspaceUuid,
  });
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
