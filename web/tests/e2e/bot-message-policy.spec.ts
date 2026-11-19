import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test.describe.configure({ timeout: 90_000 });

const ruleStage = {
  name: 'group-respond-rules',
  label: { en_US: 'Group Respond Rule' },
  config: [
    {
      id: 'enabled',
      name: 'enabled',
      label: { en_US: 'Enable Group Respond Rules' },
      type: 'boolean',
      required: true,
      default: true,
    },
  ],
};
const replyStage = {
  name: 'misc',
  label: { en_US: 'Misc' },
  config: [
    {
      id: 'at-sender',
      name: 'at-sender',
      label: { en_US: 'At Sender' },
      type: 'boolean',
      required: true,
      default: true,
    },
  ],
};
const neutral = {
  trigger: { 'group-respond-rules': { enabled: false } },
  safety: {},
  output: { misc: { 'at-sender': false } },
};

function plugin(name: string, kind: string) {
  return {
    status: 'mounted',
    priority: 0,
    plugin_config: {},
    debug: false,
    enabled: true,
    install_source: 'local',
    install_info: {},
    manifest: {
      manifest: {
        apiVersion: 'v1',
        kind: 'Plugin',
        metadata: { name, author: 'qa', label: { en_US: `QA ${name}` } },
        spec: {},
      },
    },
    components: [
      {
        component_config: {},
        manifest: {
          manifest: {
            apiVersion: 'v1',
            kind,
            metadata: { name, label: { en_US: name } },
            spec: {},
          },
        },
      },
    ],
  };
}

async function setup(page: Page) {
  await installLangBotApiMocks(page, { authenticated: true });
  const bot = {
    uuid: 'policy-bot',
    name: 'Policy bot',
    description: '',
    adapter: 'playwright-adapter',
    adapter_config: {},
    enable: true,
    plugin_processors: [],
    command_settings: { enabled: true, prefixes: ['/'], processors: [] },
    message_policy: {
      ...neutral,
      plugins: { enable_all: true, plugins: [] },
    },
    event_bindings: [
      {
        id: 'r-chat',
        event_pattern: 'message.received',
        target_type: 'pipeline',
        target_uuid: 'chat-1',
        priority: 0,
        enabled: true,
        description: 'Group chat',
        filters: [],
        policy: {
          trigger: { 'group-respond-rules': { enabled: true } },
          output: { misc: { 'at-sender': true } },
        },
      },
      {
        id: 'r-agent',
        event_pattern: 'message.received',
        target_type: 'agent',
        target_uuid: 'agent-1',
        priority: 0,
        enabled: true,
        description: 'Private agent',
        filters: [],
      },
    ],
  };
  const saved: Record<string, unknown>[] = [];
  await page.route('**/api/v1/agents**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path !== '/api/v1/agents') return route.fallback();
    return route.fulfill({
      json: {
        code: 0,
        data: {
          agents: [
            { uuid: 'chat-1', name: 'Support chat', kind: 'pipeline' },
            {
              uuid: 'agent-1',
              name: 'Helper',
              kind: 'agent',
              supported_event_patterns: ['message.received'],
            },
          ],
        },
      },
    });
  });
  await page.route('**/api/v1/plugins', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          plugins: [
            plugin('listener', 'EventListener'),
            plugin('draw', 'Command'),
          ],
        },
      },
    }),
  );
  await page.route('**/api/v1/platform/bots/**', (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/_/message-policy/metadata'))
      return route.fulfill({
        json: {
          code: 0,
          data: {
            configs: [
              {
                name: 'trigger',
                label: { en_US: 'Entry' },
                stages: [ruleStage],
              },
              { name: 'safety', label: { en_US: 'Safety' }, stages: [] },
              {
                name: 'output',
                label: { en_US: 'Reply' },
                stages: [replyStage],
              },
            ],
            default: neutral,
            neutral,
          },
        },
      });
    if (url.pathname.endsWith('/policy-bot/plugin-registrations')) {
      expect(url.searchParams.get('include_disabled')).toBe('1');
      return route.fulfill({
        json: {
          code: 0,
          data: {
            plugins: {
              'qa/listener': {
                commands: [],
                events: [
                  'GroupMessageReceived',
                  'PromptPreProcessing',
                  'NormalMessageResponded',
                ],
                event_processors: {
                  GroupMessageReceived: ['messaging', 'agent', 'command'],
                  PromptPreProcessing: ['messaging'],
                  NormalMessageResponded: ['messaging', 'agent'],
                },
              },
              'qa/draw': {
                commands: ['draw'],
                events: [],
                event_processors: {},
              },
            },
          },
        },
      });
    }
    if (url.pathname.endsWith('/policy-bot')) {
      if (route.request().method() === 'PUT') {
        saved.push(route.request().postDataJSON());
        return route.fulfill({ json: { code: 0, data: {} } });
      }
      return route.fulfill({ json: { code: 0, data: { bot } } });
    }
    return route.fallback();
  });
  return saved;
}

