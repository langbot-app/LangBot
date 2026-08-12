import {
  ErrorLog,
  LLMCall,
  MonitoringMessage,
  ToolCall,
} from '../types/monitoring';

type MessageRole = 'user' | 'assistant' | 'unknown';

export interface ConversationTurn {
  id: string;
  sessionId: string;
  startedAt: Date;
  lastActivityAt: Date;
  botId: string;
  botName: string;
  pipelineId: string;
  pipelineName: string;
  runnerName?: string;
  platform?: string;
  userId?: string;
  userName?: string;
  userMessage?: MonitoringMessage;
  assistantMessages: MonitoringMessage[];
  messages: MonitoringMessage[];
  llmCalls: LLMCall[];
  toolCalls: ToolCall[];
  errors: ErrorLog[];
  status: 'success' | 'error' | 'pending';
  level: 'info' | 'warning' | 'error' | 'debug';
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  totalDuration: number;
  totalToolDuration: number;
}

function normalizeRole(
  message: MonitoringMessage,
  llmMessageIds: Set<string>,
): MessageRole {
  const role = message.role?.toLowerCase();

  if (role === 'user' || role === 'assistant') {
    return role;
  }

  if (llmMessageIds.has(message.id)) {
    return 'user';
  }

  return 'unknown';
}

export function hasRenderableMessageContent(content?: string): boolean {
  const trimmed = content?.trim();

  if (!trimmed || trimmed === '[]' || trimmed === '""') {
    return false;
  }

  try {
    const parsed = JSON.parse(trimmed);

    if (typeof parsed === 'string') {
      return parsed.trim().length > 0;
    }

    if (Array.isArray(parsed)) {
      return parsed.some(
        (component) =>
          typeof component !== 'object' ||
          component === null ||
          component.type !== 'Source',
      );
    }
  } catch {
    return true;
  }

  return true;
}

function createTurn(message: MonitoringMessage): ConversationTurn {
  return {
    id: message.id,
    sessionId: message.sessionId,
    startedAt: message.timestamp,
    lastActivityAt: message.timestamp,
    botId: message.botId,
    botName: message.botName,
    pipelineId: message.pipelineId,
    pipelineName: message.pipelineName,
    runnerName: message.runnerName,
    platform: message.platform,
    userId: message.userId,
    userName: message.userName,
    assistantMessages: [],
    messages: [],
    llmCalls: [],
    toolCalls: [],
    errors: [],
    status: message.status,
    level: message.level,
    inputTokens: 0,
    outputTokens: 0,
    totalTokens: 0,
    totalDuration: 0,
    totalToolDuration: 0,
  };
}

function updateTurnActivity(turn: ConversationTurn, timestamp: Date) {
  if (timestamp.getTime() > turn.lastActivityAt.getTime()) {
    turn.lastActivityAt = timestamp;
  }
}

function addMessageToTurn(
  turn: ConversationTurn,
  message: MonitoringMessage,
  role: MessageRole,
) {
  turn.messages.push(message);
  updateTurnActivity(turn, message.timestamp);

  if (message.level === 'error') {
    turn.level = 'error';
  } else if (message.level === 'warning' && turn.level !== 'error') {
    turn.level = 'warning';
  }

  if (message.status === 'error') {
    turn.status = 'error';
  } else if (message.status === 'pending' && turn.status !== 'error') {
    turn.status = 'pending';
  }

  if (role === 'assistant') {
    turn.assistantMessages.push(message);
    return;
  }

  if (!turn.userMessage) {
    turn.userMessage = message;
    turn.userId = message.userId ?? turn.userId;
    turn.userName = message.userName ?? turn.userName;
    return;
  }

  turn.assistantMessages.push(message);
}

function findTurnBySessionTime(
  sessionTurns: Map<string, ConversationTurn[]>,
  sessionId: string | undefined,
  timestamp: Date,
): ConversationTurn | undefined {
  if (!sessionId) {
    return undefined;
  }

  const turns = sessionTurns.get(sessionId);
  if (!turns?.length) {
    return undefined;
  }

  let nearest = turns[0];
  const targetTime = timestamp.getTime();

  for (const turn of turns) {
    if (turn.startedAt.getTime() <= targetTime) {
      nearest = turn;
    } else {
      break;
    }
  }

  return nearest;
}

export function buildConversationTurns(
  messages: MonitoringMessage[],
  llmCalls: LLMCall[],
  errors: ErrorLog[],
  toolCalls: ToolCall[] = [],
): ConversationTurn[] {
  const activityMessageIds = new Set([
    ...llmCalls
      .map((call) => call.messageId)
      .filter((messageId): messageId is string => Boolean(messageId)),
    ...toolCalls
      .map((call) => call.messageId)
      .filter((messageId): messageId is string => Boolean(messageId)),
  ]);
  const visibleMessages = messages
    .filter((message) => hasRenderableMessageContent(message.messageContent))
    .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const sessionTurns = new Map<string, ConversationTurn[]>();
  const lastTurnBySession = new Map<string, ConversationTurn>();
  const messageIdToTurn = new Map<string, ConversationTurn>();

  for (const message of visibleMessages) {
    const role = normalizeRole(message, activityMessageIds);
    const previousTurn = lastTurnBySession.get(message.sessionId);
    const shouldStartTurn = role === 'user' || !previousTurn;
    const turn = shouldStartTurn ? createTurn(message) : previousTurn;

    if (shouldStartTurn) {
      const turns = sessionTurns.get(message.sessionId) ?? [];
      turns.push(turn);
      sessionTurns.set(message.sessionId, turns);
      lastTurnBySession.set(message.sessionId, turn);
    }

    addMessageToTurn(turn, message, role);
    messageIdToTurn.set(message.id, turn);
  }

  const allTurns = Array.from(sessionTurns.values()).flat();

  for (const call of llmCalls) {
    const turn =
      (call.messageId ? messageIdToTurn.get(call.messageId) : undefined) ??
      findTurnBySessionTime(sessionTurns, call.sessionId, call.timestamp);

    if (!turn) {
      continue;
    }

    turn.llmCalls.push(call);
    turn.inputTokens += call.tokens.input;
    turn.outputTokens += call.tokens.output;
    turn.totalTokens += call.tokens.total;
    turn.totalDuration += call.duration;
    updateTurnActivity(turn, call.timestamp);

    if (call.status === 'error') {
      turn.status = 'error';
      turn.level = 'error';
    }
  }

  for (const call of toolCalls) {
    const turn =
      (call.messageId ? messageIdToTurn.get(call.messageId) : undefined) ??
      findTurnBySessionTime(sessionTurns, call.sessionId, call.timestamp);

    if (!turn) {
      continue;
    }

    turn.toolCalls.push(call);
    turn.totalToolDuration += call.duration;
    updateTurnActivity(turn, call.timestamp);

    if (call.status === 'error') {
      turn.status = 'error';
      turn.level = 'error';
    }
  }

  for (const error of errors) {
    const turn =
      (error.messageId ? messageIdToTurn.get(error.messageId) : undefined) ??
      findTurnBySessionTime(sessionTurns, error.sessionId, error.timestamp);

    if (!turn) {
      continue;
    }

    turn.errors.push(error);
    turn.status = 'error';
    turn.level = 'error';
    updateTurnActivity(turn, error.timestamp);
  }

  for (const turn of allTurns) {
    turn.messages.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    turn.assistantMessages.sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime(),
    );
    turn.llmCalls.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
    turn.toolCalls.sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime(),
    );
    turn.errors.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  }

  return allTurns.sort(
    (a, b) => b.lastActivityAt.getTime() - a.lastActivityAt.getTime(),
  );
}
