import { expect, test, type Page } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const botId = 'bot-tool-timeline';
const timestamp = (index: number) =>
  new Date(Date.UTC(2026, 2, 8, 10, index)).toISOString();
const message = (index: number) => ({
  id: `page-message-${index}`,
  timestamp: timestamp(index),
  bot_id: botId,
  bot_name: 'Boundary Bot',
  pipeline_id: 'pipeline-tool-timeline',
  pipeline_name: 'Boundary Pipeline',
  message_content: `message row ${index}`,
  session_id: 'person-boundary-0',
  role: 'assistant',
  status: 'success',
  level: 'info',
  platform: 'bot',
  user_id: 'boundary-user',
  user_name: 'Boundary User',
});

async function openMonitor(page: Page) {
  await installLangBotApiMocks(page, { authenticated: true });
  const requests: {
    path: string;
    query: Record<string, string>;
    headers: Record<string, string>;
  }[] = [];
  await page.route('**/api/v1/monitoring/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (!/\/(sessions|messages|analysis)$/.test(path)) return route.fallback();
    requests.push({
      path,
      query: Object.fromEntries(url.searchParams),
      headers: route.request().headers(),
    });
    const offset = Number(url.searchParams.get('offset') ?? 0);
    let data: unknown;
    if (path.endsWith('/sessions')) {
      data = {
        total: 21,
        sessions: [
          {
            session_id: `person-boundary-${offset}`,
            bot_id: botId,
            bot_name: 'Boundary Bot',
            pipeline_id: 'pipeline-tool-timeline',
            pipeline_name: 'Boundary Pipeline',
            user_id: `boundary-${offset}`,
            user_name: offset ? 'Page two User' : 'Boundary User',
            message_count: 52,
            start_time: timestamp(0),
            last_activity: timestamp(51),
            is_active: true,
          },
        ],
      };
    } else if (path.endsWith('/messages')) {
      data = {
        total: 52,
        messages: Array.from({ length: 52 }, (_, index) => message(index))
          .slice(offset, offset + 50)
          .reverse(),
      };
    } else {
      const start =
        Date.parse(url.searchParams.get('startTime') ?? '') || -Infinity;
      const end = Date.parse(url.searchParams.get('endTime') ?? '') || Infinity;
      data = {
        found: true,
        tool_calls: [1, 50]
          .filter(
            (index) =>
              Date.parse(timestamp(index)) >= start &&
              Date.parse(timestamp(index)) <= end,
          )
          .map((index) => ({
            id: `tool-${index}`,
            timestamp: timestamp(index),
            tool_name: index === 1 ? 'first_page_tool' : 'second_page_tool',
            tool_source: 'native',
            status: 'success',
            duration: 20,
            bot_id: botId,
            session_id: 'person-boundary-0',
            arguments: '{}',
            result: '{}',
          })),
      };
    }
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto(`/home/bots?id=${botId}`);
  await page.getByRole('tab', { name: /Sessions/ }).click();
  await expect(
    page.getByRole('button', { name: /Boundary User/ }),
  ).toBeVisible();
  return requests;
}

async function selectSession(page: Page) {
  await page.getByRole('button', { name: /Boundary User/ }).click();
  await expect(page.getByText('message row 0', { exact: true })).toBeVisible();
}

test('session pages send the server offset and reset it when the user filter is applied', async ({
  page,
}) => {
  const requests = await openMonitor(page);
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(
    page.getByRole('button', { name: /Page two User/ }),
  ).toBeVisible();
  const pageRequest = requests
    .filter((request) => request.path.endsWith('/sessions'))
    .at(-1)!;
  expect(pageRequest.query).toMatchObject({ botId, limit: '20', offset: '20' });
  expect(pageRequest.headers['x-workspace-id']).toBe('workspace-playwright');
  expect(pageRequest.headers.authorization).toBe('Bearer playwright-token');
  await page.getByRole('textbox', { name: 'User ID or name' }).fill('alice');
  await page.getByRole('textbox', { name: 'User ID or name' }).press('Enter');
  await expect
    .poll(
      () =>
        requests.filter((request) => request.path.endsWith('/sessions')).at(-1)
          ?.query,
    )
    .toMatchObject({ botId, limit: '20', offset: '0', userQuery: 'alice' });
  await expect(
    page.getByRole('button', { name: /Boundary User/ }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: /Page two User/ })).toHaveCount(
    0,
  );
});

