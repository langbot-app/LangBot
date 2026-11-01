import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('platform menu shows constraints, rejection reasons and synchronization status', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const processor = {
    uuid: 'command-one',
    name: 'Draw',
    kind: 'command_processor',
    component_ref: 'plugin:qa/draw',
  };
  const bot = {
    uuid: 'menu-bot',
    name: 'Menu bot',
    adapter: 'telegram',
    adapter_config: {},
    enable: true,
    event_bindings: [],
    plugin_processors: [],
    command_settings: {
      enabled: true,
      prefixes: ['!'],
      processors: [{ processor_uuid: processor.uuid, enabled: true }],
      platform_commands: { enabled: true, selected: ['draw'] },
    },
    platform_command_sync: { synced_at: '2026-10-31T00:00:00Z', error: null },
    platform_command_registration: {
      rejected: [{ name: 'Bad', reason: 'invalid_name' }],
    },
  };
  await page.route('**/api/v1/platform/adapters', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          adapters: [
            {
              name: 'telegram',
              label: { en_US: 'Telegram' },
              description: { en_US: 'Telegram' },
              spec: {
                config: [],
                supported_events: ['message.received'],
                command_registration: {
                  max_commands: 100,
                  name_pattern: '[a-z0-9_]{1,32}',
                  description_max_length: 256,
                  multilingual: true,
                  scopes: true,
                },
              },
            },
          ],
        },
      },
    }),
  );
  await page.route('**/api/v1/agents**', (route) => {
    const metadata = new URL(route.request().url()).pathname.endsWith(
      '/_/metadata',
    );
    return route.fulfill({
      json: {
        code: 0,
        data: metadata
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
    });
  });
  await page.route('**/api/v1/platform/bots**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/menu-bot'))
      return route.fulfill({ json: { code: 0, data: { bot } } });
    return route.fallback();
  });
  let syncs = 0;
  await page.route(
    '**/api/v1/bots/menu-bot/platform-commands/sync',
    (route) => {
      syncs++;
      return route.fulfill({
        json: {
          code: 0,
          data: { synced_at: '2026-10-31T01:00:00Z', error: null },
        },
      });
    },
  );
  await page.goto('/home/bots?id=menu-bot');
  await page.getByRole('tab', { name: /^Plugin commands/ }).click();
  const panel = page.getByRole('region', { name: 'Register on platform' });
  await expect(panel).toBeVisible({ timeout: 15_000 });
  await expect(panel).toContainText('manually configured');
  await expect(panel).toContainText('100 commands');
  await expect(panel).toContainText('Telegram menu commands will not match');
  await expect(panel).toContainText('Bad: Invalid command name');
  await expect(panel.getByRole('checkbox', { name: '/draw' })).toBeChecked();
  await panel.getByRole('button', { name: 'Sync now' }).click();
  await expect.poll(() => syncs).toBe(1);
  await expect(panel.getByRole('status')).toContainText('2026-10-31T01:00:00Z');
  await page.screenshot({
    path: 'test-results/platform-commands.png',
    fullPage: true,
  });
  await panel.getByRole('switch').uncheck();
  await expect(panel.getByRole('button', { name: 'Sync now' })).toBeDisabled();
});

test('unsupported adapters do not expose platform registration', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto('/home/bots?id=unsupported');
  await page.getByRole('tab', { name: /^Plugin commands/ }).click();
  await expect(
    page.getByRole('region', { name: 'Register on platform' }),
  ).toHaveCount(0);
});
