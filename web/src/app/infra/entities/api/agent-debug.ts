export interface DebugExecutionEvent {
  type: string;
  data: Record<string, any>;
  sequence?: number;
  timestamp?: number;
  run_id?: string;
}
