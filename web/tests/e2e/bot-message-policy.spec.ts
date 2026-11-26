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
  await expect(draw).toHaveCount(0);
  await page.getByTestId('add-bot-plugin').click();
  const addDialog = page.getByTestId('add-bot-plugin-dialog');
  await addDialog.locator('[data-addable-plugin="qa/draw"]').click();
  await addDialog.getByRole('button', { name: 'Add 1 plugin(s)' }).click();
  await expect(draw).toBeVisible();
  await expect(listener).toHaveCount(0);
  await expect(
    lifecycle.locator('[data-step="received"] [data-lifecycle-plugin]'),
  ).toHaveCount(0);

  // Message policy: promote the Chat route's custom policy to the bot default.
  await page.getByRole('tab', { name: 'Message policy' }).click();
  const policy = page.getByTestId('bot-message-policy');
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  const chatRoute = page.getByRole('option', { name: /Group chat/ });
  await expect(chatRoute).toContainText('Custom');
  await chatRoute.click();
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
  await page.getByTestId('add-bot-plugin').click();
  const addDialog = page.getByTestId('add-bot-plugin-dialog');
  await addDialog.locator('[data-addable-plugin="qa/listener"]').click();
  await addDialog.getByRole('button', { name: 'Add 1 plugin(s)' }).click();
  await expect(page.locator('[data-plugin="qa/listener"]')).toBeVisible();

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

test('plugin commands are configured from the plugin list', async ({
  page,
}) => {
  const saved = await setup(page);
  const created: Record<string, unknown>[] = [];
  // Registered after setup, so these take precedence.
  await page.route('**/api/v1/agents**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/agents/_/metadata')
      return route.fulfill({
        json: {
          code: 0,
          data: {
            runners: [],
            event_processors: [],
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
                        id: 'style',
                        name: 'style',
                        label: { en_US: 'Style' },
                        type: 'string',
                        required: false,
                        default: 'sketch',
                      },
                    ],
                  },
                ],
              },
            ],
          },
        },
      });
    if (path === '/api/v1/agents' && route.request().method() === 'POST') {
      created.push(route.request().postDataJSON());
      return route.fulfill({
        json: { code: 0, data: { uuid: 'cmd-1', kind: 'command_processor' } },
      });
    }
    return route.fallback();
  });
  // The listener also registers /draw; it is listed first, so it owns it.
  await page.route('**/policy-bot/plugin-registrations**', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          plugins: {
            'qa/listener': {
              commands: ['draw'],
              events: ['GroupMessageReceived'],
              event_processors: {
                GroupMessageReceived: ['messaging', 'agent', 'command'],
              },
            },
            'qa/draw': { commands: ['draw'], events: [], event_processors: {} },
          },
        },
      },
    }),
  );

  await page.setViewportSize({ width: 1440, height: 1400 });
  await page.goto('/home/bots?id=policy-bot');
  await page.getByRole('tab', { name: 'Plugins' }).click();

  const settings = page.getByTestId('bot-command-settings');
  await expect(settings).toBeVisible({ timeout: 15_000 });
  await expect(settings).toContainText('Plugin commands');
  const commandLayer = page.getByRole('region', {
    name: 'Commands',
    exact: true,
  });
  const commandSwitch = commandLayer.locator('#bot-commands-enabled');
  await expect(page.getByTestId('command-prefix-button')).toContainText('/');
  // The separate command binding section is gone.
  await expect(page.getByText('Add Plugin', { exact: true })).toHaveCount(0);

  const draw = page.locator('[data-plugin="qa/draw"]');
  const listener = page.locator('[data-plugin="qa/listener"]');
  await expect(draw.locator('[data-command="draw"]')).toHaveAttribute(
    'data-overridden',
    'true',
  );
  await expect(listener.locator('[data-command="draw"]')).toHaveAttribute(
    'data-overridden',
    'false',
  );
  await expect(listener.getByTestId('command-config-button')).toHaveCount(0);

  await draw.getByTestId('command-config-button').click();
  const dialog = page.getByTestId('command-config-dialog');
  await expect(dialog).toContainText('/draw');
  await dialog.getByRole('textbox').fill('oil');
  await page.screenshot({
    path: 'test-results/bot-command-config.png',
    fullPage: true,
  });
  await dialog.getByRole('button', { name: 'Save' }).click();
  await expect(dialog).toHaveCount(0);
  await expect.poll(() => created.length).toBe(1);
  expect(created[0]).toMatchObject({
    kind: 'command_processor',
    component_ref: 'plugin:qa/draw',
    config: { command_config: { draw: { style: 'oil' } } },
  });
  await expect(draw.getByTestId('command-config-custom')).toBeVisible();
  // Binding the new settings is an unsaved bot change.
  await expect(page.getByRole('button', { name: 'Save' })).toBeEnabled();
  await page.screenshot({
    path: 'test-results/bot-plugins-commands.png',
    fullPage: true,
  });

  // Command settings are bot-wide: read-only while a route is selected.
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  await page.getByRole('option', { name: /Private agent/ }).click();
  await expect(commandSwitch).toBeDisabled();
  await expect(commandLayer).toContainText('apply to the whole bot');
  await expect(draw.getByTestId('command-config-button')).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  await page.getByRole('option', { name: 'Bot default' }).click();

  await commandSwitch.click();
  await expect(draw.getByTestId('command-config-button')).toHaveCount(0);
  // Turning commands off crosses out every command badge.
  for (const plugin of [draw, listener])
    await expect(plugin.locator('[data-command="draw"]')).toHaveClass(
      /line-through/,
    );
  await page.screenshot({
    path: 'test-results/bot-commands-off.png',
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as {
    command_settings: {
      enabled: boolean;
      prefixes: string[];
      processors: { processor_uuid: string; enabled: boolean }[];
    };
  };
  expect(body.command_settings).toMatchObject({
    enabled: false,
    prefixes: ['/'],
    processors: [{ processor_uuid: 'cmd-1', enabled: true }],
  });
});

