import {
  MonitoringMessage,
  LLMCall,
  SessionInfo,
  ErrorLog,
  OverviewMetrics,
  FilterState,
  DateRange,
} from '../types/monitoring';

// Sample data for generating realistic mocks
const BOT_NAMES = [
  'Customer Service Bot',
  'Sales Assistant',
  'Technical Support',
  'Marketing Bot',
  'FAQ Bot',
];

const PIPELINE_NAMES = [
  'default',
  'customer-support',
  'sales-workflow',
  'tech-support-v2',
  'marketing-campaign',
];

const LLM_MODELS = [
  'gpt-4',
  'gpt-3.5-turbo',
  'claude-3-opus',
  'claude-3-sonnet',
  'gemini-pro',
];

const PLATFORMS = ['WeChat', 'Feishu', 'DingTalk', 'Telegram', 'Web'];

const ERROR_TYPES = [
  'NetworkError',
  'TimeoutError',
  'ValidationError',
  'RateLimitError',
  'ModelError',
];

const MESSAGE_TEMPLATES = [
  'Hello, how can I help you today?',
  'I understand your concern. Let me assist you with that.',
  'Thank you for your inquiry. Here is the information you requested.',
  'I apologize for the inconvenience. Let me look into this for you.',
  'Is there anything else I can help you with?',
  'Your request has been processed successfully.',
];

/**
 * Generate random ID
 */
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Generate random timestamp within date range
 */
function generateTimestamp(range: DateRange | null): Date {
  if (!range) {
    // Default to last 24 hours
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    range = { from: yesterday, to: now };
  }

  const from = range.from.getTime();
  const to = range.to.getTime();
  const timestamp = from + Math.random() * (to - from);
  return new Date(timestamp);
}

/**
 * Generate mock monitoring messages
 */
export function generateMockMessages(
  count: number,
  filters?: Partial<FilterState>,
): MonitoringMessage[] {
  const messages: MonitoringMessage[] = [];
  const dateRange = filters?.customDateRange || null;

  for (let i = 0; i < count; i++) {
    const botId = `bot-${Math.floor(Math.random() * BOT_NAMES.length)}`;
    const botName = BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)];
    const pipelineId = `pipeline-${Math.floor(Math.random() * PIPELINE_NAMES.length)}`;
    const pipelineName =
      PIPELINE_NAMES[Math.floor(Math.random() * PIPELINE_NAMES.length)];

    // Apply bot filter
    if (filters?.selectedBots && filters.selectedBots.length > 0) {
      if (!filters.selectedBots.includes(botId)) continue;
    }

    // Apply pipeline filter
    if (filters?.selectedPipelines && filters.selectedPipelines.length > 0) {
      if (!filters.selectedPipelines.includes(pipelineId)) continue;
    }

    const timestamp = generateTimestamp(dateRange);
    const statuses: ('success' | 'error' | 'pending')[] = [
      'success',
      'success',
      'success',
      'error',
      'pending',
    ];
    const levels: ('info' | 'warning' | 'error' | 'debug')[] = [
      'info',
      'info',
      'warning',
      'error',
      'debug',
    ];

    messages.push({
      id: generateId(),
      timestamp,
      botId,
      botName,
      pipelineId,
      pipelineName,
      messageContent:
        MESSAGE_TEMPLATES[Math.floor(Math.random() * MESSAGE_TEMPLATES.length)],
      sessionId: `session-${Math.floor(Math.random() * 100)}`,
      status: statuses[Math.floor(Math.random() * statuses.length)],
      level: levels[Math.floor(Math.random() * levels.length)],
      platform: PLATFORMS[Math.floor(Math.random() * PLATFORMS.length)],
      userId: `user-${Math.floor(Math.random() * 1000)}`,
    });
  }

  return messages.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
}

/**
 * Generate mock LLM calls
 */
export function generateMockLLMCalls(
  count: number,
  filters?: Partial<FilterState>,
): LLMCall[] {
  const calls: LLMCall[] = [];
  const dateRange = filters?.customDateRange || null;

  for (let i = 0; i < count; i++) {
    const botId = `bot-${Math.floor(Math.random() * BOT_NAMES.length)}`;
    const botName = BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)];
    const pipelineId = `pipeline-${Math.floor(Math.random() * PIPELINE_NAMES.length)}`;
    const pipelineName =
      PIPELINE_NAMES[Math.floor(Math.random() * PIPELINE_NAMES.length)];

    if (filters?.selectedBots && filters.selectedBots.length > 0) {
      if (!filters.selectedBots.includes(botId)) continue;
    }

    if (filters?.selectedPipelines && filters.selectedPipelines.length > 0) {
      if (!filters.selectedPipelines.includes(pipelineId)) continue;
    }

    const timestamp = generateTimestamp(dateRange);
    const inputTokens = Math.floor(Math.random() * 1000) + 100;
    const outputTokens = Math.floor(Math.random() * 500) + 50;
    const status = Math.random() > 0.1 ? 'success' : 'error';

    calls.push({
      id: generateId(),
      timestamp,
      modelName: LLM_MODELS[Math.floor(Math.random() * LLM_MODELS.length)],
      tokens: {
        input: inputTokens,
        output: outputTokens,
        total: inputTokens + outputTokens,
      },
      duration: Math.floor(Math.random() * 5000) + 500,
      cost:
        (inputTokens * 0.00001 + outputTokens * 0.00003) *
        (Math.random() * 0.5 + 0.75),
      status,
      botId,
      botName,
      pipelineId,
      pipelineName,
      errorMessage: status === 'error' ? 'Rate limit exceeded' : undefined,
    });
  }

  return calls.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
}

