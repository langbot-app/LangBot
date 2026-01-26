export interface MonitoringMessage {
  id: string;
  timestamp: Date;
  botId: string;
  botName: string;
  pipelineId: string;
  pipelineName: string;
  messageContent: string;
  sessionId: string;
  status: 'success' | 'error' | 'pending';
  level: 'info' | 'warning' | 'error' | 'debug';
  platform?: string;
  userId?: string;
  runnerName?: string;
  variables?: string;
}

export interface LLMCall {
  id: string;
  timestamp: Date;
  modelName: string;
  tokens: {
    input: number;
    output: number;
    total: number;
  };
  duration: number;
  cost?: number;
  status: 'success' | 'error';
  botId: string;
  botName: string;
  pipelineId: string;
  pipelineName: string;
  errorMessage?: string;
  messageId?: string;
}

export interface EmbeddingCall {
  id: string;
  timestamp: Date;
  modelName: string;
  promptTokens: number;
  totalTokens: number;
  duration: number;
  inputCount: number;
  status: 'success' | 'error';
  errorMessage?: string;
  knowledgeBaseId?: string;
  queryText?: string;
  sessionId?: string;
  messageId?: string;
  callType?: 'embedding' | 'retrieve';
}

// Unified model call type for displaying LLM and Embedding calls together
export interface ModelCall {
  id: string;
  timestamp: Date;
  modelName: string;
  modelType: 'llm' | 'embedding';
  status: 'success' | 'error';
  duration: number;
  errorMessage?: string;
  messageId?: string;
  // LLM specific fields
  tokens?: {
    input: number;
    output: number;
    total: number;
  };
  cost?: number;
  botId?: string;
  botName?: string;
  pipelineId?: string;
  pipelineName?: string;
  // Embedding specific fields
  callType?: 'embedding' | 'retrieve';
  promptTokens?: number;
  totalTokens?: number;
  inputCount?: number;
  knowledgeBaseId?: string;
  queryText?: string;
  sessionId?: string;
}

export interface SessionInfo {
  sessionId: string;
  botId: string;
  botName: string;
  pipelineId: string;
  pipelineName: string;
  messageCount: number;
  duration: number;
  lastActivity: Date;
  startTime: Date;
  platform?: string;
  userId?: string;
}

export interface ErrorLog {
  id: string;
  timestamp: Date;
  errorType: string;
  errorMessage: string;
  botId: string;
  botName: string;
  pipelineId: string;
  pipelineName: string;
  sessionId?: string;
  stackTrace?: string;
  messageId?: string;
}

export interface MessageDetails {
  messageId: string;
  found: boolean;
  message?: MonitoringMessage;
  llmCalls: LLMCall[];
  llmStats: {
    totalCalls: number;
    totalInputTokens: number;
    totalOutputTokens: number;
    totalTokens: number;
    totalDurationMs: number;
    averageDurationMs: number;
  };
  errors: ErrorLog[];
}

export interface OverviewMetrics {
  totalMessages: number;
  llmCalls: number;
  embeddingCalls: number;
  modelCalls: number;
  successRate: number;
  activeSessions: number;
  trends?: {
    messages: number;
    llmCalls: number;
    successRate: number;
    sessions: number;
  };
}

export interface FilterState {
  selectedBots: string[];
  selectedPipelines: string[];
  timeRange: TimeRangeOption;
  customDateRange: DateRange | null;
}

export type TimeRangeOption =
  | 'lastHour'
  | 'last6Hours'
  | 'last24Hours'
  | 'last7Days'
  | 'last30Days'
  | 'custom';

export interface DateRange {
  from: Date;
  to: Date;
}

export interface MonitoringData {
  overview: OverviewMetrics;
  messages: MonitoringMessage[];
  llmCalls: LLMCall[];
  embeddingCalls: EmbeddingCall[];
  modelCalls: ModelCall[];
  sessions: SessionInfo[];
  errors: ErrorLog[];
  totalCount: {
    messages: number;
    llmCalls: number;
    embeddingCalls: number;
    sessions: number;
    errors: number;
  };
}