test('plugins tab shows lifecycle, hook applicability and bot-level enablement', async ({
  page,
}) => {
  const saved = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1400 });
  await page.goto('/home/bots?id=policy-bot');
  await page.getByRole('tab', { name: 'Plugins' }).click();

  const lifecycle = page.getByTestId('plugin-lifecycle');
  await expect(lifecycle).toBeVisible({ timeout: 15_000 });
  for (const step of [
    'Received',
    'Command',
    'Admission',
    'Before reply',
    'Process',
    'After reply',
    'Send',
  ])
    await expect(lifecycle).toContainText(step);
  await expect(
    lifecycle.locator('[data-step="received"] [data-lifecycle-plugin]'),
  ).toHaveCount(1);
  await expect(
    lifecycle.locator('[data-step="command"] [data-lifecycle-plugin]'),
  ).toHaveCount(1);

  const listener = page.locator('[data-plugin="qa/listener"]');
  const draw = page.locator('[data-plugin="qa/draw"]');
  await expect(draw).toContainText('/draw');
  await expect(
    listener.locator('[data-hook="PromptPreProcessing"]'),
  ).toHaveAttribute('data-active', 'true');
  await page.screenshot({
    path: 'test-results/bot-plugins-tab.png',
    fullPage: true,
  });

  // On the Agent route the prompt hook does not apply.
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  await page.getByRole('option', { name: /Private agent/ }).click();
  await expect(
    listener.locator('[data-hook="PromptPreProcessing"]'),
  ).toHaveAttribute('data-active', 'false');
  await expect(listener).toContainText(
    'Routed to an Agent; prompt hooks do not apply',
  );
  await page.keyboard.press('Escape');
  await page.screenshot({
    path: 'test-results/bot-plugins-agent-route.png',
    fullPage: true,
  });

  // Back to the bot default: enable only the command plugin.
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  await page.getByRole('option', { name: 'Bot default' }).click();
  await page.getByLabel('Enable All Plugins').click();
  await draw.getByRole('switch').click();
  await expect(listener.getByRole('switch')).not.toBeChecked();
  await expect(
    lifecycle.locator('[data-step="received"] [data-lifecycle-plugin]'),
  ).toHaveCount(0);

  // Message policy: promote the Chat route's custom policy to the bot default.
  await page.getByRole('tab', { name: 'Message policy' }).click();
  const policy = page.getByTestId('bot-message-policy');
  await expect(policy).toContainText('Policy: Custom');
  await policy.getByRole('button', { name: 'Group chat' }).click();
  await page.screenshot({
    path: 'test-results/bot-policy-route.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Make bot default' }).click();
  await expect(page.getByText('1 route(s) now use the default')).toBeVisible();
  await expect(
    page.getByRole('radio', { name: 'Use default' }),
  ).toHaveAttribute('aria-checked', 'true');

  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as {
    message_policy: Record<string, unknown>;
    event_bindings: { id: string; policy: unknown }[];
  };
  expect(body.message_policy.plugins).toEqual({
    enable_all: false,
    plugins: [{ author: 'qa', name: 'draw' }],
  });
  expect(body.message_policy.trigger).toMatchObject({
    'group-respond-rules': { enabled: true },
  });
  expect(body.event_bindings.map((b) => [b.id, b.policy])).toEqual([
    ['r-chat', null],
    ['r-agent', null],
  ]);
});

test('custom route plugin selection is saved as a route override', async ({
  page,
}) => {
  const saved = await setup(page);
  await page.goto('/home/bots?id=policy-bot');
  await page.getByRole('tab', { name: 'Plugins' }).click();
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  await page.getByRole('option', { name: /Private agent/ }).click();
  await expect(page.getByLabel('Enable All Plugins')).toBeDisabled();
  await page.getByRole('radio', { name: 'Custom' }).click();
  await page.getByLabel('Enable All Plugins').click();
  await page.locator('[data-plugin="qa/listener"]').getByRole('switch').click();

  await page.getByRole('tab', { name: 'Message policy' }).click();
  await expect(page.getByText('Plugins: Custom')).toHaveCount(0); // route scope shows editor
  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as {
    event_bindings: { id: string; policy: unknown }[];
  };
  expect(body.event_bindings[1]).toMatchObject({
    id: 'r-agent',
    policy: {
      plugins: {
        enable_all: false,
        plugins: [{ author: 'qa', name: 'listener' }],
      },
    },
  });
  // The Chat route keeps its section override; it has no plugin override.
  expect(body.event_bindings[0].policy).toMatchObject({ plugins: null });
});
