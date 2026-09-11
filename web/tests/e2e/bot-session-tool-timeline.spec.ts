import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const botId = 'bot-tool-timeline';
const sessionId = 'person-tool-timeline-user';
const botName = 'Tool Timeline Bot';
const pipelineId = 'pipeline-tool-timeline';
const pipelineName = 'Tool Timeline Pipeline';

function at(minute: number, second = 0) {
  return `2026-07-02T10:${String(minute).padStart(2, '0')}:${String(
    second,
  ).padStart(2, '0')}Z`;
}

function sessionMessage(
  id: string,
  role: 'user' | 'assistant',
  minute: number,
  content: string,
) {
  return {
    id,
    timestamp: at(minute),
    bot_id: botId,
    bot_name: botName,
    pipeline_id: pipelineId,
    pipeline_name: pipelineName,
    message_content: content,
    session_id: sessionId,
    status: 'success',
    level: 'info',
    platform: role === 'user' ? 'person' : 'bot',
    user_id: 'timeline-user',
    user_name: 'Timeline User',
    runner_name: role === 'assistant' ? 'local-agent' : null,
    variables: '{}',
    role,
  };
}

function toolCall(
  id: string,
  minute: number,
  toolName: string,
  duration: number,
  status: 'success' | 'error' = 'success',
) {
  return {
    id,
    timestamp: at(minute, 30),
    tool_name: toolName,
    tool_source: 'native',
    duration,
    status,
    bot_id: botId,
    bot_name: botName,
    pipeline_id: pipelineId,
    pipeline_name: pipelineName,
    session_id: sessionId,
    message_id: 'user-message',
    arguments: JSON.stringify({ target: toolName }),
    result: status === 'success' ? JSON.stringify({ ok: true }) : null,
    error_message: status === 'error' ? 'Tool execution failed' : null,
  };
}

test.describe('bot session request recovery', () => {
  for (const failure of [
    'initial list',
    'list page',
    'session switch',
    'message page',
    'analysis',
  ]) {
    test(`${failure} failure is visible and retry recovers`, async ({
      page,
    }) => {
      await installLangBotApiMocks(page, { authenticated: true });
      let failing = true;
      await page.route('**/api/v1/monitoring/**', async (route) => {
        const url = new URL(route.request().url());
        const offset = Number(url.searchParams.get('offset') || 0);
        const second = url.searchParams.get('sessionId') === 'person-second';
        const list = url.pathname.endsWith('/sessions');
        const message = url.pathname.endsWith('/messages');
        const analysis = url.pathname.endsWith('/analysis');
        if (!list && !message && !analysis) return route.fallback();
        const fail =
          failing &&
          ((list && failure === 'initial list') ||
            (list && failure === 'list page' && offset > 0) ||
            (message && failure === 'session switch' && second) ||
            (message && failure === 'message page' && offset > 0) ||
            (analysis && failure === 'analysis'));
        if (fail)
          return route.fulfill({
            status: 500,
            json: { code: 500, message: 'fixture failure' },
          });
        const data = list
          ? {
              sessions: [sessionId, 'person-second'].map((id, i) => ({
                session_id: id,
                bot_id: botId,
                bot_name: botName,
                pipeline_id: pipelineId,
                pipeline_name: pipelineName,
                message_count: 51,
                start_time: at(0),
                last_activity: at(4),
                is_active: true,
                user_name: offset ? `Page two ${i}` : `Recovery user ${i}`,
              })),
              total: 21,
            }
          : message
            ? {
                messages: [
                  sessionMessage(
                    'recovery-message',
                    'user',
                    0,
                    second
                      ? 'Second session message'
                      : offset
                        ? 'Second page message'
                        : 'Successful message',
                  ),
                ],
                total: 51,
              }
            : {
                tool_calls: [
                  toolCall('recovery-tool', 1, 'recovered_tool', 40),
                ],
              };
        return route.fulfill({ json: { code: 0, data } });
      });
      await page.goto(`/home/bots?id=${botId}`);
      await page.getByRole('tab', { name: /Sessions/ }).click();
      if (failure === 'list page') {
        await page.getByRole('button', { name: 'Next', exact: true }).click();
      } else if (failure !== 'initial list') {
        await page.getByRole('button', { name: /Recovery user 0/ }).click();
        if (failure !== 'analysis') {
          await expect(
            page.getByText('Successful message', { exact: true }),
          ).toBeVisible();
          if (failure === 'session switch')
            await page.getByRole('button', { name: /Recovery user 1/ }).click();
          else
            await page
              .getByRole('button', { name: 'Next', exact: true })
              .last()
              .click();
        }
      }
      await expect(page.getByRole('alert')).toBeVisible();
      await expect(
        page.getByText('No sessions found', { exact: true }),
      ).toHaveCount(0);
      if (failure === 'analysis') {
        await expect(page.getByRole('alert')).toContainText(/Tool/i);
        await expect(
          page.getByText('Successful message', { exact: true }),
        ).toBeVisible();
      } else {
        await expect(
          page.getByText('Successful message', { exact: true }),
        ).toHaveCount(0);
      }
      if (failure === 'list page')
        await expect(
          page.getByRole('button', { name: /Recovery user 0/ }),
        ).toHaveCount(0);
      failing = false;
      await page
        .getByRole('alert')
        .getByRole('button', { name: 'Retry', exact: true })
        .click();
      await expect(page.getByRole('alert')).toHaveCount(0);
      if (failure === 'initial list' || failure === 'list page') {
        await expect(
          page.getByRole('button', {
            name: failure === 'list page' ? /Page two 0/ : /Recovery user 0/,
          }),
        ).toBeVisible();
      } else {
        await expect(
          page.getByText(
            failure === 'session switch'
              ? 'Second session message'
              : failure === 'message page'
                ? 'Second page message'
                : 'Successful message',
            { exact: true },
          ),
        ).toBeVisible();
        await expect(
          page.getByText('recovered_tool', { exact: true }),
        ).toBeVisible();
      }
    });
  }
});

