export interface GetBotLogsResponse {
  logs: BotLog[];
  total_count: number;
}

export interface BotLog {
  images: string[];
  level: string;
  message_session_id: string;
  metadata?: Record<string, unknown> | null;
  seq_id: number;
  text: string;
  timestamp: number;
}
