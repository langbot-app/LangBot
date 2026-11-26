import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test.describe.configure({ timeout: 90_000 });

const NOW = Date.parse('2026-11-26T10:00:00Z');

function row(id: string, extra: Record<string, unknown>) {
  return {
    source: 'event',
    id,
    event_id: id,
    status: 'completed',
    status_group: 'completed',
    title: 'message.received',
    input_preview: `message ${id}`,
    target_kind: 'event',
    target_id: null,
    target_name: null,
    bot_id: 'bot-1',
    bot_name: 'Support bot',
    pipeline_id: null,
    pipeline_name: null,
    runner_id: null,
    handled_by: null,
    conversation_id: 'group_1',
    session_id: 'group_1',
    created_at_ms: NOW,
    started_at_ms: null,
    finished_at_ms: null,
    duration_ms: null,
    usage: null,
    cost: null,
    queue_name: null,
    debug: false,
    has_error: false,
    ...extra,
  };
}

const ROWS = [
  row('evt-help', {
    handling: 'command',
    command_kind: 'builtin',
    command_name: 'help',
    command_denied: false,
    handled_by: 'builtin_command:help',
  }),
  row('evt-denied', {
    status: 'denied',
    status_group: 'denied',
    handling: 'command',
    command_kind: 'plugin',
    command_name: 'draw',
    command_denied: true,
  }),
  row('evt-policy', {
    status: 'ignored',
    status_group: 'ignored',
    handling: 'policy',
    policy_layer: 'route',
    policy_item: 'rate-limit',
  }),
  row('evt-hook', {
    handling: 'plugin',
    hook: 'CommandSent',
    handled_by: 'plugin:qa/guard',
  }),
  {
    ...row('msg-chat', {
      handling: 'ai',
      source: 'pipeline',
      target_kind: 'pipeline',
      target_id: 'chat-1',
      target_name: 'Support chat',
      pipeline_id: 'chat-1',
      pipeline_name: 'Support chat',
      input_preview: 'a long question',
    }),
  },
];

const INGRESS: Record<string, Record<string, unknown>> = {
  'evt-policy': {
    status: 'ignored',
    policy_item: 'rate-limit',
    policy_layer: 'route',
    routes: [
      {
        target_type: 'agent',
        status: 'discarded',
        failure_code: 'message_policy',
        policy_layer: 'route',
        policy_item: 'rate-limit',
      },
    ],
  },
  'msg-chat': {
    status: 'completed',
    routes: [
      { target_type: 'pipeline', target_uuid: 'chat-1', status: 'delivered' },
    ],
    policy_events: [
      {
        type: 'output',
        actions: [
          { kind: 'long_text', strategy: 'forward' },
          { kind: 'delay', ms: 1200 },
          { kind: 'at' },
          { kind: 'quote' },
        ],
      },
    ],
  },
};

async function mockExecutions(page: Page) {
  const handlings: string[] = [];
  await page.route('**/api/v1/monitoring/executions?*', (route) => {
    const handling =
      new URL(route.request().url()).searchParams.get('handling') ?? 'all';
    handlings.push(handling);
    const items =
      handling === 'all'
        ? ROWS
        : ROWS.filter((item) => item.handling === handling);
    return route.fulfill({
      json: {
        code: 0,
        data: {
          items,
          total: items.length,
          limit: 50,
          offset: 0,
          has_more: false,
        },
      },
    });
  });
  await page.route('**/api/v1/monitoring/executions/*/*?*', (route) => {
    const id = new URL(route.request().url()).pathname.split('/').pop()!;
    const record = ROWS.find((item) => item.id === id)!;
    const page_ = (items: unknown[]) => ({
      items,
      has_more: false,
      next_offset: items.length,
    });
    return route.fulfill({
      json: {
        code: 0,
        data: {
          source: record.source,
          row: record,
          pages: {
            inputs: page_([
              {
                id,
                event_type: 'message.received',
                source: 'platform',
                timestamp_ms: NOW,
                content: { text: record.input_preview },
                metadata: INGRESS[id] ?? {},
              },
            ]),
            outputs: page_([]),
            deliveries: page_([]),
            errors: page_([]),
          },
        },
      },
    });
  });
  return handlings;
}