test('route notes are optional and routes are told apart by their conditions', async ({
  page,
}) => {
  const saved = await setup(page);
  await page.setViewportSize({ width: 1440, height: 1400 });
  await page.goto('/home/bots?id=policy-bot');

  // Saved routes collapse to a summary: the note as title, then when and where.
  const firstRoute = page.locator('[data-testid^="event-route-"]').first();
  const summary = firstRoute.getByTestId('route-summary');
  await expect(summary).toContainText('Group chat', { timeout: 15_000 });
  await expect(summary).toContainText('Message received → Support chat');
  await expect(firstRoute.getByTestId('route-note-input')).toHaveCount(0);
  await page.screenshot({
    path: 'test-results/bot-routes-collapsed.png',
    fullPage: true,
  });
  await summary.click();
  const note = firstRoute.getByTestId('route-note-input');
  await expect(note).toHaveValue('Group chat');
  await note.fill('Support group');
  await page.screenshot({
    path: 'test-results/bot-route-note.png',
    fullPage: true,
  });

  // The scope picker shows the note plus where the route goes and when.
  await page.getByRole('tab', { name: 'Plugins' }).click();
  await page.getByRole('combobox', { name: 'Applies to' }).click();
  const option = page.getByRole('option', { name: /Support group/ });
  await expect(option).toContainText('Support chat · All messages');
  await page.waitForTimeout(300);
  await page.screenshot({
    path: 'test-results/bot-scope-picker.png',
    fullPage: true,
  });
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as { event_bindings: { description: string }[] };
  expect(body.event_bindings[0].description).toBe('Support group');
});

test('message policy settings read as summaries and edit in place', async ({
  page,
}) => {
  const saved = await setup(page);
  await page.goto('/home/bots?id=policy-bot');
  await page.getByRole('tab', { name: 'Message policy' }).click();
  const policy = page.getByTestId('bot-message-policy');
  const groupRow = policy.locator(
    '[data-policy-setting="group-respond-rules"]',
  );
  await expect(groupRow.locator('[data-policy-summary]')).toHaveText(
    'Reply to every group message',
  );
  await groupRow.getByRole('button').first().click();
  await groupRow
    .getByRole('radio', { name: 'Only when conditions match' })
    .click();
  await expect(groupRow.locator('[data-policy-summary]')).toContainText(
    'No condition set',
  );
  await groupRow.getByText('When the bot is @-mentioned').click();
  const prefix = groupRow.getByPlaceholder(/Type a prefix/);
  await prefix.fill('ai');
  await prefix.press('Enter');
  await expect(groupRow.locator('[data-policy-summary]')).toHaveText(
    'Reply when @-mentioned, or starting with “ai”',
  );
  await page.screenshot({
    path: 'test-results/bot-policy-settings.png',
    fullPage: true,
  });

  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as { message_policy: Record<string, unknown> };
  expect(body.message_policy.trigger).toMatchObject({
    'group-respond-rules': { enabled: true, at: true, prefix: ['ai'] },
  });
});

