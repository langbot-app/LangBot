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
  const runs: unknown[] = [];
  let limits: Record<string, number> = {};
  const common = { timeout_sec: true, idle_ttl_sec: true, max_sessions: true };
  const local = {
    ...common,
    cpus: true,
    memory_mb: true,
    pids_limit: true,
    workspace_quota_mb: true,
  };
  await page.route('**/api/v1/workspaces/current/sandbox**', async (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      const draft = request.postDataJSON().e2b;
      (request.url().endsWith('/test') ? runs : checks).push(draft);
      e2bAvailable = draft.api_key !== 'invalid';
      reason = e2bAvailable ? null : 'authentication_failed';
    }
    if (request.method() === 'PUT') {
      expect(request.headers()['x-workspace-id']).toBe('sandbox-workspace');
      const body = request.postDataJSON();
      writes.push(body);
      backend = body.backend;
      limits = body.limits || limits;
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
          limits,
          limit_caps: {
            timeout_sec: 120,
            idle_ttl_sec: 86400,
            max_sessions: 64,
            cpus: 8,
            memory_mb: 8192,
            pids_limit: 1024,
            workspace_quota_mb: 10240,
          },
          e2b: {
            ...config,
            api_key_configured: mode !== 'unavailable' || writes.length > 0,
            source: 'workspace',
          },
          backends: [
            {
              name: 'docker',
              limit_capabilities: local,
              available: mode !== 'unavailable',
              reason: mode === 'unavailable' ? 'docker_unreachable' : null,
            },
            {
              name: 'e2b',
              limit_capabilities: common,
              template_validation: 'unsupported',
              available: e2bAvailable,
              reason,
              template_validated:
                request.url().endsWith('/test') && e2bAvailable,
            },
            {
              name: 'nsjail',
              limit_capabilities: local,
              available: mode === 'unavailable',
              reason: mode === 'unavailable' ? null : 'policy_restricted',
            },
          ],
        },
      },
    });
  });
  await page.goto('/home?action=showWorkspaceSettings');
  return { writes, checks, runs, backend: () => backend };
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
  await expect(save).toBeEnabled();
  await page.getByRole('button', { name: 'Check again', exact: true }).click();
  await expect(save).toBeEnabled();
  expect(state.writes).toHaveLength(0);
  await save.click();
  await expect(
    page.getByText('Saved; applies to new tasks', { exact: true }),
  ).toBeVisible();
  expect(state.writes).toHaveLength(1);
  expect(state.backend()).toBe('e2b');
  expect(state.runs).toHaveLength(0);
  await page.getByRole('button', { name: 'Test run', exact: true }).click();
  await expect(
    page.getByText(
      'Template verified: temporary sandbox created, executed and deleted',
      { exact: true },
    ),
  ).toBeVisible();
  expect(state.runs).toHaveLength(1);
  expect(state.writes).toHaveLength(1);
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

test('workspace limits persist, reject out-of-range values and disable unsupported E2B controls', async ({
  page,
}) => {
  const state = await setup(page);
  const cpu = page.getByLabel('CPU cores', { exact: true });
  await expect(cpu).toBeEnabled();
  await cpu.fill('99');
  const save = page.getByRole('button', {
    name: 'Confirm and save',
    exact: true,
  });
  await expect(save).toBeDisabled();
  await cpu.fill('0.5');
  await page.getByLabel('Command timeout (seconds)', { exact: true }).fill('2');
  await page.getByLabel('Idle cleanup (seconds)', { exact: true }).fill('60');
  await page.getByLabel('Maximum sandboxes', { exact: true }).fill('2');
  await save.click();
  await expect(save).toBeDisabled();
  expect(state.writes[0]).toMatchObject({
    limits: { cpus: 0.5, timeout_sec: 2, idle_ttl_sec: 60, max_sessions: 2 },
  });
  await page.reload();
  await page.goto('/home?action=showWorkspaceSettings');
  await expect(cpu).toHaveValue('0.5');
  const select = page.getByRole('combobox', {
    name: 'Execution environment',
    exact: true,
  });
  await select.click();
  await page.getByRole('option', { name: 'E2B', exact: true }).click();
  await expect(cpu).toBeDisabled();
  await expect(
    page.getByLabel('Workspace disk quota (MiB)', { exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByLabel('Command timeout (seconds)', { exact: true }),
  ).toBeEnabled();
  await save.click();
  await expect(save).toBeDisabled();
  expect(state.writes[1]).toMatchObject({
    limits: { timeout_sec: 2, idle_ttl_sec: 60, max_sessions: 2 },
  });
  expect(
    (state.writes[1] as { limits: Record<string, number> }).limits.cpus,
  ).toBeUndefined();
  expect(state.runs).toHaveLength(0);
});