test('execution list badges, handling filter and message policy timeline', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const handlings = await mockExecutions(page);
  await page.goto('/home/monitoring');

  await expect(page.getByText('System command /help')).toBeVisible();
  await expect(page.getByText('Command denied')).toBeVisible();
  await expect(
    page.getByText('Blocked by policy · Rate limit').first(),
  ).toBeVisible();
  await expect(
    page.getByText('Plugin intercepted · qa/guard (CommandSent)'),
  ).toBeVisible();

  await page.locator('#monitoring-filter-handling').click();
  await page.getByRole('option', { name: 'Blocked by policy' }).click();
  await expect.poll(() => handlings.at(-1)).toBe('policy');
  await expect(page.getByText('System command /help')).toHaveCount(0);

  await page
    .getByRole('button')
    .filter({ hasText: 'message evt-policy' })
    .click();
  const timeline = page.getByTestId('policy-timeline');
  await expect(timeline.locator('[data-step="admission"]')).toHaveAttribute(
    'data-state',
    'blocked',
  );
  await expect(timeline).toContainText(
    'Blocked by "Rate limit" of the route override policy',
  );
  await expect(timeline.locator('[data-step="processor"]')).toHaveAttribute(
    'data-state',
    'skipped',
  );
  await page.keyboard.press('Escape');

  await page.locator('#monitoring-filter-handling').click();
  await page.getByRole('option', { name: 'AI', exact: true }).click();
  await page.getByRole('button').filter({ hasText: 'a long question' }).click();
  await expect(timeline).toContainText('Handled by Support chat');
  for (const chip of [
    'Long text as forwarded message',
    'Delayed 1200 ms',
    '@ sender',
    'Quoted the message',
  ])
    await expect(timeline).toContainText(chip);
});

test('upgrade check banner opens the assistant, runs actions and disappears after acknowledging all', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let confirmed = false;
  const actions: unknown[] = [];
  const items = () => [
    {
      id: 'command_prefix_changed:bot-1',
      code: 'command_prefix_changed',
      params: { bot_uuid: 'bot-1', original_prefixes: ['!', '！'] },
      actions: ['restore_prefixes'],
      confirmed,
    },
    {
      id: 'equivalent_route_policies:bot-1',
      code: 'equivalent_route_policies',
      params: {
        bot_uuid: 'bot-1',
        route_ids: ['r1', 'r2'],
        message_policy: {},
        changes_unrouted_commands: true,
      },
      actions: ['promote_route_policy'],
      confirmed,
    },
    {
      id: 'command_admin_missing:bot-1',
      code: 'command_admin_missing',
      params: { bot_uuid: 'bot-1' },
      actions: [],
      confirmed,
    },
  ];
  await page.route('**/api/v1/platform/bots/_/upgrade-checks**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/action')) {
      actions.push(route.request().postDataJSON());
      return route.fulfill({ json: { code: 0, data: {} } });
    }
    if (path.endsWith('/confirm-all')) {
      confirmed = true;
      return route.fulfill({ json: { code: 0, data: { confirmed: [] } } });
    }
    return route.fulfill({
      json: { code: 0, data: { items: items(), reports: [] } },
    });
  });
  await page.goto('/home/bots');
  const banner = page.getByTestId('upgrade-checks-banner');
  await expect(banner).toContainText('3 upgrade changes need your review');
  await banner.getByRole('button', { name: 'Review' }).click();

  const sheet = page.getByRole('dialog', { name: 'Upgrade check' });
  await expect(sheet.getByText('Command prefix changed')).toBeVisible();
  await expect(
    sheet.getByText(
      'Commands that match no route will also use these settings.',
    ),
  ).toBeVisible();
  await expect(
    sheet.getByRole('link', { name: 'Set admins in Sessions' }),
  ).toHaveAttribute('href', '/home/bots?id=bot-1&tab=sessions');

  await sheet.getByRole('button', { name: 'Also accept ! and ！' }).click();
  await expect.poll(() => actions.length).toBe(1);
  expect(actions[0]).toEqual({
    id: 'command_prefix_changed:bot-1',
    action: 'restore_prefixes',
  });

  // Data-changing actions ask first.
  await sheet.getByRole('button', { name: 'Make it the bot default' }).click();
  const confirmDialog = page.getByRole('alertdialog');
  await expect(confirmDialog).toContainText('overrides on 2 routes');
  await confirmDialog.getByRole('button', { name: 'Confirm' }).click();
  await expect.poll(() => actions.length).toBe(2);

  await sheet.getByRole('button', { name: 'Acknowledge all' }).click();
  await expect(sheet).toBeHidden();
  await expect(banner).toBeHidden();
});
