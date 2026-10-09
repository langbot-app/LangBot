import { expect, test, type Page } from '@playwright/test';
import {
  installLangBotApiMocks,
  pipelineMetadata,
} from './fixtures/langbot-api';

const runnerId = 'plugin:langbot-team/LocalAgent/default';
const hint = 'The selected runner is not authorized.';
const runnerPlugin = { author: 'langbot-team', name: 'LocalAgent' };

async function setup(page: Page, enableAll: boolean) {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.routeWebSocket('**/api/v1/pipelines/**/ws/connect**', (ws) => {
    ws.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === 'authenticate') {
        ws.send(
          JSON.stringify({
            type: 'connected',
            connection_id: 'fixture',
            session_type: 'person',
          }),
        );
      }
    });
  });
  let config = {
    ai: {
      runner: { id: runnerId },
      runner_config: {
        [runnerId]: {
          model: { primary: 'llm-valid', fallbacks: [] },
          instruction: 'Original instruction',
        },
      },
    },
    trigger: {},
    safety: {},
    output: {},
  };
  const extensions = {
    enable_all_plugins: enableAll,
    bound_plugins: [] as (typeof runnerPlugin)[],
    available_plugins: [
      {
        enabled: true,
        manifest: {
          manifest: { metadata: { ...runnerPlugin, version: '1.0.0' } },
        },
        components: [{ manifest: { manifest: { kind: 'Runner' } } }],
      },
    ],
    enable_all_mcp_servers: true,
    bound_mcp_servers: [],
    available_mcp_servers: [],
    enable_all_skills: true,
    bound_skills: [],
    available_skills: [],
  };
  const writes: Record<string, unknown>[] = [];
  const metadata = pipelineMetadata();
  metadata.configs[0].stages[1].config.push({
    name: 'instruction',
    label: { en_US: 'Instruction' },
    type: 'text',
    default: 'Original instruction',
  } as never);
  await page.route('**/api/v1/pipelines/_/metadata', (route) =>
    route.fulfill({ json: { code: 0, data: metadata } }),
  );
  await page.route('**/api/v1/pipelines/authorization', async (route) => {
    if (route.request().method() === 'PUT') {
      if (
        !extensions.enable_all_plugins &&
        extensions.bound_plugins.length === 0
      ) {
        await route.fulfill({
          status: 400,
          json: { code: -1, msg: 'pipeline_runner_not_authorized' },
        });
        return;
      }
      const body = route.request().postDataJSON();
      config = body.config;
      writes.push(body);
    }
    await route.fulfill({
      json: {
        code: 0,
        data: {
          pipeline: {
            uuid: 'authorization',
            name: 'Authorization test',
            description: '',
            emoji: '⚙️',
            config,
          },
        },
      },
    });
  });
  await page.route(
    '**/api/v1/pipelines/authorization/extensions',
    async (route) => {
      if (route.request().method() === 'PUT') {
        const body = route.request().postDataJSON();
        if (!body.enable_all_plugins && body.bound_plugins.length === 0) {
          await route.fulfill({
            status: 400,
            json: { code: -1, msg: 'pipeline_runner_not_authorized' },
          });
          return;
        }
        Object.assign(extensions, body);
      }
      await route.fulfill({ json: { code: 0, data: extensions } });
    },
  );
  await page.goto('/home/pipelines?id=authorization');
  return { writes, extensions };
}

async function selectRunnerPlugin(page: Page) {
  await page.getByRole('button', { name: 'Add Plugin', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByText('LocalAgent', { exact: true }).click();
  await dialog.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(dialog).not.toBeVisible();
}

test('rejected config stays editable and can be saved after authorizing its runner', async ({
  page,
}) => {
  const { writes, extensions } = await setup(page, false);
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  const input = page.locator('textarea[name="instruction"]');
  await input.fill('Changed instruction');
  const save = page.getByRole('button', { name: 'Save', exact: true });
  await save.click();
  await expect(page.getByText(hint, { exact: false })).toBeVisible();
  expect(writes).toHaveLength(0);
  await expect(input).toHaveValue('Changed instruction');
  await expect(save).toBeEnabled();
  await page.screenshot({
    path: test.info().outputPath('runner-authorization-error.png'),
  });

  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await selectRunnerPlugin(page);
  await expect.poll(() => extensions.bound_plugins).toEqual([runnerPlugin]);
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  await expect(input).toHaveValue('Changed instruction');
  await save.click();
  await expect.poll(() => writes.length).toBe(1);
  await page.reload();
  await page.getByRole('tab', { name: 'AI', exact: true }).click();
  await expect(input).toHaveValue('Changed instruction');
  await expect(save).toBeDisabled();
});

test('prepare the runner allowlist before disabling all plugins, and restore rejected removals', async ({
  page,
}) => {
  const { extensions } = await setup(page, true);
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  const enableAll = page.getByRole('switch', {
    name: 'Enable All Plugins',
    exact: true,
  });
  await enableAll.click();
  await expect(page.getByText(hint, { exact: false })).toBeVisible();
  await expect(enableAll).toBeChecked();

  await selectRunnerPlugin(page);
  await expect.poll(() => extensions.bound_plugins).toEqual([runnerPlugin]);
  expect(extensions.enable_all_plugins).toBe(true);
  await enableAll.click();
  await expect.poll(() => extensions.enable_all_plugins).toBe(false);
  await expect(enableAll).not.toBeChecked();

  // Selecting an already-selected plugin removes it. A rejected save must restore it.
  await selectRunnerPlugin(page);
  await expect(page.getByText(hint, { exact: false }).first()).toBeVisible();
  await expect(page.getByText('LocalAgent', { exact: true })).toBeVisible();
  expect(extensions.bound_plugins).toEqual([runnerPlugin]);
  await page.reload();
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await expect(enableAll).not.toBeChecked();
  await expect(page.getByText('LocalAgent', { exact: true })).toBeVisible();
});
