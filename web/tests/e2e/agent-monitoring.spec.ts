import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

const run = (id: string, status = 'completed') => ({
  run_id: id,
  binding_id: `debug:agent-logs:plugin:qa/agent/default`,
  runner_id: 'plugin:qa/agent/default',
  status,
  status_reason: status === 'failed' ? 'Model request timed out' : 'stop',
  created_at: 1788000000,
  started_at_ms: 1788000000000,
  finished_at_ms: 1788000001500,
  metadata: {
    event_type: 'message.received',
    source: 'webui',
    input: { text: `Task ${id}` },
  },
  usage: { prompt_tokens: 30, completion_tokens: 12, total_tokens: 42 },
});

test('Agent logs show task execution and keep the debug draft when switching tabs', async ({
  page,
}) => {
  await installLangBotApiMocks(page, {
    authenticated: true,
    withAdapterEvents: true,
    withRunnerToolSelector: true,
  });
  let listCalls = 0;
  await page.route('**/api/v1/agents/agent-logs/runs**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/runs')) {
      listCalls++;
      return route.fulfill({
        json: {
          code: 0,
          data: {
            items: [run('done'), run('failed', 'failed')],
            total: 2,
            has_more: false,
            next_cursor: null,
          },
        },
      });
    }
    const failed = url.pathname.includes('/failed/');
    return route.fulfill({
      json: {
        code: 0,
        data: {
          run: run(failed ? 'failed' : 'done', failed ? 'failed' : 'completed'),
          items: failed
            ? []
            : [
                {
                  sequence: 1,
                  type: 'message.delta',
                  data: {
                    chunk: {
                      role: 'assistant',
                      content: 'Checking the weather.',
                      model: 'test-model',
                    },
                  },
                },
                {
                  sequence: 2,
                  type: 'tool.call.started',
                  data: {
                    tool_call_id: 'call-1',
                    tool_name: 'weather_lookup',
                    parameters: { city: 'Beijing' },
                  },
                },
                {
                  sequence: 3,
                  type: 'tool.call.completed',
                  data: {
                    tool_call_id: 'call-1',
                    tool_name: 'weather_lookup',
                    result: { forecast: 'Sunny' },
                  },
                },
                {
                  sequence: 4,
                  type: 'message.completed',
                  data: {
                    message: {
                      role: 'assistant',
                      content: 'It will be sunny.',
                      model: 'test-model',
                    },
                  },
                },
              ],
          has_more: false,
          next_cursor: null,
        },
      },
    });
  });
  await page.goto('/home/agents?id=agent-logs');
  const debug = page.getByRole('region', { name: 'Event Debug', exact: true });
  const draft = debug.getByRole('textbox', { name: 'Message content' });
  await draft.fill('Keep this draft');
  expect(listCalls).toBe(0);
  await page.getByRole('tab', { name: 'Run logs', exact: true }).click();
  const log = page.getByTestId('agent-monitoring');
  await expect(
    log.getByText('Task done', { exact: true }).last(),
  ).toBeVisible();
  await expect(log.getByText('test-model', { exact: true })).toBeVisible();
  await expect(log.getByText('weather_lookup', { exact: true })).toBeVisible();
  await expect(
    log.getByText('It will be sunny.', { exact: true }),
  ).toBeVisible();
  await expect(log.getByText('Beijing', { exact: false })).not.toBeVisible();
  await log.getByRole('button', { name: 'Arguments', exact: true }).click();
  await expect(log.getByText(/"city": "Beijing"/)).toBeVisible();
  await log.getByRole('button').filter({ hasText: 'Task failed' }).click();
  await expect(log.getByText('Model request timed out')).toBeVisible();
  await expect(log.getByText('It will be sunny.', { exact: true })).toHaveCount(
    0,
  );
  await page
    .getByRole('tab', { name: 'Configure & debug', exact: true })
    .click();
  await expect(draft).toHaveValue('Keep this draft');
  await expect(page.getByTestId('agent-monitoring')).toHaveCount(0);
});

test('Agent log pagination retains selection and ignores a slow previous detail response', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let release: () => void = () => {};
  const slow = new Promise<void>((resolve) => {
    release = resolve;
  });
  let slowRequested = false;
  await page.route('**/api/v1/agents/agent-logs/runs**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/runs'))
      return route.fulfill({
        json: {
          code: 0,
          data: {
            items: url.searchParams.has('before_id')
              ? [run('older')]
              : [run('slow'), run('fast')],
            total: 3,
            has_more: !url.searchParams.has('before_id'),
            next_cursor: url.searchParams.has('before_id') ? null : 2,
          },
        },
      });
    const id = url.pathname.split('/').at(-2)!;
    if (id === 'slow') {
      slowRequested = true;
      await slow;
    }
    const more = id === 'fast' && !url.searchParams.has('after_sequence');
    return route.fulfill({
      json: {
        code: 0,
        data: {
          run: run(id),
          items: [
            {
              sequence: more ? 1 : 2,
              type: 'message.completed',
              data: {
                message: {
                  role: 'assistant',
                  content: more ? 'First step' : `Result ${id}`,
                },
              },
            },
          ],
          has_more: more,
          next_cursor: more ? 1 : null,
        },
      },
    });
  });
  await page.goto('/home/agents?id=agent-logs');
  await page.getByRole('tab', { name: 'Run logs', exact: true }).click();
  await expect.poll(() => slowRequested).toBe(true);
  const log = page.getByTestId('agent-monitoring');
  await log.getByRole('button').filter({ hasText: 'Task fast' }).click();
  await expect(log.getByText('First step', { exact: true })).toBeVisible();
  release();
  await log
    .getByRole('region', { name: 'Execution steps' })
    .getByRole('button', { name: 'Load more' })
    .click();
  await expect(log.getByText('Result fast', { exact: true })).toBeVisible();
  await expect(log.getByText('Result slow', { exact: true })).toHaveCount(0);
  await log.getByRole('button', { name: 'Load more', exact: true }).click();
  await expect(
    log.getByRole('button').filter({ hasText: 'Task older' }),
  ).toBeVisible();
  await expect(
    log.getByRole('button').filter({ hasText: 'Task fast' }),
  ).toHaveAttribute('aria-pressed', 'true');
});

test('Agent logs show an empty state and retry request errors', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  let fail = true;
  await page.route('**/api/v1/agents/agent-logs/runs**', (route) =>
    fail
      ? route.fulfill({ status: 500, json: { code: -1, msg: 'Unavailable' } })
      : route.fulfill({
          json: {
            code: 0,
            data: { items: [], total: 0, has_more: false, next_cursor: null },
          },
        }),
  );
  await page.goto('/home/agents?id=agent-logs');
  await page.getByRole('tab', { name: 'Run logs', exact: true }).click();
  const log = page.getByTestId('agent-monitoring');
  await expect(log.getByRole('alert')).toBeVisible();
  fail = false;
  await log.getByRole('button', { name: 'Refresh', exact: false }).click();
  await expect(log.getByRole('alert')).toHaveCount(0);
  await expect(log.getByText('No runs yet.', { exact: false })).toBeVisible();
});
