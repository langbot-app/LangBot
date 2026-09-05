import type { DebugExecutionEvent } from '@/app/infra/entities/api/agent-debug';
export type { DebugExecutionEvent } from '@/app/infra/entities/api/agent-debug';

export type ExecutionStep =
  | { kind: 'message'; text: string; reasoning: string }
  | {
      kind: 'tool';
      id: string;
      name: string;
      parameters?: unknown;
      result?: unknown;
      error?: string;
      status: 'running' | 'completed' | 'failed';
    };

function contentText(content: unknown): string {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return '';
  return content
    .map((part) => (typeof part?.text === 'string' ? part.text : ''))
    .join('');
}

function splitMessage(
  content: string,
  reasoning: string,
): ExecutionStep & { kind: 'message' } {
  const thoughts: string[] = [];
  const text = content.replace(
    /<think>([\s\S]*?)(?:<\/think>|$)/gi,
    (_, thought) => {
      thoughts.push(thought);
      return '';
    },
  );
  return {
    kind: 'message',
    text: text.trim(),
    reasoning: (reasoning || thoughts.join('\n')).trim(),
  };
}

/** Preserve execution order while replacing streamed messages with their final snapshot. */
export function executionSteps(events: DebugExecutionEvent[]): ExecutionStep[] {
  const steps: ExecutionStep[] = [];
  const tools = new Map<string, number>();
  let active: number | null = null;
  let content = '';
  let reasoning = '';
  let visiblePrefix = '';
  for (const event of events) {
    const data = event.data ?? {};
    if (
      event.type === 'tool.call.started' ||
      event.type === 'tool.call.completed'
    ) {
      if (active !== null && content) visiblePrefix = content;
      active = null;
      content = reasoning = '';
      const id = String(
        data.tool_call_id ?? `${event.sequence}:${steps.length}`,
      );
      const index = tools.get(id);
      const old = index === undefined ? undefined : steps[index];
      const step: ExecutionStep = {
        kind: 'tool',
        id,
        name: String(data.tool_name ?? ''),
        ...(event.type === 'tool.call.started'
          ? { parameters: data.parameters }
          : {
              parameters: old?.kind === 'tool' ? old.parameters : undefined,
              result: data.result,
              error: data.error,
            }),
        status:
          event.type === 'tool.call.started'
            ? 'running'
            : data.error ||
                data.result?.ok === false ||
                data.result?.isError === true
              ? 'failed'
              : 'completed',
      };
      if (index === undefined) {
        tools.set(id, steps.length);
        steps.push(step);
      } else steps[index] = step;
      continue;
    }
    if (
      !['message.delta', 'message.completed', 'run.completed'].includes(
        event.type,
      )
    )
      continue;
    const message = data.chunk ?? data.message;
    if (!message || (message.role && message.role !== 'assistant')) continue;
    const nextContent = contentText(message.content);
    const fields = message.provider_specific_fields ?? {};
    const nextReasoning =
      contentText(fields.reasoning_content ?? message.reasoning_content) ||
      (Array.isArray(fields.thinking_blocks)
        ? fields.thinking_blocks
            .map((block: { thinking?: string }) => block.thinking ?? '')
            .join('\n')
        : '');
    if (event.type === 'message.delta') {
      // LocalAgent batches cumulative snapshots with msg_sequence; raw deltas use zero.
      if (typeof message.all_content === 'string')
        content = message.all_content;
      else if (message.msg_sequence > 0) content = nextContent;
      else content += nextContent;
      if (Array.isArray(fields.thinking_blocks) || message.msg_sequence > 0) {
        reasoning = nextReasoning || reasoning;
      } else reasoning += nextReasoning;
    } else {
      content = nextContent;
      reasoning = nextReasoning || reasoning;
    }
    // LocalAgent includes previous model turns in cumulative chunks after tool calls.
    const visibleContent =
      event.type === 'message.delta' &&
      message.msg_sequence > 0 &&
      visiblePrefix &&
      content.startsWith(visiblePrefix)
        ? content.slice(visiblePrefix.length)
        : content;
    const step = splitMessage(visibleContent, reasoning);
    const previous = steps.at(-1);
    if (
      event.type === 'run.completed' &&
      active === null &&
      previous?.kind === 'message' &&
      previous.text === step.text &&
      (!step.reasoning || previous.reasoning === step.reasoning)
    )
      continue;
    if (active === null) {
      active = steps.length;
      steps.push(step);
    } else steps[active] = step;
    if (event.type !== 'message.delta') {
      active = null;
      content = reasoning = '';
    }
  }
  return steps;
}