/**
 * Generate mock sessions
 */
export function generateMockSessions(
  count: number,
  filters?: Partial<FilterState>,
): SessionInfo[] {
  const sessions: SessionInfo[] = [];
  const dateRange = filters?.customDateRange || null;

  for (let i = 0; i < count; i++) {
    const botId = `bot-${Math.floor(Math.random() * BOT_NAMES.length)}`;
    const botName = BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)];
    const pipelineId = `pipeline-${Math.floor(Math.random() * PIPELINE_NAMES.length)}`;
    const pipelineName =
      PIPELINE_NAMES[Math.floor(Math.random() * PIPELINE_NAMES.length)];

    if (filters?.selectedBots && filters.selectedBots.length > 0) {
      if (!filters.selectedBots.includes(botId)) continue;
    }

    if (filters?.selectedPipelines && filters.selectedPipelines.length > 0) {
      if (!filters.selectedPipelines.includes(pipelineId)) continue;
    }

    const startTime = generateTimestamp(dateRange);
    const duration = Math.floor(Math.random() * 3600) + 60;
    const lastActivity = new Date(startTime.getTime() + duration * 1000);

    sessions.push({
      sessionId: `session-${i}`,
      botId,
      botName,
      pipelineId,
      pipelineName,
      messageCount: Math.floor(Math.random() * 50) + 1,
      duration,
      lastActivity,
      startTime,
      platform: PLATFORMS[Math.floor(Math.random() * PLATFORMS.length)],
      userId: `user-${Math.floor(Math.random() * 1000)}`,
    });
  }

  return sessions.sort(
    (a, b) => b.lastActivity.getTime() - a.lastActivity.getTime(),
  );
}

/**
 * Generate mock errors
 */
export function generateMockErrors(
  count: number,
  filters?: Partial<FilterState>,
): ErrorLog[] {
  const errors: ErrorLog[] = [];
  const dateRange = filters?.customDateRange || null;

  for (let i = 0; i < count; i++) {
    const botId = `bot-${Math.floor(Math.random() * BOT_NAMES.length)}`;
    const botName = BOT_NAMES[Math.floor(Math.random() * BOT_NAMES.length)];
    const pipelineId = `pipeline-${Math.floor(Math.random() * PIPELINE_NAMES.length)}`;
    const pipelineName =
      PIPELINE_NAMES[Math.floor(Math.random() * PIPELINE_NAMES.length)];

    if (filters?.selectedBots && filters.selectedBots.length > 0) {
      if (!filters.selectedBots.includes(botId)) continue;
    }

    if (filters?.selectedPipelines && filters.selectedPipelines.length > 0) {
      if (!filters.selectedPipelines.includes(pipelineId)) continue;
    }

    const timestamp = generateTimestamp(dateRange);
    const errorType =
      ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];

    errors.push({
      id: generateId(),
      timestamp,
      errorType,
      errorMessage: `An error occurred in ${errorType}: ${Math.random().toString(36).substr(2, 9)}`,
      botId,
      botName,
      pipelineId,
      pipelineName,
      sessionId:
        Math.random() > 0.5
          ? `session-${Math.floor(Math.random() * 100)}`
          : undefined,
      stackTrace: Math.random() > 0.7 ? 'Stack trace...' : undefined,
    });
  }

  return errors.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
}

/**
 * Generate mock overview metrics
 */
export function generateMockMetrics(): OverviewMetrics {
  const totalMessages = Math.floor(Math.random() * 10000) + 1000;
  const llmCalls = Math.floor(Math.random() * 5000) + 500;
  const successRate = Math.floor(Math.random() * 20) + 80;
  const activeSessions = Math.floor(Math.random() * 100) + 10;

  return {
    totalMessages,
    llmCalls,
    successRate,
    activeSessions,
    trends: {
      messages: Math.floor(Math.random() * 40) - 20,
      llmCalls: Math.floor(Math.random() * 40) - 20,
      successRate: Math.floor(Math.random() * 10) - 5,
      sessions: Math.floor(Math.random() * 20) - 10,
    },
  };
}

/**
 * Generate all mock data at once
 */
export function generateAllMockData(filters?: Partial<FilterState>) {
  return {
    overview: generateMockMetrics(filters),
    messages: generateMockMessages(50, filters),
    llmCalls: generateMockLLMCalls(30, filters),
    sessions: generateMockSessions(20, filters),
    errors: generateMockErrors(15, filters),
    totalCount: {
      messages: 500,
      llmCalls: 300,
      sessions: 80,
      errors: 45,
    },
  };
}