test.describe('bot session request races', () => {
  for (const kind of ['messages', 'analysis', 'sessions']) {
    for (const status of [200, 500]) {
      test(`ignores stale ${kind} ${status} after switching`, async ({
        page,
      }) => {
        await installLangBotApiMocks(page, { authenticated: true });
        let release!: () => void;
        const gate = new Promise<void>((resolve) => {
          release = resolve;
        });
        let held = false;
        let released = false;
        await page.route('**/api/v1/monitoring/**', async (route) => {
          const url = new URL(route.request().url());
          const list = url.pathname.endsWith('/sessions');
          const message = url.pathname.endsWith('/messages');
          const analysis = url.pathname.endsWith('/analysis');
          if (!list && !message && !analysis) return route.fallback();
          const old =
            kind === 'sessions'
              ? url.searchParams.get('userQuery') === 'old'
              : message
                ? url.searchParams.get('sessionId') === sessionId
                : url.pathname.includes(sessionId);
          const isHeld = old && url.pathname.endsWith(`/${kind}`);
          if (isHeld) {
            held = true;
            await gate;
            if (status === 500) {
              await route.fulfill({ status: 500, json: { code: 500 } });
              released = true;
              return;
            }
          }
          const data = list
            ? {
                sessions: [sessionId, 'person-new'].map((id, i) => ({
                  session_id: id,
                  bot_id: botId,
                  bot_name: botName,
                  pipeline_id: pipelineId,
                  pipeline_name: pipelineName,
                  message_count: 1,
                  start_time: at(0),
                  last_activity: at(4),
                  is_active: true,
                  user_name: isHeld ? 'Stale list' : `Race user ${i}`,
                })),
                total: 2,
              }
            : message
              ? {
                  messages: [
                    sessionMessage(
                      'race-message',
                      'user',
                      0,
                      old ? 'Old message' : 'Current message',
                    ),
                  ],
                  total: 1,
                }
              : {
                  tool_calls: [
                    toolCall(
                      'race-tool',
                      1,
                      old ? 'old_tool' : 'current_tool',
                      40,
                    ),
                  ],
                };
          await route.fulfill({ json: { code: 0, data } });
          if (isHeld) released = true;
        });
        await page.goto(`/home/bots?id=${botId}`);
        await page.getByRole('tab', { name: /Sessions/ }).click();
        if (kind === 'sessions') {
          await page
            .getByRole('textbox', { name: 'User ID or name' })
            .fill('old');
          await page
            .getByRole('textbox', { name: 'User ID or name' })
            .press('Enter');
        } else await page.getByRole('button', { name: /Race user 0/ }).click();
        await expect.poll(() => held).toBe(true);
        if (kind === 'sessions') {
          await page
            .getByRole('textbox', { name: 'User ID or name' })
            .fill('new');
          await page
            .getByRole('textbox', { name: 'User ID or name' })
            .press('Enter');
          await expect(
            page.getByRole('button', { name: /Race user 0/ }),
          ).toBeVisible();
        } else {
          await page.getByRole('button', { name: /Race user 1/ }).click();
          await expect(
            page.getByText('Current message', { exact: true }),
          ).toBeVisible();
        }
        release();
        await expect.poll(() => released).toBe(true);
        // Allow the released HTTP response and React's queued update to settle.
        await page.waitForTimeout(200);
        await expect(page.getByRole('alert')).toHaveCount(0);
        await expect(page.getByText('Stale list', { exact: true })).toHaveCount(
          0,
        );
        if (kind !== 'sessions') {
          await expect(
            page.getByText('Current message', { exact: true }),
          ).toBeVisible();
          await expect(
            page.getByText('current_tool', { exact: true }),
          ).toBeVisible();
          await expect(
            page.getByText('Old message', { exact: true }),
          ).toHaveCount(0);
          await expect(page.getByText('old_tool', { exact: true })).toHaveCount(
            0,
          );
        }
      });
    }
  }
});

