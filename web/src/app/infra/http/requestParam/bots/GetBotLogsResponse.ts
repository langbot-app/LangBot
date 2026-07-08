export interface GetBotLogsResponse {
  logs: BotLog[];
  total_count: number;
}

export interface BotLog {
  images: [];
  level: string;
  message_session_id: string;
  seq_id: number;
  text: string;
  timestamp: number;
}
