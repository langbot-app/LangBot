import type { WorkflowGraph, WorkflowIssue } from '@/app/infra/entities/api';

const ISSUE = /^([\w-]+)(?:: ([^:]+))?: ([a-z_]+)$/;

/** Validation failures come back as `step: field: code`; recover the issue. */
export function parseIssue(error?: string | null): WorkflowIssue | null {
  const match = error?.trim().match(ISSUE);
  if (!match) return null;
  return {
    node_id: match[1],
    field: match[2],
    code: match[3],
    severity: 'error',
  };
}

export function describeError(
  error: string | null | undefined,
  graph: WorkflowGraph,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const issue = parseIssue(error);
  if (!issue) return error ?? '';
  const step = graph.nodes.find((node) => node.id === issue.node_id);
  const name = step
    ? step.name || t(`workflows.steps.${step.type}`)
    : issue.node_id;
  return `「${name}」${t(`workflows.issues.${issue.code}`, { defaultValue: issue.code })}`;
}
