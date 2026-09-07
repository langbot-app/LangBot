import { expect, test } from '@playwright/test';
import { installLangBotApiMocks } from './fixtures/langbot-api';

test('create first, select a plugin in the header, debug beside scrollable logs', async ({
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
    config: {
      runner: { id: ref },
      runner_config: { [ref]: { greeting: 'Hello' } },
    },
  };
  const run = {
    run_id: 'run-one',
    status: 'completed',
    status_reason: 'stop',
    created_at: 1788000000,
    started_at_ms: 1788000000000,
    finished_at_ms: 1788000000500,
    metadata: {
      event_type: 'group.member_joined',
      input_event: { member: { id: 'one' } },
      delivery: {
        reply_target: { target_type: 'group', target_id: 'test-group' },
      },
    },
  };
  const cursors: string[] = [];
  const debugRequests: unknown[] = [];
  const operations: string[] = [];
  const creations: unknown[] = [];
  await page.route('**/api/v1/agents**', async (route) => {
    const url = new URL(route.request().url());
    let data: unknown;
    if (
      url.pathname === '/api/v1/agents' &&
      route.request().method() === 'POST'
    ) {
      const payload = route.request().postDataJSON();
      creations.push(payload);
      Object.assign(processor, payload, {
        component_ref: null,
        config: {},
        supported_event_patterns: [],
      });
      await route.fulfill({
        json: { code: 0, data: { uuid: processor.uuid, kind: processor.kind } },
      });
      return;
    } else if (url.pathname.endsWith('/debug/stream')) {
      operations.push('debug');
      debugRequests.push(route.request().postDataJSON());
      const events = [
        {
          type: 'processor.log',
          sequence: 1,
          data: { level: 'info', text: 'Debug handler invoked once' },
        },
        {
          type: 'tool.call.started',
          sequence: 2,
          data: { tool_name: 'event_reply', parameters: { text: 'Welcome' } },
        },
        {
          type: 'tool.call.completed',
          sequence: 3,
          data: {
            tool_name: 'event_reply',
            result: { mock: true, ok: true, delivery: 'simulated' },
          },
        },
        { type: 'run.completed', sequence: 4, data: {} },
      ];
      await route.fulfill({
        contentType: 'application/x-ndjson',
        body:
          [
            ...events.map((data) => ({ kind: 'result', data })),
            { kind: 'completed', data: { final_text: '' } },
          ]
            .map((frame) => JSON.stringify(frame))
            .join('\n') + '\n',
      });
      return;
    } else if (url.pathname.endsWith('/_/metadata')) {
      data = {
        kinds: [],
        event_processors: [
          {
            id: ref,
            label: { en_US: 'Welcome' },
            supported_event_patterns: ['group.member_joined'],
            config_schema: [
              {
                name: 'greeting',
                type: 'string',
                label: { en_US: 'Greeting' },
                default: 'Hello',
                required: true,
              },
            ],
            plugin_author: 'qa',
            plugin_name: 'welcome',
          },
        ],
      };
    } else if (url.pathname.endsWith('/runs/run-two/events')) {
      data = {
        run: {
          ...run,
          run_id: 'run-two',
          metadata: { event_type: 'group.member_left' },
        },
        items: [
          {
            sequence: 1,
            type: 'processor.log',
            created_at_ms: 1788000000000,
            data: { text: 'Older run selected', level: 'info' },
          },
        ],
        has_more: false,
        next_cursor: null,
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
                created_at_ms: 1788000000000,
              },
              {
                sequence: 2,
                type: 'tool.call.started',
                created_at_ms: 1788000000050,
                data: {
                  tool_call_id: 'reply-one',
                  tool_name: 'event_reply',
                  parameters: { text: 'Welcome' },
                },
              },
              {
                sequence: 3,
                type: 'tool.call.completed',
                created_at_ms: 1788000000200,
                data: {
                  tool_call_id: 'reply-one',
                  tool_name: 'event_reply',
                  result: { ok: true },
                },
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
      data = {
        items: debugRequests.length
          ? [
              run,
              {
                ...run,
                run_id: 'run-two',
                created_at: run.created_at - 60,
                started_at_ms: 1787999940000,
                finished_at_ms: 1787999940200,
                metadata: { event_type: 'group.member_left' },
              },
            ]
          : [],
        has_more: false,
        next_cursor: null,
        total: debugRequests.length,
      };
    } else if (url.pathname.endsWith('/processor-qa')) {
      if (route.request().method() === 'PUT') {
        operations.push('save');
        Object.assign(processor, route.request().postDataJSON(), {
          supported_event_patterns: ['group.member_joined'],
        });
      }
      data = { agent: processor };
    } else {
      data = { agents: [processor] };
    }
    await route.fulfill({ json: { code: 0, data } });
  });
  await page.goto('/home/agents?id=new');
  await page.locator('[data-processor-kind="event_processor"]').click();
  await expect(
    page.getByRole('combobox', { name: 'Plugin component' }),
  ).toHaveCount(0);
  await page
    .getByRole('textbox', { name: 'Name', exact: false })
    .fill('Welcome processor');
  await page.getByRole('button', { name: 'Submit', exact: true }).click();
  await expect(page).toHaveURL(/id=processor-qa/);
  expect(creations).toHaveLength(1);
  expect(creations[0]).toMatchObject({
    kind: 'event_processor',
    name: 'Welcome processor',
  });
  expect(creations[0]).not.toHaveProperty('component_ref');
  expect(creations[0]).not.toHaveProperty('config');
  const panel = page.getByRole('region', { name: 'Event Debug' });
  const logs = page.getByRole('region', { name: 'Logs and message flow' });
  await expect(panel).toBeVisible();
  await expect(logs).toBeVisible();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(panel.getByRole('button', { name: 'Run test' })).toHaveCount(0);
  await page.getByRole('combobox', { name: 'Plugin component' }).click();
  await page.getByRole('option').filter({ hasText: 'Welcome' }).click();
  await expect(
    panel.getByRole('combobox', { name: 'Event type' }),
  ).toContainText('group.member_joined');
  await expect(page.getByText('Greeting', { exact: true })).toHaveCount(0);
  await page
    .getByRole('button', { name: 'Plugin settings', exact: true })
    .click();
  const settings = page.locator('[data-slot="popover-content"]');
  await settings.getByRole('textbox').fill('Welcome');
  await page.keyboard.press('Escape');
  await panel
    .getByRole('textbox', { name: 'Member ID' })
    .fill('debug-member-42');
  await panel.getByRole('button', { name: 'Save and run' }).click();
  await expect(panel.getByText('Debug handler invoked once')).toBeVisible();
  expect(operations).toEqual(['save', 'debug']);
  expect(debugRequests).toHaveLength(1);
  expect(debugRequests[0]).toMatchObject({
    event_type: 'group.member_joined',
    data: { member: { id: 'debug-member-42' } },
  });
  await expect(
    logs.getByText('Member received', { exact: true }),
  ).toBeVisible();
  await expect(
    logs.getByText('Payload line 99', { exact: false }),
  ).toBeHidden();
  const runList = logs.getByRole('group', { name: 'Runs', exact: true });
  await expect(logs.getByRole('combobox')).toHaveCount(0);
  await expect(runList.getByRole('button')).toHaveCount(2);
  await expect(runList.getByText('500 ms', { exact: true })).toBeVisible();
  await expect(runList.getByText('200 ms', { exact: true })).toBeVisible();
  await expect(runList.getByText('Member received')).toHaveCount(0);
  await runList.getByRole('button', { name: /group.member_left/ }).click();
  await expect(logs.getByText('Older run selected')).toBeVisible();
  await runList.getByRole('button', { name: /group.member_joined/ }).click();
  await expect(
    logs.getByText('Member received', { exact: true }),
  ).toBeVisible();
  await logs
    .getByRole('button', { name: 'Action result', exact: true })
    .click();
  await logs.getByRole('button', { name: 'Load more' }).click();
  await logs.getByText('Final log after pagination').scrollIntoViewIfNeeded();
  await expect(logs.getByText('Final log after pagination')).toBeInViewport();
  expect(cursors).toContain('100');
  await expect(panel.getByText('Debug handler invoked once')).toBeVisible();
  const debugBox = await panel.boundingBox();
  const logBox = await logs.boundingBox();
  expect(debugBox!.x).toBeLessThan(logBox!.x);
  await page.setViewportSize({ width: 390, height: 700 });
  await panel
    .getByRole('button', { name: 'Run test' })
    .scrollIntoViewIfNeeded();
  await expect(
    panel.getByRole('button', { name: 'Run test' }),
  ).toBeInViewport();
  await logs.getByText('Final log after pagination').scrollIntoViewIfNeeded();
  await expect(logs.getByText('Final log after pagination')).toBeInViewport();
});
