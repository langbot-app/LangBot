import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('event processor shows isolated logs, paginates and scrolls expanded payloads', async ({
  page,
}) => {
  await installLangBotApiMocks(page, { authenticated: true });
  const ref = 'event_processor:qa/welcome/default';
  const processor = {
    uuid: 'processor-qa',
    kind: 'event_processor',
    name: 'Welcome processor',
    component_ref: ref,
    supported_event_patterns: ['group.member_joined'],
    config: { runner: { id: ref }, runner_config: { [ref]: {} } },
  };
  const run = {
    run_id: 'run-one',
    status: 'completed',
    status_reason: 'stop',
    created_at: 1788000000,
    metadata: {
      event_type: 'group.member_joined',
      input_event: { member: { id: 'one' } },
      delivery: {
        reply_target: { target_type: 'group', target_id: 'test-group' },
      },
    },
  };
  const cursors: string[] = [];
  await page.route('**/api/v1/agents**', async (route) => {
    const url = new URL(route.request().url());
    let data: unknown;
    if (url.pathname.endsWith('/_/metadata')) {
      data = {
        kinds: [],
        event_processors: [
          {
            id: ref,
            label: { en_US: 'Welcome' },
            supported_event_patterns: ['group.member_joined'],
            config_schema: [],
            plugin_author: 'qa',
            plugin_name: 'welcome',
          },
        ],
      };
    } else if (url.pathname.endsWith('/runs/run-one/events')) {
      cursors.push(url.searchParams.get('after_sequence') ?? '');
      data = {
        run,
        items: url.searchParams.has('after_sequence')
          ? [
              {
                sequence: 101,
                type: 'processor.log',
                data: { level: 'info', text: 'Final log after pagination' },
              },
            ]
          : [
              {
                sequence: 1,
                type: 'processor.log',
                data: { level: 'info', text: 'Member received' },
              },
              {
                sequence: 100,
                type: 'tool.call.completed',
                data: {
                  result: Array.from(
                    { length: 100 },
                    (_, i) => `Payload line ${i}`,
                  ),
                },
              },
            ],
        has_more: !url.searchParams.has('after_sequence'),
        next_cursor: url.searchParams.has('after_sequence') ? null : 100,
      };
    } else if (url.pathname.endsWith('/runs')) {
      data = { items: [run], has_more: false, next_cursor: null, total: 1 };
    } else if (url.pathname.endsWith('/processor-qa')) {
      data = { agent: processor };
    } else {
      data = { agents: [processor] };
    }
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto('/home/agents?id=processor-qa');
  await expect(
    page.getByRole('heading', { name: 'Welcome processor' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Logs and message flow' }),
  ).toBeVisible();
  await expect(page.getByText('stop', { exact: true })).toHaveCount(0);
  await page
    .getByRole('button')
    .filter({ hasText: 'group.member_joined' })
    .click();
  await expect(
    page.getByText('Member received', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('Payload line 99', { exact: false }),
  ).toBeHidden();
  await page.locator('summary').filter({ hasText: 'Action result' }).click();
  await page.getByRole('button', { name: 'Load more', exact: true }).click();
  await page.getByText('Final log after pagination').scrollIntoViewIfNeeded();
  await expect(page.getByText('Final log after pagination')).toBeInViewport();
  expect(cursors).toEqual(['', '100']);
  await expect(
    page.getByRole('button', { name: 'Load more', exact: true }),
  ).toHaveCount(0);
});
