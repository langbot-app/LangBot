import { expect, test } from '@playwright/test';

import { installLangBotApiMocks } from './fixtures/langbot-api';
import { buildConversationTurns } from '../../src/app/home/monitoring/utils/conversationTurns';
import {
  ErrorLog,
  LLMCall,
  MonitoringMessage,
  ToolCall,
} from '../../src/app/home/monitoring/types/monitoring';

const bot = {
  id: 'bot-monitoring',
  name: 'Monitoring Bot',
};

const pipeline = {
  id: 'pipeline-monitoring',
  name: 'Monitoring Pipeline',
};

function time(minute: number) {
  return new Date(`2026-07-02T10:${String(minute).padStart(2, '0')}:00Z`);
}

function message(
  id: string,
  role: 'user' | 'assistant',
  minute: number,
  content: string,
  sessionId = 'session-agent',
): MonitoringMessage {
  return {
    id,
    timestamp: time(minute),
    botId: bot.id,
    botName: bot.name,
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    messageContent: content,
    sessionId,
    status: 'success',
    level: 'info',
    platform: role === 'user' ? 'person' : 'bot',
    userId: 'user-1',
    userName: 'Playwright User',
    runnerName: 'local-agent',
    variables: '{}',
    role,
  };
}

function llmCall(
  id: string,
  minute: number,
  messageId: string | undefined,
  input: number,
  output: number,
  duration: number,
  sessionId = 'session-agent',
): LLMCall {
  return {
    id,
    timestamp: time(minute),
    modelName: 'gpt-5.5',
    tokens: {
      input,
      output,
      total: input + output,
    },
    duration,
    status: 'success',
    botId: bot.id,
    botName: bot.name,
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    sessionId,
    messageId,
  };
}

function errorLog(id: string, minute: number, messageId: string): ErrorLog {
  return {
    id,
    timestamp: time(minute),
    errorType: 'ToolExecutionError',
    errorMessage: 'Tool retry failed',
    botId: bot.id,
    botName: bot.name,
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    sessionId: 'session-agent',
    messageId,
  };
}

function toolCall(
  id: string,
  minute: number,
  messageId: string | undefined,
  toolName: string,
  duration: number,
  sessionId = 'session-agent',
  status: 'success' | 'error' = 'success',
): ToolCall {
  return {
    id,
    timestamp: time(minute),
    toolName,
    toolSource: 'native',
    duration,
    status,
    botId: bot.id,
    botName: bot.name,
    pipelineId: pipeline.id,
    pipelineName: pipeline.name,
    sessionId,
    messageId,
    arguments: JSON.stringify({ query: toolName }),
    result: status === 'success' ? JSON.stringify({ ok: true }) : undefined,
    errorMessage: status === 'error' ? 'Tool failed' : undefined,
  };
}

function rawMessage(message: MonitoringMessage) {
  return {
    id: message.id,
    timestamp: message.timestamp.toISOString(),
    bot_id: message.botId,
    bot_name: message.botName,
    pipeline_id: message.pipelineId,
    pipeline_name: message.pipelineName,
    message_content: message.messageContent,
    session_id: message.sessionId,
    status: message.status,
    level: message.level,
    platform: message.platform,
    user_id: message.userId,
    user_name: message.userName,
    runner_name: message.runnerName,
    variables: message.variables,
    role: message.role,
  };
}

function rawLlmCall(call: LLMCall) {
  return {
    id: call.id,
    timestamp: call.timestamp.toISOString(),
    model_name: call.modelName,
    input_tokens: call.tokens.input,
    output_tokens: call.tokens.output,
    total_tokens: call.tokens.total,
    duration: call.duration,
    cost: call.cost,
    status: call.status,
    bot_id: call.botId,
    bot_name: call.botName,
    pipeline_id: call.pipelineId,
    pipeline_name: call.pipelineName,
    session_id: call.sessionId,
    error_message: call.errorMessage,
    message_id: call.messageId,
  };
}

function rawError(error: ErrorLog) {
  return {
    id: error.id,
    timestamp: error.timestamp.toISOString(),
    error_type: error.errorType,
    error_message: error.errorMessage,
    bot_id: error.botId,
    bot_name: error.botName,
    pipeline_id: error.pipelineId,
    pipeline_name: error.pipelineName,
    session_id: error.sessionId,
    stack_trace: error.stackTrace,
    message_id: error.messageId,
  };
}

function rawToolCall(call: ToolCall) {
  return {
    id: call.id,
    timestamp: call.timestamp.toISOString(),
    tool_name: call.toolName,
    tool_source: call.toolSource,
    duration: call.duration,
    status: call.status,
    bot_id: call.botId,
    bot_name: call.botName,
    pipeline_id: call.pipelineId,
    pipeline_name: call.pipelineName,
    session_id: call.sessionId,
    message_id: call.messageId,
    arguments: call.arguments,
    result: call.result,
    error_message: call.errorMessage,
  };
}