test('system commands are configured from a small entry in the command bar', async ({
  page,
}) => {
  const saved = await setup(page);
  const describe = (text: string) => ({ en_US: text, zh_Hans: text });
  await page.route('**/api/v1/platform/bots/_/builtin-commands', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          commands: [
            ['help', 'session', true, 'everyone', []],
            ['new', 'session', true, 'everyone', ['reset']],
            ['status', 'info', true, 'admins', []],
            ['model', 'admin', false, 'admins', []],
          ].map(([name, group, enabled, permission, aliases]) => ({
            name,
            group,
            default_enabled: enabled,
            default_permission: permission,
            aliases,
            label: describe(`/${name}`),
            description: describe(`${name} description`),
          })),
        },
      },
    }),
  );
  const admins: { id: number; launcher_type: string; launcher_id: string }[] =
    [];
  await page.route('**/api/v1/platform/bots/policy-bot/admins', (route) =>
    route.fulfill({ json: { code: 0, data: { admins } } }),
  );
  await page.goto('/home/bots?id=policy-bot');
  await page.getByRole('tab', { name: 'Plugins & commands' }).click();
  const commandsSection = page.getByTestId('bot-command-settings');
  await expect(commandsSection).toContainText('e.g. /help.');
  const entry = page.getByTestId('system-commands-button');
  await expect(entry).toContainText('3/4', { timeout: 15_000 });
  // Shared by system and plugin commands: on the section, not in a sheet.
  await expect(commandsSection).toContainText('No admins set yet.');
  await expect(
    commandsSection.getByRole('link', { name: /Open session monitor/ }),
  ).toHaveAttribute('href', '/home/bots?id=policy-bot&tab=sessions');
  await commandsSection
    .getByRole('radio', { name: 'Reply with a notice' })
    .click();

  // System commands sheet lists only built-in commands.
  await entry.click();
  const sheet = page.getByTestId('system-commands-sheet');
  await expect(sheet).not.toContainText('/draw');
  await sheet.getByRole('switch', { name: 'Enable /model' }).click();
  await sheet.getByRole('combobox', { name: 'Who may use /new' }).click();
  await page.getByRole('option', { name: 'Admins only' }).click();
  await sheet.getByRole('button', { name: 'Close' }).click();
  await expect(sheet).toHaveCount(0);
  await expect(entry).toContainText('4/4');
  await expect(
    commandsSection.getByTestId('command-admins-warning'),
  ).toBeVisible();

  // Plugin command access has its own sheet on the plugin commands row.
  await commandsSection.getByTestId('plugin-commands-button').click();
  const pluginSheet = page.getByTestId('plugin-commands-sheet');
  await expect(pluginSheet).not.toContainText('/help');
  await pluginSheet
    .getByRole('combobox', { name: 'Who may use /draw' })
    .click();
  await page.getByRole('option', { name: 'Admins only' }).click();
  await pluginSheet.getByRole('button', { name: 'Close' }).click();
  await expect(
    commandsSection.getByTestId('plugin-commands-button'),
  ).toContainText('1 admins-only');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect.poll(() => saved.length).toBe(1);
  const body = saved[0] as { command_settings: Record<string, unknown> };
  expect(body.command_settings).not.toHaveProperty('admins');
  expect(body.command_settings).toMatchObject({
    denied_reply: 'notice',
    builtin: {
      model: { enabled: true, permission: 'admins' },
      new: { enabled: true, permission: 'admins' },
    },
    plugin_permissions: { 'qa/draw/draw': 'admins' },
  });
});