test('message pages replace the visible rows with the requested bounded page', async ({
  page,
}) => {
  const requests = await openMonitor(page);
  await selectSession(page);
  await expect(page.getByText('message row 49', { exact: true })).toHaveCount(
    1,
  );
  await expect(page.getByText('message row 50', { exact: true })).toHaveCount(
    0,
  );
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(page.getByText('message row 50', { exact: true })).toBeVisible();
  await expect(page.getByText('message row 51', { exact: true })).toHaveCount(
    1,
  );
  await expect(page.getByText('message row 0', { exact: true })).toHaveCount(0);
  await expect(page.getByText('message row 49', { exact: true })).toHaveCount(
    0,
  );
  expect(
    requests.filter((request) => request.path.endsWith('/messages')).at(-1)
      ?.query,
  ).toMatchObject({
    botId,
    limit: '50',
    offset: '50',
    sessionId: 'person-boundary-0',
  });
});

for (const change of ['page', 'user', 'start date', 'end date']) {
  test(`changing ${change} clears the selected session detail`, async ({
    page,
  }) => {
    await openMonitor(page);
    await selectSession(page);
    if (change === 'page')
      await page.getByRole('button', { name: 'Next', exact: true }).click();
    else if (change === 'user') {
      await page
        .getByRole('textbox', { name: 'User ID or name' })
        .fill('alice');
      await page
        .getByRole('textbox', { name: 'User ID or name' })
        .press('Enter');
    } else
      await page
        .getByLabel(change === 'start date' ? 'Start date' : 'End date')
        .fill('2026-03-08');
    await expect(
      page.getByText('Select a session to view messages', { exact: true }),
    ).toBeVisible();
    await expect(page.getByText('message row 0', { exact: true })).toHaveCount(
      0,
    );
  });
}

for (const [timezoneId, start, end] of [
  [
    'America/Los_Angeles',
    '2026-03-08T08:00:00.000Z',
    '2026-03-09T06:59:59.999Z',
  ],
  ['Asia/Shanghai', '2026-03-07T16:00:00.000Z', '2026-03-08T15:59:59.999Z'],
]) {
  test.describe(timezoneId, () => {
    test.use({ timezoneId });
    test('date filters send the operator local calendar day boundaries', async ({
      page,
    }) => {
      const requests = await openMonitor(page);
      await page.getByLabel('Start date').fill('2026-03-08');
      await page.getByLabel('End date').fill('2026-03-08');
      await expect
        .poll(
          () =>
            requests
              .filter((request) => request.path.endsWith('/sessions'))
              .at(-1)?.query,
        )
        .toMatchObject({ startTime: start, endTime: end, offset: '0' });
    });
  });
}

test('tool analysis follows the visible message page rather than the previous page', async ({
  page,
}) => {
  const requests = await openMonitor(page);
  await selectSession(page);
  await expect(
    page.getByText('first_page_tool', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('second_page_tool', { exact: true })).toHaveCount(
    0,
  );
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(
    page.getByText('second_page_tool', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('first_page_tool', { exact: true })).toHaveCount(
    0,
  );
  const analysis = requests
    .filter((request) => request.path.endsWith('/analysis'))
    .at(-1)!;
  expect(analysis.path).toContain('/sessions/person-boundary-0/analysis');
  expect(analysis.query).toMatchObject({
    botId,
    startTime: timestamp(50),
    endTime: timestamp(51),
  });
  expect(analysis.headers['x-workspace-id']).toBe('workspace-playwright');
  expect(analysis.headers.authorization).toBe('Bearer playwright-token');
});
