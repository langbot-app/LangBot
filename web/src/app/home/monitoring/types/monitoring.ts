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
}

export interface OverviewMetrics {
  totalMessages: number;
  llmCalls: number;
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
  sessions: SessionInfo[];
  errors: ErrorLog[];
  totalCount: {
    messages: number;
    llmCalls: number;
    sessions: number;
    errors: number;
  };
}
