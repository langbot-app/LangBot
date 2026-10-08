import { expect, test } from '@playwright/test';
import {
  installLangBotApiMocks,
  buildExecutionList,
} from './fixtures/langbot-api';

const monitoring = {
  messages: [
    {
      id: 'input-one',
      role: 'user',
      message_content: 'Open this execution',
      timestamp: '2026-07-02T10:00:00Z',
      bot_id: 'bot',
      pipeline_id: 'pipe',
      pipeline_name: 'Processor A',
    },
  ],
};
const row = buildExecutionList(monitoring).items[0];
const pageOf = (
  items: unknown[],
  has_more = false,
  next_offset = items.length,
) => ({ items, has_more, next_offset });

test('renders typed and custom events without duplicate text or empty attachment messages', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    monitoringData: monitoring,
  });
  await page.route('**/api/v1/monitoring/executions/*/*?*', async (route) => {
    await route.fulfill({
      json: {
        code: 0,
        data: {
          source: 'pipeline',
          row,
          pages: {
            inputs: pageOf([
              {
                id: 'message',
                content: {
                  text: '你好~',
                  contents: [{ type: 'text', text: '你好~', image_url: null }],
                  attachments: [],
                },
              },
              {
                id: 'member',
                event_type: 'group.member_banned',
                content: {
                  member: { id: 'member-42', nickname: 'Alice' },
                  group: { id: 'group-9' },
                  duration: 0,
                  permanent: false,
                  custom: { reason: 'Moderation reason' },
                },
              },
              {
                id: 'edited',
                content: {
                  message_chain: [{ type: 'Plain', text: 'Typed chain text' }],
                  editor: { id: 'editor-7' },
                  new_content: [{ type: 'Plain', text: 'Updated text' }],
                },
              },
              {
                id: 'custom',
                content: {
                  type: 'CustomEvent',
                  text: 'Distinct text',
                  content: 'Different content',
                  properties: { nested: ['custom-value'] },
                },
              },
              {
                id: 'same-again',
                content: {
                  text: '你好~',
                  contents: [{ type: 'text', text: '你好~' }],
                },
              },
              {
                id: 'image',
                content: {
                  contents: [
                    {
                      type: 'image_url',
                      image_url: {
                        url: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
                      },
                    },
                  ],
                },
              },
            ]),
            outputs: pageOf([
              {
                id: 'assistant',
                content: {
                  content: 'Agent answer',
                  tool_calls: [
                    {
                      id: 'tool-1',
                      function: {
                        name: 'event_reply',
                        arguments: '{"text":"sent"}',
                      },
                    },
                  ],
                },
                attachments: [],
              },
            ]),
            deliveries: pageOf([]),
          },
        },
      },
    });
  });
  await page.goto('/home/monitoring');
  await page
    .getByRole('button')
    .filter({ hasText: 'Open this execution' })
    .click();
  const sheet = page.getByRole('dialog');
  await expect(sheet.getByText('你好~', { exact: true })).toHaveCount(2);
  await expect(sheet.getByText('[Empty message]', { exact: true })).toHaveCount(
    0,
  );
  for (const text of [
    'Agent answer',
    'member-42',
    'Alice',
    'group-9',
    'Moderation reason',
    '0',
    'false',
    'Typed chain text',
    'editor-7',
    'Updated text',
    'Distinct text',
    'Different content',
    'custom-value',
    'event_reply',
  ]) {
    await expect(sheet.getByText(text, { exact: true })).toBeVisible();
  }
  await expect(
    sheet.getByRole('img', { name: 'Message attachment' }),
  ).toBeVisible();
});