test.describe('bot session monitor tool timeline', () => {
  test('isolates messages and analysis for two bots sharing a raw session id', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, { authenticated: true });
    const requests: Array<{ bot: string; path: string }> = [];
    await page.route('**/api/v1/monitoring/**', async (route) => {
      const url = new URL(route.request().url());
      const selectedBot = url.searchParams.get('botId');
      if (
        !url.pathname.endsWith('/sessions') &&
        !url.pathname.endsWith('/messages') &&
        !url.pathname.endsWith('/analysis')
      ) {
        return route.fallback();
      }
      expect(['bot-shared-a', 'bot-shared-b']).toContain(selectedBot);
      expect(route.request().headers().authorization).toBe(
        'Bearer playwright-token',
      );
      expect(route.request().headers()['x-workspace-id']).toBe(
        'workspace-playwright',
      );
      requests.push({ bot: selectedBot!, path: url.pathname });
      const shared = {
        session_id: sessionId,
        bot_id: selectedBot,
        bot_name: selectedBot,
        pipeline_id: pipelineId,
        pipeline_name: pipelineName,
        message_count: 1,
        start_time: at(0),
        last_activity: at(4),
        is_active: true,
        platform: 'person',
        user_id: 'shared-user',
        user_name: 'Shared User',
      };
      const data = url.pathname.endsWith('/sessions')
        ? { sessions: [shared], total: 1 }
        : url.pathname.endsWith('/messages')
          ? {
              messages: [
                {
                  ...sessionMessage(
                    'shared-message',
                    'user',
                    0,
                    `Message for ${selectedBot}`,
                  ),
                  bot_id: selectedBot,
                },
              ],
              total: 1,
            }
          : {
              session_id: sessionId,
              found: true,
              tool_calls: [
                {
                  ...toolCall('shared-tool', 1, `tool_${selectedBot}`, 40),
                  bot_id: selectedBot,
                },
              ],
            };
      if (url.pathname.endsWith('/messages'))
        expect(url.searchParams.get('sessionId')).toBe(sessionId);
      if (url.pathname.endsWith('/analysis'))
        expect(decodeURIComponent(url.pathname)).toContain(
          `/sessions/${sessionId}/analysis`,
        );
      await route.fulfill({ json: { code: 0, data } });
    });
    for (const selectedBot of ['bot-shared-a', 'bot-shared-b']) {
      await page.goto(`/home/bots?id=${selectedBot}`);
      await page.getByRole('tab', { name: /Sessions/ }).click();
      await page.getByRole('button', { name: /Shared User/ }).click();
      await expect(
        page.getByText(`Message for ${selectedBot}`, { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText(`tool_${selectedBot}`, { exact: true }),
      ).toBeVisible();
      const otherBot =
        selectedBot === 'bot-shared-a' ? 'bot-shared-b' : 'bot-shared-a';
      await expect(
        page.getByText(`Message for ${otherBot}`, { exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByText(`tool_${otherBot}`, { exact: true }),
      ).toHaveCount(0);
      expect(
        requests.some(
          (request) =>
            request.bot === selectedBot && request.path.endsWith('/messages'),
        ),
      ).toBe(true);
      expect(
        requests.some(
          (request) =>
            request.bot === selectedBot && request.path.endsWith('/analysis'),
        ),
      ).toBe(true);
    }
  });
  test('renders tool calls as left-side agent events interleaved with messages', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      monitoringSessions: [
        {
          session_id: sessionId,
          bot_id: botId,
          bot_name: botName,
          pipeline_id: pipelineId,
          pipeline_name: pipelineName,
          message_count: 3,
          start_time: at(0),
          last_activity: at(4),
          is_active: true,
          platform: 'person',
          user_id: 'timeline-user',
          user_name: 'Timeline User',
        },
      ],
      sessionMessages: {
        [sessionId]: [
          sessionMessage('user-message', 'user', 0, 'Need a timeline check'),
          sessionMessage(
            'assistant-step-1',
            'assistant',
            2,
            'Agent step 1: inspected repository files',
          ),
          sessionMessage(
            'assistant-step-2',
            'assistant',
            4,
            'Agent step 2: test suite finished',
          ),
        ],
      },
      sessionAnalyses: {
        [sessionId]: {
          session_id: sessionId,
          found: true,
          tool_calls: [
            toolCall('tool-repo-read', 1, 'repo_file_read', 80),
            toolCall('tool-test-run', 3, 'run_test_suite', 140),
          ],
        },
      },
    });

    const monitoringRequests: import('@playwright/test').Request[] = [];
    page.on('request', (request) => {
      if (request.url().includes('/api/v1/monitoring/'))
        monitoringRequests.push(request);
    });
    await page.goto(`/home/bots?id=${botId}`);
    await page.getByRole('tab', { name: /Sessions/ }).click();
    await page.getByRole('button', { name: /Timeline User/ }).click();

    await expect(page.getByText('Need a timeline check')).toBeVisible();
    await expect
      .poll(() =>
        monitoringRequests.some((request) =>
          request.url().includes('/analysis?'),
        ),
      )
      .toBe(true);
    for (const request of monitoringRequests.filter((request) =>
      /\/messages\?|\/analysis\?/.test(request.url()),
    )) {
      const url = new URL(request.url());
      expect(url.searchParams.get('botId')).toBe(botId);
      if (url.pathname.endsWith('/analysis')) {
        expect(url.searchParams.get('startTime')).toBe(at(0));
        expect(url.searchParams.get('endTime')).toBe(at(4));
      }
      expect(request.headers().authorization).toBe('Bearer playwright-token');
      expect(request.headers()['x-workspace-id']).toBe('workspace-playwright');
      if (url.pathname.endsWith('/messages'))
        expect(url.searchParams.get('sessionId')).toBe(sessionId);
      else
        expect(decodeURIComponent(url.pathname)).toContain(
          `/sessions/${sessionId}/analysis`,
        );
    }
    await expect(
      page.getByText('repo_file_read', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('Agent step 1: inspected repository files'),
    ).toBeVisible();
    await expect(
      page.getByText('run_test_suite', { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText('Agent step 2: test suite finished'),
    ).toBeVisible();
    await expect(page.getByText('{"target":"repo_file_read"}')).toHaveCount(0);
    await expect(page.getByText('{"ok":true}')).toHaveCount(0);

    await expect(
      page.locator('div.flex.justify-start').filter({
        hasText: 'repo_file_read',
      }),
    ).toHaveCount(1);
    await expect(
      page.locator('div.flex.justify-start').filter({
        hasText: 'run_test_suite',
      }),
    ).toHaveCount(1);
    await expect(
      page.locator('div.flex.justify-end').filter({
        hasText: 'repo_file_read',
      }),
    ).toHaveCount(0);
    await expect(
      page.locator('div.flex.justify-end').filter({
        hasText: 'run_test_suite',
      }),
    ).toHaveCount(0);

    const text = await page.locator('body').innerText();
    expect(text.indexOf('Need a timeline check')).toBeLessThan(
      text.indexOf('repo_file_read'),
    );
    expect(text.indexOf('repo_file_read')).toBeLessThan(
      text.indexOf('Agent step 1: inspected repository files'),
    );
    expect(
      text.indexOf('Agent step 1: inspected repository files'),
    ).toBeLessThan(text.indexOf('run_test_suite'));
    expect(text.indexOf('run_test_suite')).toBeLessThan(
      text.indexOf('Agent step 2: test suite finished'),
    );

    await page.getByText('repo_file_read', { exact: true }).click();
    await expect(page.getByText('{"target":"repo_file_read"}')).toBeVisible();
    await expect(page.getByText('{"ok":true}').first()).toBeVisible();
  });
});
