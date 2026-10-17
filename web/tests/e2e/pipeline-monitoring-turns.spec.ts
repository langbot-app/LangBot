import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';

const bot = {
  id: 'bot-pipeline-monitoring',
  name: 'Pipeline Bot',
};

const pipeline = {
  id: 'pipeline-monitoring',
  name: 'Pipeline Under Test',
};

function at(minute: number) {
  return `2026-07-02T10:${String(minute).padStart(2, '0')}:00Z`;
}

function message(
  id: string,
  role: 'user' | 'assistant',
  minute: number,
  content: string,
  sessionId = 'session-pipeline-agent',
) {
  return {
    id,
    timestamp: at(minute),
    bot_id: bot.id,
    bot_name: bot.name,
    pipeline_id: pipeline.id,
    pipeline_name: pipeline.name,
    message_content: content,
    session_id: sessionId,
    status: 'success',
    level: 'info',
    platform: role === 'user' ? 'person' : 'bot',
    user_id: 'pipeline-user',
    user_name: 'Pipeline User',
    runner_name: 'local-agent',
    variables: '{}',
    role,
  };
}

function llmCall(
  id: string,
  minute: number,
  messageId: string,
  input: number,
  output: number,
  duration: number,
) {
  return {
    id,
    timestamp: at(minute),
    model_name: 'gpt-5.5',
    input_tokens: input,
    output_tokens: output,
    total_tokens: input + output,
    duration,
    cost: 0,
    status: 'success',
    bot_id: bot.id,
    bot_name: bot.name,
    pipeline_id: pipeline.id,
    pipeline_name: pipeline.name,
    session_id: 'session-pipeline-agent',
    message_id: messageId,
  };
}

function toolCall(id: string, minute: number, messageId: string, name: string) {
  return {
    id,
    timestamp: at(minute),
    tool_name: name,
    tool_source: 'native',
    duration: 120,
    status: 'success',
    bot_id: bot.id,
    bot_name: bot.name,
    pipeline_id: pipeline.id,
    pipeline_name: pipeline.name,
    session_id: 'session-pipeline-agent',
    message_id: messageId,
    arguments: JSON.stringify({ query: name }),
    result: JSON.stringify({ ok: true }),
  };
}

function monitoringData() {
  const messages = [
    message(
      'single-user',
      'user',
      1,
      'Pipeline single user message without reply',
      'session-pipeline-single',
    ),
    message('agent-user', 'user', 10, 'Pipeline needs a deployment plan'),
    message(
      'agent-assistant-1',
      'assistant',
      11,
      'Pipeline agent step 1: inspect repository',
    ),
    message(
      'agent-assistant-2',
      'assistant',
      12,
      'Pipeline agent step 2: run tests',
    ),
    message(
      'agent-assistant-3',
      'assistant',
      13,
      'Pipeline final answer: deployment ready',
    ),
  ];
  const llmCalls = [
    llmCall('pipeline-call-1', 10, 'agent-user', 100, 40, 180),
    llmCall('pipeline-call-2', 11, 'agent-user', 140, 50, 220),
  ];
  const toolCalls = [
    toolCall('pipeline-tool-1', 11, 'agent-user', 'repo_search'),
    toolCall('pipeline-tool-2', 12, 'agent-user', 'run_tests'),
  ];

  return {
    overview: {
      total_messages: messages.length,
      llm_calls: llmCalls.length,
      embedding_calls: 0,
      model_calls: llmCalls.length,
      success_rate: 100,
      active_sessions: 2,
    },
    messages,
    llmCalls,
    toolCalls,
    embeddingCalls: [],
    sessions: [],
    errors: [],
    totalCount: {
      messages: messages.length,
      llmCalls: llmCalls.length,
      toolCalls: toolCalls.length,
      embeddingCalls: 0,
      sessions: 0,
      errors: 0,
    },
  };
}

test.describe('pipeline monitoring conversation turns', () => {
  test('uses conversation turns and folded tool calls in the pipeline dashboard', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      monitoringData: monitoringData(),
    });

    await page.goto(`/home/agents?id=${pipeline.id}`);
    await page.getByRole('tab', { name: 'Run logs' }).click();

    await expect(page.getByText('2 conversation turns')).toBeVisible();
    await expect(
      page.getByText('Pipeline single user message without reply'),
    ).toBeVisible();
    const agentTurn = page.getByRole('button', {
      name: /Pipeline Bot Success Pipeline needs a deployment plan/,
    });
    await agentTurn.click();
    const detail = page.getByRole('article');
    await expect(
      detail.getByText('Pipeline needs a deployment plan', { exact: true }),
    ).toBeVisible();
    for (const text of [
      'Pipeline agent step 1: inspect repository',
      'Pipeline agent step 2: run tests',
      'Pipeline final answer: deployment ready',
    ])
      await expect(detail.getByText(text, { exact: true })).toBeVisible();
    await expect(
      detail.getByText('Tool Calls 2', { exact: true }),
    ).toBeVisible();
    const search = detail
      .getByRole('listitem')
      .filter({ hasText: 'repo_search' });
    await expect(
      search.getByText('repo_search', { exact: true }),
    ).toBeVisible();
    await expect(detail.getByText('run_tests', { exact: true })).toBeVisible();
    await expect(search.getByText(/"query"/)).toHaveCount(0);
    await search
      .getByRole('button', { name: 'Arguments', exact: true })
      .click();
    await expect(search.getByText(/"query"/)).toBeVisible();
    await search.getByRole('button', { name: 'Result', exact: true }).click();
    await expect(search.getByText(/"ok"/)).toBeVisible();
  });
});
