import { expect, test, type Page } from '@playwright/test';
import {
  installLangBotApiMocks,
  makeWorkspaceEntry,
} from './fixtures/langbot-api';

async function setup(
  page: Page,
  mode: 'owner' | 'viewer' | 'unavailable' = 'owner',
) {
  const workspace = makeWorkspaceEntry(
    'sandbox-workspace',
    'Sandbox Workspace',
    'local',
  );
  workspace.permissions =
    mode === 'viewer'
      ? ['workspace.view']
      : ['workspace.view', 'workspace.update'];
  workspace.membership.role = mode === 'viewer' ? 'viewer' : 'owner';
  await installLangBotApiMocks(page, {
    authenticated: true,
    workspaces: [workspace],
  });
  let backend =
    mode === 'viewer' ? 'e2b' : mode === 'unavailable' ? 'nsjail' : 'docker';
  let config = {
    api_url: 'http://e2b-api.test:3000',
    sandbox_url: 'http://e2b-proxy.test:3001',
    template: 'base',
  };
  let e2bAvailable = mode !== 'unavailable';
  let reason: string | null = e2bAvailable ? null : 'missing_credentials';
  const writes: unknown[] = [];
  const checks: unknown[] = [];
  await page.route('**/api/v1/workspaces/current/sandbox**', async (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      const draft = request.postDataJSON().e2b;
      checks.push(draft);
      e2bAvailable = draft.api_key !== 'invalid';
      reason = e2bAvailable ? null : 'authentication_failed';
    }
    if (request.method() === 'PUT') {
      expect(request.headers()['x-workspace-id']).toBe('sandbox-workspace');
      const body = request.postDataJSON();
      writes.push(body);
      backend = body.backend;
      if (body.e2b)
        config = {
          api_url: body.e2b.api_url,
          sandbox_url: body.e2b.sandbox_url,
          template: body.e2b.template,
        };
    }
    await route.fulfill({
      json: {
        code: 0,
        msg: 'ok',
        data: {
          backend,
          effective_backend: backend,
          enabled: true,
          e2b_configurable: true,
          e2b: {
            ...config,
            api_key_configured: mode !== 'unavailable' || writes.length > 0,
            source: 'workspace',
          },
          backends: [
            {
              name: 'docker',
              available: mode !== 'unavailable',
              reason: mode === 'unavailable' ? 'docker_unreachable' : null,
            },
            {
              name: 'e2b',
              available: e2bAvailable,
              reason,
              template_validated: request.method() === 'POST' && e2bAvailable,
            },
            {
              name: 'nsjail',
              available: mode === 'unavailable',
              reason: mode === 'unavailable' ? null : 'policy_restricted',
            },
          ],
        },
      },
    });
  });
  await page.goto('/home?action=showWorkspaceSettings');
  return { writes, checks, backend: () => backend };
}

test('selection and E2B drafts require explicit confirmation; failed checks do not save', async ({
  page,
}) => {
  const state = await setup(page);
  const select = page.getByRole('combobox', {
    name: 'Execution environment',
    exact: true,
  });
  await expect(select).toHaveText('Docker');
  await select.click();
  await page.getByRole('option', { name: 'E2B', exact: true }).click();
  await expect(page.getByLabel('API URL', { exact: true })).toHaveValue(
    'http://e2b-api.test:3000',
  );
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
  expect(state.writes).toHaveLength(0);
  expect(state.backend()).toBe('docker');
  await page.getByLabel('Template', { exact: true }).fill('python');
  const save = page.getByRole('button', {
    name: 'Confirm and save',
    exact: true,
  });
  await expect(save).toBeDisabled();
  await page.getByRole('button', { name: 'Check again', exact: true }).click();
  await expect(save).toBeEnabled();
  expect(state.writes).toHaveLength(0);
  await save.click();
  await expect(
    page.getByText('Saved; applies to new tasks', { exact: true }),
  ).toBeVisible();
  expect(state.writes).toHaveLength(1);
  expect(state.backend()).toBe('e2b');
  await page.reload();
  await page.goto('/home?action=showWorkspaceSettings');
  await expect(select).toHaveText('E2B');
  await expect(page.getByLabel('Template', { exact: true })).toHaveValue(
    'python',
  );
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
  await page.getByLabel('API Key', { exact: true }).fill('invalid');
  await page.getByRole('button', { name: 'Check again', exact: true }).click();
  await expect(
    page.getByText('E2B: E2B authentication failed; check API key', {
      exact: true,
    }),
  ).toBeVisible();
  await expect(save).toBeDisabled();
  expect(state.writes).toHaveLength(1);
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
  expect(state.writes).toHaveLength(1);
});

test('unavailable choices are disabled with reasons but E2B can be configured before selection', async ({
  page,
}) => {
  const state = await setup(page, 'unavailable');
  const select = page.getByRole('combobox', {
    name: 'Execution environment',
    exact: true,
  });
  await expect(select).toHaveText('nsjail');
  await select.click();
  await expect(
    page.getByRole('option', {
      name: /Docker daemon is stopped or access is denied/,
    }),
  ).toHaveAttribute('aria-disabled', 'true');
  await expect(
    page.getByRole('option', { name: /E2B API key is missing/ }),
  ).toHaveAttribute('aria-disabled', 'true');
  await page.keyboard.press('Escape');
  await page
    .getByRole('button', { name: 'Configure E2B', exact: true })
    .click();
  await page.getByLabel('API Key', { exact: true }).fill('valid-test-key');
  await page.getByRole('button', { name: 'Check again', exact: true }).click();
  const save = page.getByRole('button', {
    name: 'Confirm and save',
    exact: true,
  });
  await expect(save).toBeEnabled();
  expect(state.backend()).toBe('nsjail');
  expect(state.writes).toHaveLength(0);
  await save.click();
  await expect(save).toBeDisabled();
  expect(state.backend()).toBe('e2b');
});

test('viewer can read configuration without receiving an API key or editing settings', async ({
  page,
}) => {
  const state = await setup(page, 'viewer');
  await expect(
    page.getByRole('combobox', { name: 'Execution environment', exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel('API URL', { exact: true })).toHaveValue(
    'http://e2b-api.test:3000',
  );
  await expect(page.getByLabel('API Key', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('API Key', { exact: true })).toBeDisabled();
  await expect(
    page.getByRole('button', { name: 'Confirm and save', exact: true }),
  ).toBeDisabled();
  expect(state.writes).toHaveLength(0);
});
