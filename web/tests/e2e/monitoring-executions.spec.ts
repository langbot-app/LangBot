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

test('loads external input images and previews without sending a referrer', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    monitoringData: monitoring,
  });
  const imageUrl = 'https://images.example.test/attachment.png';
  const referrers: (string | undefined)[] = [];
  await page.route(imageUrl, async (route) => {
    const referrer = route.request().headers().referer;
    referrers.push(referrer);
    // Match providers that return JSON errors for embedded requests.
    if (referrer) {
      await route.fulfill({ status: 400, json: { error: 'Invalid referrer' } });
      return;
    }
    await route.fulfill({
      contentType: 'image/png',
      headers: { 'Cache-Control': 'no-store' },
      body: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1sAAAAASUVORK5CYII=',
        'base64',
      ),
    });
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
              { id: 'image', content: [{ type: 'Image', url: imageUrl }] },
            ]),
            outputs: pageOf([]),
            deliveries: pageOf([]),
            errors: pageOf([]),
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
  const thumbnail = page.getByRole('img', { name: 'Message attachment' });
  await expect
    .poll(() => thumbnail.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBe(1);
  await thumbnail.click();
  const preview = page.getByRole('img', { name: 'Preview', exact: true });
  await expect(preview).toBeVisible();
  await expect
    .poll(() => preview.evaluate((img: HTMLImageElement) => img.naturalWidth))
    .toBe(1);
  expect(referrers).toEqual([undefined, undefined]);
});

test('loads collapsed history on demand, retries and pages without reloading it on reopen', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    monitoringData: monitoring,
  });
  const requests: string[] = [];
  let failHistory = true;
  await page.route('**/api/v1/monitoring/executions/*/*?*', async (route) => {
    const url = new URL(route.request().url());
    const section = url.searchParams.get('section');
    requests.push(url.search);
    if (section === 'conversation' && failHistory) {
      failHistory = false;
      await route.fulfill({
        status: 500,
        json: { code: 500, msg: 'Temporary failure' },
      });
      return;
    }
    const offset = Number(url.searchParams.get('offset') || 0);
    const pages =
      section === 'overview'
        ? {
            inputs: pageOf([{ id: 'input', content: 'Selected message' }]),
            outputs: pageOf([]),
            deliveries: pageOf([]),
            errors: pageOf([]),
          }
        : section === 'conversation'
          ? {
              conversation: pageOf(
                [
                  {
                    id: `history-${offset}`,
                    content: offset ? 'Older history' : 'Recent history',
                  },
                ],
                offset === 0,
                offset + 1,
              ),
            }
          : { related: pageOf([]) };
    await route.fulfill({
      json: { code: 0, data: { source: 'pipeline', row, pages } },
    });
  });
  await page.goto('/home/monitoring');
  await page
    .getByRole('button')
    .filter({ hasText: 'Open this execution' })
    .click();
  const sheet = page.getByRole('dialog');
  await expect(
    sheet.getByText('Selected message').filter({ visible: true }),
  ).toBeVisible();
  expect(requests).toEqual(['?section=overview']);
  const history = sheet.locator('details').filter({
    has: page.locator('summary', { hasText: /^Conversation context/ }),
  });
  await history.locator(':scope > summary').click();
  await expect(history.getByRole('alert')).toBeVisible();
  await history.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(
    history.getByText('Recent history').filter({ visible: true }),
  ).toBeVisible();
  await history.getByRole('button', { name: 'Load more', exact: true }).click();
  await expect(
    history.getByText('Older history').filter({ visible: true }),
  ).toBeVisible();
  await expect(
    history.getByText('Recent history').filter({ visible: true }),
  ).toBeVisible();
  const count = requests.length;
  await history.locator(':scope > summary').click();
  await history.locator(':scope > summary').click();
  await expect(
    history.getByText('Older history').filter({ visible: true }),
  ).toBeVisible();
  expect(requests).toHaveLength(count);
  expect(requests.every((query) => !query.includes('section=related'))).toBe(
    true,
  );
});