function monitoringScenario() {
  const messages = [
    message(
      'single-user',
      'user',
      1,
      'Standalone question with no reply',
      'session-single',
    ),
    message('agent-user-1', 'user', 10, 'Need deployment plan'),
    message('agent-assistant-1', 'assistant', 11, 'Agent step 1: inspect repo'),
    message('agent-assistant-2', 'assistant', 12, 'Agent step 2: run tests'),
    message(
      'agent-assistant-3',
      'assistant',
      13,
      'Final answer: deployment plan ready',
    ),
    message('agent-user-2', 'user', 20, 'Continue with rollback plan'),
    message('agent-assistant-4', 'assistant', 21, 'Rollback plan ready'),
  ];
  const llmCalls = [
    llmCall('agent-call-1', 10, 'agent-user-1', 100, 40, 120),
    llmCall('agent-call-2', 11, 'agent-user-1', 200, 60, 220),
    llmCall('agent-call-3', 12, 'agent-user-1', 300, 90, 260),
    llmCall('agent-call-4', 20, 'agent-user-2', 50, 25, 80),
  ];
  const errors = [errorLog('agent-error-1', 12, 'agent-user-1')];
  const toolCalls = [
    toolCall('agent-tool-1', 11, 'agent-user-1', 'repo_search', 90),
    toolCall('agent-tool-2', 12, 'agent-user-1', 'run_tests', 150),
    toolCall('agent-tool-3', 20, 'agent-user-2', 'rollback_lookup', 70),
  ];

  return {
    messages,
    llmCalls,
    toolCalls,
    errors,
  };
}

function rawMonitoringData() {
  const scenario = monitoringScenario();

  return {
    overview: {
      total_messages: scenario.messages.length,
      llm_calls: scenario.llmCalls.length,
      embedding_calls: 0,
      model_calls: scenario.llmCalls.length,
      success_rate: 100,
      active_sessions: 2,
    },
    messages: scenario.messages.map(rawMessage),
    llmCalls: scenario.llmCalls.map(rawLlmCall),
    toolCalls: scenario.toolCalls.map(rawToolCall),
    embeddingCalls: [],
    sessions: [],
    errors: scenario.errors.map(rawError),
    totalCount: {
      messages: scenario.messages.length,
      llmCalls: scenario.llmCalls.length,
      toolCalls: scenario.toolCalls.length,
      embeddingCalls: 0,
      sessions: 0,
      errors: scenario.errors.length,
    },
  };
}

