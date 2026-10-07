import type { ExecutionRow } from '@/app/infra/entities/api/monitoring-executions';

/**
 * The identity a recorded call carries: every call kind (model, tool) has a time,
 * a session and - when a Pipeline recorded it - the message it belongs to.
 */
export interface CallLinkSource {
  timestamp: Date;
  sessionId?: string | null;
  messageId?: string | null;
}

/** A record the dashboard can open for a recorded model or tool call. */
export type CallTarget =
  | { kind: 'execution'; row: ExecutionRow }
  | { kind: 'message'; id: string };

/** Calls are matched against a run's window; clock skew must not lose the link. */
const WINDOW_SLACK_MS = 2000;

function containsCall(row: ExecutionRow, callTime: number): boolean {
  if (row.started_at_ms == null) {
    return false;
  }
  const started = row.started_at_ms;
  if (callTime < started - WINDOW_SLACK_MS) {
    return false;
  }
  if (row.finished_at_ms == null) {
    // A run with no end time is still open: anything after its start belongs to it.
    return true;
  }
  return callTime <= row.finished_at_ms + WINDOW_SLACK_MS;
}

/**
 * The execution a recorded call ran inside.
 *
 * A Pipeline call names its message, which is the same id the execution list
 * uses for that query. An Agent call names nothing, so it is matched to the run
 * sharing its session whose window contains the call; the latest such start
 * wins, so a session with consecutive runs links to the run that was live.
 */
export function findCallExecution(
  call: CallLinkSource,
  executions: ExecutionRow[],
): ExecutionRow | null {
  if (executions.length === 0) {
    return null;
  }

  const messageId = call.messageId;
  if (messageId) {
    const direct = executions.find((row) => row.id === messageId);
    if (direct) {
      return direct;
    }
  }

  const sessionId = call.sessionId;
  const callTime = call.timestamp.getTime();
  let matched: ExecutionRow | null = null;
  for (const row of executions) {
    if (
      !sessionId ||
      row.session_id !== sessionId ||
      !containsCall(row, callTime)
    ) {
      continue;
    }
    if (
      matched == null ||
      (row.started_at_ms ?? 0) > (matched.started_at_ms ?? 0)
    ) {
      matched = row;
    }
  }
  return matched;
}

/**
 * Where a call's card jumps to: its execution record when the loaded list knows
 * it, else the pipeline message it names. An Agent call carries its run id, so
 * the message fallback applies only to ids the message list actually holds.
 */
export function resolveCallTarget(
  call: CallLinkSource,
  executions: ExecutionRow[],
  messageIds?: ReadonlySet<string>,
): CallTarget | null {
  const row = findCallExecution(call, executions);
  if (row) {
    return { kind: 'execution', row };
  }
  const messageId = call.messageId;
  if (messageId && messageIds?.has(messageId)) {
    return { kind: 'message', id: messageId };
  }
  return null;
}