test('pages a long trace without dropping inputs and opens related executions', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    monitoringData: monitoring,
  });
  const requests: string[] = [];
  await page.route('**/api/v1/monitoring/executions/*/*?*', async (route) => {
    const url = new URL(route.request().url());
    requests.push(url.search);
    const sibling = url.pathname.endsWith('/sibling');
    const more = url.searchParams.get('section') === 'events';
    await route.fulfill({
      json: {
        code: 0,
        data: {
          source: 'pipeline',
          row: sibling
            ? { ...row, id: 'sibling', target_name: 'Processor B' }
            : row,
          pages: more
            ? {
                events: pageOf(
                  [
                    {
                      id: 101,
                      sequence: 101,
                      type: 'run.completed',
                      data: { final: 'Last trace event' },
                    },
                  ],
                  false,
                  101,
                ),
              }
            : {
                inputs: pageOf([
                  {
                    id: 'in',
                    content: sibling ? 'Sibling input' : 'Original input',
                  },
                ]),
                outputs: pageOf([
                  { id: 'out', content: 'Generated but not sent' },
                ]),
                deliveries: pageOf([]),
                events: pageOf(
                  [{ id: 1, sequence: 1, type: 'run.started', data: {} }],
                  true,
                  100,
                ),
                related: pageOf(
                  sibling
                    ? []
                    : [{ ...row, id: 'sibling', target_name: 'Processor B' }],
                ),
              },
        },
      },
    });
  });
  await page.goto('/home/monitoring');
  await page
    .getByRole('button')
    .filter({ hasText: 'Open this execution' })
    .click();
  const sheet = page.getByRole('dialog');
  await expect(sheet.getByText('Generated but not sent')).toBeVisible();
  await expect(sheet.getByText('Delivery records (0)')).toBeVisible();
  await sheet.getByText('Execution events (1+)', { exact: true }).click();
  await sheet.getByRole('button', { name: 'Load more' }).click();
  await expect(sheet.getByText('run.completed', { exact: true })).toBeVisible();
  await expect(sheet.getByText('Original input')).toBeVisible();
  expect(
    requests.some(
      (query) =>
        query.includes('section=events') && query.includes('offset=100'),
    ),
  ).toBe(true);
  await sheet.getByText('Related executions (1)', { exact: true }).click();
  await sheet.getByRole('button', { name: /Processor B/ }).click();
  await expect(sheet.getByText('Sibling input')).toBeVisible();
  await expect(sheet.getByText('Original input')).toHaveCount(0);
});

test('shows non-message events without fabricating a reply or a processor', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const event = {
    ...row,
    source: 'event',
    id: 'event-only',
    event_id: 'event-only',
    target_id: null,
    target_kind: 'event',
    target_name: null,
    title: 'group.member.joined',
    input_preview: 'Member joined',
    status_group: 'ignored',
    status: 'ignored',
  };
  await page.route('**/api/v1/monitoring/executions?*', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: { ...buildExecutionList(monitoring), items: [event] },
      },
    }),
  );
  await page.route('**/api/v1/monitoring/executions/event/*?*', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          source: 'event',
          row: event,
          pages: {
            inputs: pageOf([
              {
                id: 'event-only',
                event_type: 'group.member.joined',
                content: { member_id: 'member-42' },
                metadata: {
                  routes: [
                    { status: 'not_matched', reason: 'No matching route' },
                  ],
                },
              },
            ]),
            outputs: pageOf([]),
            deliveries: pageOf([]),
          },
        },
      },
    }),
  );
  await page.goto('/home/monitoring');
  await page.getByRole('button').filter({ hasText: 'Member joined' }).click();
  const sheet = page.getByRole('dialog');
  await expect(
    sheet.getByRole('heading', { name: 'No processor run' }),
  ).toBeVisible();
  await expect(sheet.getByText(/member-42/)).toBeVisible();
  await expect(sheet.getByText(/No matching route/)).toBeVisible();
  await expect(sheet.getByText('Delivery records (0)')).toBeVisible();
});