test.describe('monitoring conversation turn grouping', () => {
  test('keeps a single user message as one observable turn', () => {
    const userOnly = message(
      'single-user-only',
      'user',
      1,
      'No answer yet',
      'session-user-only',
    );

    const turns = buildConversationTurns([userOnly], [], []);

    expect(turns).toHaveLength(1);
    expect(turns[0].id).toBe(userOnly.id);
    expect(turns[0].userMessage?.messageContent).toBe('No answer yet');
    expect(turns[0].assistantMessages).toHaveLength(0);
    expect(turns[0].llmCalls).toHaveLength(0);
    expect(turns[0].totalTokens).toBe(0);
  });

  test('groups multi-step agent execution and multiple replies into one user turn', () => {
    const scenario = monitoringScenario();
    const turns = buildConversationTurns(
      scenario.messages,
      scenario.llmCalls,
      scenario.errors,
      scenario.toolCalls,
    );

    const agentTurn = turns.find((turn) => turn.id === 'agent-user-1');

    expect(agentTurn).toBeTruthy();
    expect(agentTurn?.userMessage?.messageContent).toBe('Need deployment plan');
    expect(
      agentTurn?.assistantMessages.map((item) => item.messageContent),
    ).toEqual([
      'Agent step 1: inspect repo',
      'Agent step 2: run tests',
      'Final answer: deployment plan ready',
    ]);
    expect(agentTurn?.llmCalls).toHaveLength(3);
    expect(agentTurn?.toolCalls).toHaveLength(2);
    expect(agentTurn?.errors).toHaveLength(1);
    expect(agentTurn?.totalTokens).toBe(790);
    expect(agentTurn?.totalDuration).toBe(600);
    expect(agentTurn?.totalToolDuration).toBe(240);
  });

  test('starts a new turn for each later user message in the same session', () => {
    const firstUser = message('same-session-user-1', 'user', 1, 'First');
    const firstReply = message(
      'same-session-reply-1',
      'assistant',
      2,
      'First reply',
    );
    const secondUser = message('same-session-user-2', 'user', 3, 'Second');
    const secondReply = message(
      'same-session-reply-2',
      'assistant',
      4,
      'Second reply',
    );

    const turns = buildConversationTurns(
      [firstUser, firstReply, secondUser, secondReply],
      [
        llmCall('same-session-call-1', 1, firstUser.id, 10, 5, 40),
        llmCall('same-session-call-2', 3, secondUser.id, 20, 10, 50),
      ],
      [],
    );

    expect(turns.map((turn) => turn.id)).toEqual([
      'same-session-user-2',
      'same-session-user-1',
    ]);
    expect(
      turns[0].assistantMessages.map((item) => item.messageContent),
    ).toEqual(['Second reply']);
    expect(
      turns[1].assistantMessages.map((item) => item.messageContent),
    ).toEqual(['First reply']);
  });

  test('attaches calls without message ids by session time', () => {
    const user = message('fallback-user', 'user', 1, 'Use session fallback');
    const assistant = message(
      'fallback-assistant',
      'assistant',
      2,
      'Fallback reply',
    );
    const call = llmCall('fallback-call', 2, undefined, 25, 5, 70);

    const turns = buildConversationTurns([user, assistant], [call], []);

    expect(turns).toHaveLength(1);
    expect(turns[0].llmCalls).toHaveLength(1);
    expect(turns[0].llmCalls[0].id).toBe(call.id);
    expect(turns[0].totalTokens).toBe(30);
  });

  test('attaches tool calls without message ids by session time', () => {
    const user = message('tool-fallback-user', 'user', 1, 'Use tool fallback');
    const assistant = message(
      'tool-fallback-assistant',
      'assistant',
      2,
      'Tool fallback reply',
    );
    const call = toolCall(
      'tool-fallback-call',
      2,
      undefined,
      'memory_lookup',
      45,
    );

    const turns = buildConversationTurns([user, assistant], [], [], [call]);

    expect(turns).toHaveLength(1);
    expect(turns[0].toolCalls).toHaveLength(1);
    expect(turns[0].toolCalls[0].id).toBe(call.id);
    expect(turns[0].totalToolDuration).toBe(45);
  });

  test('renders user-only, multi-agent, and multi-turn cases in the monitoring page', async ({
    page,
  }) => {
    await installLangBotApiMocks(page, {
      authenticated: true,
      monitoringData: rawMonitoringData(),
    });

    await page.goto('/home/monitoring');

    await expect(page.getByText('3 conversation turns')).toBeVisible();
    await expect(
      page.getByText('Standalone question with no reply'),
    ).toBeVisible();
    await expect(page.getByText('No assistant reply recorded')).toBeVisible();
    await expect(page.getByText('Need deployment plan')).toBeVisible();
    await expect(page.getByText('Agent step 1: inspect repo')).toBeVisible();
    await expect(page.getByText('Assistant +2')).toBeVisible();
    await expect(page.getByText('3 LLM')).toBeVisible();
    await expect(page.getByText('2 tools')).toBeVisible();
    await expect(page.getByText('790 tokens')).toBeVisible();
    await expect(page.getByText('1 errors')).toBeVisible();
    await expect(page.getByText('Continue with rollback plan')).toBeVisible();
    await expect(page.getByText('Rollback plan ready')).toBeVisible();

    const agentTurn = page
      .locator('div[role="button"]')
      .filter({ hasText: 'Need deployment plan' });
    await expect(agentTurn).toHaveCount(1);
    await agentTurn.click();

    await expect(page.getByText('Conversation Trace')).toBeVisible();
    await expect(page.getByText('Agent step 2: run tests')).toBeVisible();
    await expect(
      page.getByText('Final answer: deployment plan ready'),
    ).toBeVisible();
    await expect(page.getByText('LLM Calls (3)')).toBeVisible();
    await expect(page.getByText('#3 gpt-5.5')).toBeVisible();
    await expect(page.getByText('In: 300')).toBeVisible();
    await expect(page.getByText('Out: 90')).toBeVisible();
    await expect(page.getByText('Total: 390')).toBeVisible();
    await expect(page.getByText('Tool Calls (2)')).toBeVisible();
    await expect(page.getByText('#1 repo_search')).toBeVisible();
    await expect(page.getByText('#2 run_tests')).toBeVisible();
    await expect(page.getByText('Arguments')).toHaveCount(0);
    await expect(page.getByText('Result')).toHaveCount(0);

    await page.getByText('#1 repo_search').click();
    await expect(page.getByText('Arguments').first()).toBeVisible();
    await expect(page.getByText('Result').first()).toBeVisible();
    await expect(page.getByText('Tool retry failed')).toBeVisible();
  });
});
