import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

function wrapped(data: unknown) {
  return JSON.stringify({
    code: 0,
    message: 'ok',
    data,
    timestamp: Date.now(),
  });
}

async function fulfill(
  route: Parameters<Parameters<import('@playwright/test').Page['route']>[1]>[0],
  data: unknown,
) {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: wrapped(data),
  });
}

test('quota-reached create actions are disabled and explain the current limit', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });

  await page.route('**/api/v1/system/info', (route) =>
    fulfill(route, {
      debug: false,
      version: 'quota-e2e',
      edition: 'community',
      cloud_service_url: 'https://space.langbot.app',
      enable_marketplace: true,
      allow_modify_login_info: true,
      disable_models_service: false,
      limitation: {
        max_bots: 2,
        max_pipelines: 3,
        max_extensions: 3,
        max_knowledge_bases: 2,
      },
      outbound_ips: [],
      wizard_status: 'completed',
      wizard_progress: null,
    }),
  );
  await page.route('**/api/v1/platform/bots**', (route) =>
    fulfill(route, {
      bots: Array.from({ length: 2 }, (_, index) => ({
        uuid: `bot-${index}`,
        name: `Bot ${index + 1}`,
        description: '',
        adapter: 'aiocqhttp',
        enable: true,
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/pipelines**', (route) =>
    fulfill(route, {
      pipelines: Array.from({ length: 3 }, (_, index) => ({
        uuid: `pipeline-${index}`,
        name: `Pipeline ${index + 1}`,
        description: '',
        emoji: '⚙️',
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/knowledge/bases**', (route) =>
    fulfill(route, {
      bases: Array.from({ length: 2 }, (_, index) => ({
        uuid: `kb-${index}`,
        name: `Knowledge ${index + 1}`,
        description: '',
        emoji: '📚',
        updated_at: new Date().toISOString(),
      })),
    }),
  );
  await page.route('**/api/v1/plugins**', (route) =>
    fulfill(route, { plugins: [] }),
  );
  await page.route('**/api/v1/mcp/servers**', (route) =>
    fulfill(route, {
      servers: Array.from({ length: 3 }, (_, index) => ({
        name: `mcp-${index}`,
        mode: 'http',
        enable: true,
        runtime_info: { status: 'connected' },
      })),
    }),
  );
  await page.route('**/api/v1/skills**', (route) =>
    fulfill(route, { skills: [] }),
  );

  await page.goto('/home/bots');

  const botCreate = page.getByRole('button', {
    name: 'Create Bots',
    exact: true,
  });
  const pipelineCreate = page.getByRole('button', {
    name: 'Create Pipelines',
    exact: true,
  });
  const knowledgeCreate = page.getByRole('button', {
    name: 'Create Knowledge',
    exact: true,
  });
  const addExtension = page.getByRole('button', {
    name: 'Add Extension',
    exact: true,
  });

  await expect(botCreate).toBeDisabled();
  await expect(pipelineCreate).toBeDisabled();
  await expect(knowledgeCreate).toBeDisabled();
  await expect(addExtension).toBeEnabled();

  const botQuotaTrigger = botCreate.locator('..');
  await botQuotaTrigger.hover();
  await expect(
    page.getByText(
      'The Bots limit (2) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();
  await botQuotaTrigger.focus();
  await expect(botQuotaTrigger).toBeFocused();
  await expect(
    page.getByText(
      'The Bots limit (2) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();

  await addExtension.click();
  await expect(page).toHaveURL(/\/home\/add-extension$/);
  const manualAdd = page.getByRole('button', { name: 'Manual Add' });
  await expect(manualAdd).toBeDisabled();
  await manualAdd.locator('..').hover();
  await expect(
    page.getByText(
      'The Extensions limit (3) for this workspace has been reached. Delete one existing item before creating another.',
    ),
  ).toBeVisible();
});