test('filters all three processor kinds with the sidebar icons', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const processors = [
    { uuid: 'agent-one', name: 'Agent One', kind: 'agent', emoji: '🤖' },
    {
      uuid: 'pipeline-one',
      name: 'Pipeline One',
      kind: 'pipeline',
      emoji: '⚙️',
    },
    {
      uuid: 'event-one',
      name: 'Event One',
      kind: 'event_processor',
      emoji: '🧩',
    },
  ];
  await page.route('**/api/v1/agents', (route) =>
    route.fulfill({ json: { code: 0, data: { agents: processors } } }),
  );
  await page.goto('/home/monitoring');
  const filter = page.getByRole('combobox', { name: 'Processor', exact: true });
  for (const processor of processors) {
    await filter.click();
    const option = page.getByRole('option', {
      name: processor.name,
      exact: true,
    });
    await expect(
      option.getByText(processor.emoji, { exact: true }),
    ).toBeVisible();
    const request = page.waitForRequest((req) => {
      const url = new URL(req.url());
      return (
        url.pathname.endsWith('/monitoring/executions') &&
        url.searchParams.get('pipelineId') === processor.uuid
      );
    });
    await option.click();
    await request;
    await expect(filter).toContainText(processor.name);
    await expect(
      filter.getByText(processor.emoji, { exact: true }),
    ).toBeVisible();
  }
  await filter.click();
  await page
    .getByRole('option', { name: 'All Processors', exact: true })
    .click();
  await expect(filter).toContainText('All Processors');
});

test('shares mode and status filters with dashboard charts and records', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto('/home/monitoring');
  for (const [id, option, parameter, value] of [
    ['monitoring-filter-mode', 'Debug only', 'mode', 'debug'],
    ['monitoring-filter-status', 'Failed', 'status', 'failed'],
  ]) {
    await page.locator(`#${id}`).click();
    const requests = ['/monitoring/data', '/monitoring/executions'].map(
      (path) =>
        page.waitForRequest((req) => {
          const url = new URL(req.url());
          return (
            url.pathname.endsWith(path) &&
            url.searchParams.get(parameter) === value
          );
        }),
    );
    await page.getByRole('option', { name: option, exact: true }).click();
    await Promise.all(requests);
  }
});

test('remembers all filters on reload and persists resetting them', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.route('**/api/v1/platform/bots', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          bots: [{ uuid: 'bot-one', name: 'Saved Bot', adapter: 'aiocqhttp' }],
        },
      },
    }),
  );
  await page.route('**/api/v1/agents', (route) =>
    route.fulfill({
      json: {
        code: 0,
        data: {
          agents: [
            {
              uuid: 'processor-one',
              name: 'Saved Processor',
              kind: 'agent',
              emoji: '🤖',
            },
          ],
        },
      },
    }),
  );
  await page.goto('/home/monitoring');
  const selections = [
    ['bot', 'Saved Bot'],
    ['processor', 'Saved Processor'],
    ['mode', 'Debug only'],
    ['status', 'Failed'],
    ['time', 'Last 7 days'],
  ];
  for (const [id, label] of selections) {
    await page.locator(`#monitoring-filter-${id}`).click();
    await page.getByRole('option', { name: label, exact: true }).click();
  }
  await page.reload();
  for (const [id, label] of selections)
    await expect(page.locator(`#monitoring-filter-${id}`)).toContainText(label);
  await page
    .getByRole('button', { name: 'Reset Filters', exact: true })
    .click();
  await page.reload();
  for (const [id, label] of [
    ['bot', 'All Bots'],
    ['processor', 'All Processors'],
    ['mode', 'Live + debug'],
    ['status', 'All statuses'],
    ['time', 'Last 24 hours'],
  ]) {
    await expect(page.locator(`#monitoring-filter-${id}`)).toContainText(label);
  }
});

test('reset removes linked resource filters from the URL', async ({ page }) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto(
    '/home/monitoring?botId=linked-bot&pipelineId=linked-processor',
  );
  await page
    .getByRole('button', { name: 'Reset Filters', exact: true })
    .click();
  await expect(page).toHaveURL(/\/home\/monitoring$/);
  await page.reload();
  await expect(page.locator('#monitoring-filter-bot')).toContainText(
    'All Bots',
  );
  await expect(page.locator('#monitoring-filter-processor')).toContainText(
    'All Processors',
  );
});
