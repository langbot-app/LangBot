import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('loading a bot preserves saved command processor bindings and prefixes', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const processor = {
    uuid: 'saved-command',
    name: 'Saved command',
    kind: 'command_processor',
    component_ref: 'plugin:qa/draw',
  };
  const bot = {
    uuid: 'command-bot',
    name: 'Command bot',
    description: '',
    adapter: 'playwright-adapter',
    adapter_config: {},
    enable: true,
    event_bindings: [],
    plugin_processors: [],
    command_settings: {
      enabled: true,
      prefixes: ['!'],
      processors: [{ processor_uuid: processor.uuid, enabled: true }],
    },
  };
  await page.route('**/api/v1/agents**', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: new URL(route.request().url()).pathname.endsWith('/_/metadata')
          ? {
              command_processors: [
                {
                  id: 'plugin:qa/draw',
                  plugin_id: 'qa/draw',
                  commands: [
                    {
                      name: 'draw',
                      label: { en_US: 'Draw' },
                      config_schema: [],
                    },
                  ],
                },
              ],
            }
          : { agents: [processor] },
      },
    }),
  );
  await page.route('**/api/v1/platform/bots/command-bot', (route) =>
    route.fulfill({ json: { code: 0, data: { bot } } }),
  );
  await page.goto('/home/bots?id=command-bot');
  await expect(page.getByRole('link', { name: /Saved command/ })).toBeVisible();
  await expect(page.getByText('!draw', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Command Prefixes' }).click();
  const prefixInput = page.getByRole('textbox', { name: 'Add Prefix' });
  await prefixInput.fill('#');
  await prefixInput.press('Enter');
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('button', { name: 'Command Prefixes' }),
  ).toContainText('! #');
});

test('create a command instance and edit its command configuration', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const processor = {
    uuid: 'command-qa',
    kind: 'command_processor',
    name: 'qa/draw',
    component_ref: 'plugin:qa/draw',
    supported_event_patterns: ['message.received'],
    config: { command_config: { draw: { style: 'plain' } } },
  };
  const writes: Record<string, unknown>[] = [];
  await page.route('**/api/v1/agents**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    let data: unknown;
    if (path.endsWith('/_/metadata')) {
      data = {
        command_processors: [
          {
            id: 'plugin:qa/draw',
            plugin_id: 'qa/draw',
            commands: [
              {
                name: 'draw',
                label: { en_US: 'Draw' },
                config_schema: [
                  {
                    name: 'style',
                    type: 'string',
                    label: { en_US: 'Style', zh_Hans: '风格' },
                    default: 'plain',
                  },
                ],
              },
              { name: 'help', label: { en_US: 'Help' }, config_schema: [] },
            ],
          },
        ],
      };
    } else if (method === 'POST' || method === 'PUT') {
      const payload = route.request().postDataJSON();
      writes.push(payload);
      Object.assign(processor, payload);
      data = { uuid: processor.uuid, kind: processor.kind };
    } else if (path === '/api/v1/agents') data = { agents: [processor] };
    else if (path.endsWith('/command-qa')) data = { agent: processor };
    else return route.fallback();
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto('/home/agents?id=new');
  await page.locator('[data-processor-kind="command_processor"]').click();
  await page.getByRole('combobox').click();
  await page.getByRole('option', { name: 'qa/draw' }).click();
  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(
    page.getByText('No command settings', { exact: true }),
  ).toBeVisible();
  expect(writes[0]).toMatchObject({
    kind: 'command_processor',
    component_ref: 'plugin:qa/draw',
  });
  expect(writes[0]).not.toHaveProperty('config.runner');
  await page.getByRole('textbox').fill('anime');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[1]).toMatchObject({
    config: { command_config: { draw: { style: 'anime' } } },
  });
  await page.screenshot({
    path: 'test-results/command-processor.png',
    fullPage: true,
  });
});
