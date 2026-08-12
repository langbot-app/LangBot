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

test.describe('bot session monitor tool timeline', () => {
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

    await page.goto(`/home/bots?id=${botId}`);
    await page.getByRole('tab', { name: /Sessions/ }).click();
    await page.getByRole('button', { name: /Timeline User/ }).click();

    await expect(page.getByText('Need a timeline check')).toBeVisible();
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