test('ignores a late history response after selecting a different execution', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    monitoringData: monitoring,
  });
  let releaseHistory: (() => void) | undefined;
  const requested: string[] = [];
  await page.route('**/api/v1/monitoring/executions/*/*?*', async (route) => {
    const url = new URL(route.request().url());
    const section = url.searchParams.get('section');
    const sibling = url.pathname.endsWith('/sibling');
    requested.push(`${sibling ? 'sibling' : 'original'}:${section}`);
    if (section === 'conversation')
      await new Promise<void>((resolve) => {
        releaseHistory = resolve;
      });
    const pages =
      section === 'overview'
        ? {
            inputs: pageOf([
              {
                id: 'input',
                content: sibling ? 'Sibling selection' : 'Original selection',
              },
            ]),
            outputs: pageOf([]),
            deliveries: pageOf([]),
            errors: pageOf([]),
          }
        : section === 'related'
          ? {
              related: pageOf([
                { ...row, id: 'sibling', target_name: 'Processor B' },
              ]),
            }
          : {
              conversation: pageOf([
                { id: 'late', content: 'Late old history' },
              ]),
            };
    await route.fulfill({
      json: {
        code: 0,
        data: {
          source: 'pipeline',
          row: sibling ? { ...row, id: 'sibling' } : row,
          pages,
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
  await expect(
    sheet.getByText('Original selection').filter({ visible: true }),
  ).toBeVisible();
  await sheet
    .locator('summary')
    .filter({ hasText: /^Conversation context/ })
    .click();
  await expect.poll(() => !!releaseHistory).toBe(true);
  await sheet
    .locator('summary')
    .filter({ hasText: /^Related executions/ })
    .click();
  await sheet.getByRole('button', { name: /Processor B/ }).click();
  await expect(
    sheet.getByText('Sibling selection').filter({ visible: true }),
  ).toBeVisible();
  const response = page.waitForResponse(
    (res) => new URL(res.url()).searchParams.get('section') === 'conversation',
  );
  releaseHistory!();
  await response;
  await expect(sheet.getByText('Late old history')).toHaveCount(0);
  expect(requested.filter((value) => value.startsWith('sibling:'))).toEqual([
    'sibling:overview',
  ]);
});

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
  await expect(
    sheet.getByText('你好~', { exact: true }).filter({ visible: true }),
  ).toHaveCount(2);
  await expect(sheet.getByText('[Empty message]', { exact: true })).toHaveCount(
    0,
  );
  for (const details of await sheet
    .locator('summary')
    .filter({ hasText: /^Details$/ })
    .all())
    await details.click();
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
    await expect(
      sheet.getByText(text, { exact: true }).filter({ visible: true }).first(),
    ).toBeVisible();
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
  await expect(
    sheet.getByText('Generated but not sent').filter({ visible: true }),
  ).toBeVisible();
  await expect(sheet.getByText('Delivery records (0)')).toBeVisible();
  await sheet.getByText('Execution events (1+)', { exact: true }).click();
  await sheet.getByRole('button', { name: 'Load more' }).click();
  await expect(sheet.getByText('run.completed', { exact: true })).toBeVisible();
  await expect(
    sheet.getByText('Original input').filter({ visible: true }),
  ).toBeVisible();
  expect(
    requests.some(
      (query) =>
        query.includes('section=events') && query.includes('offset=100'),
    ),
  ).toBe(true);
  await sheet.getByText('Related executions (1)', { exact: true }).click();
  await sheet.getByRole('button', { name: /Processor B/ }).click();
  await expect(
    sheet.getByText('Sibling input').filter({ visible: true }),
  ).toBeVisible();
  await expect(
    sheet.getByText('Original input').filter({ visible: true }),
  ).toHaveCount(0);
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
  await sheet
    .locator('summary')
    .filter({ hasText: /^Details$/ })
    .first()
    .click();
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
  const filter = page.locator('#monitoring-filter-processor');
  await filter.click();
  const popup = page.getByRole('dialog');
  for (const processor of processors) {
    const option = popup.getByRole('checkbox', {
      name: processor.name,
      exact: true,
    });
    await expect(
      option.locator('..').getByText(processor.emoji, { exact: true }),
    ).toBeVisible();
    const request = page.waitForRequest((req) => {
      const url = new URL(req.url());
      return (
        url.pathname.endsWith('/monitoring/executions') &&
        url.searchParams.getAll('pipelineId').includes(processor.uuid)
      );
    });
    await option.check();
    await request;
    await expect(option).toBeChecked();
  }
  await expect(filter).toContainText('3');
  await popup
    .getByRole('button', { name: 'All Processors', exact: true })
    .click();
  await expect(popup.getByRole('checkbox', { checked: true })).toHaveCount(0);
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

test('restores filter trigger focus when closing with Escape', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto('/home/monitoring');
  for (const id of ['bot', 'mode', 'status', 'time']) {
    const trigger = page.locator(`#monitoring-filter-${id}`);
    await trigger.click();
    await expect(page.getByRole('listbox')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(trigger).toBeFocused();
    await expect(page.getByRole('listbox')).toHaveCount(0);
  }
});

test('keeps the custom range dialog focused when its select closes', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  await page.goto('/home/monitoring');
  await page.locator('#monitoring-filter-time').click();
  await page
    .getByRole('option', { name: 'Custom time range', exact: true })
    .click();
  const dialog = page.getByRole('dialog', { name: 'Custom time range' });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('input').first()).toBeFocused();
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
    if (id === 'processor') {
      const checkbox = page.getByRole('dialog').getByRole('checkbox', {
        name: label,
        exact: true,
      });
      await checkbox.check();
      await expect(checkbox).toBeChecked();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog')).toHaveCount(0);
    } else {
      await page.getByRole('option', { name: label, exact: true }).click();
      await expect(page.getByRole('listbox')).toHaveCount(0);
    }
    // The previous popup must finish restoring focus before opening another.
    await expect(page.locator(`#monitoring-filter-${id}`)).toBeFocused();
  }
  await page.reload();
  for (const [id, label] of selections) {
    if (id === 'processor') {
      await page.locator('#monitoring-filter-processor').click();
      await expect(
        page.getByRole('checkbox', { name: label, exact: true }),
      ).toBeChecked();
      await page.keyboard.press('Escape');
    } else
      await expect(page.locator(`#monitoring-filter-${id}`)).toContainText(
        label,
      );
  }
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
