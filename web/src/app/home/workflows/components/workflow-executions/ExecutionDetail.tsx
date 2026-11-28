import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, CircleAlert } from 'lucide-react';
import type {
  WorkflowExecution,
  WorkflowExecutionNodeInfo,
} from '@/app/infra/entities/api';
import { Badge } from '@/components/ui/badge';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import {
  formatDateTime,
  parseUTCTimestamp,
} from '@/app/home/monitoring/utils/dateUtils';
import { useWorkflowStore } from '../../store/useWorkflowStore';

type Status = WorkflowExecution['status'] | WorkflowExecutionNodeInfo['status'];

const STATUS_STYLE: Record<string, string> = {
  completed:
    'border-emerald-200/70 bg-emerald-50/70 text-emerald-700 dark:border-emerald-800/50 dark:bg-emerald-950/30 dark:text-emerald-300',
  failed:
    'border-red-200/70 bg-red-50/70 text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300',
  running:
    'border-blue-200/70 bg-blue-50/70 text-blue-700 dark:border-blue-800/50 dark:bg-blue-950/30 dark:text-blue-300',
  waiting:
    'border-amber-200/70 bg-amber-50/70 text-amber-700 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-300',
};

const DOT_STYLE: Record<string, string> = {
  completed: 'bg-emerald-500',
  failed: 'bg-red-500',
  running: 'bg-blue-500',
  waiting: 'bg-amber-500',
};

export function StatusDot({ status }: { status: Status }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-block size-2 shrink-0 rounded-full',
        DOT_STYLE[status] ?? 'bg-muted-foreground/40',
      )}
    />
  );
}

export function ExecutionStatusBadge({ status }: { status: Status }) {
  const { t } = useTranslation();
  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 whitespace-nowrap',
        STATUS_STYLE[status] ??
          'border-border bg-muted/40 text-muted-foreground',
      )}
    >
      <StatusDot status={status} />
      {t(`workflows.run.status.${status}`)}
    </Badge>
  );
}

function timestamp(value?: string): Date | null {
  if (!value) return null;
  const date = parseUTCTimestamp(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatStartedAt(value?: string): string {
  const date = timestamp(value);
  return date ? formatDateTime(date) : '—';
}

export function executionDuration(start?: string, end?: string): string {
  const from = timestamp(start);
  const to = timestamp(end);
  if (!from || !to) return '—';
  const ms = Math.max(0, to.getTime() - from.getTime());
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
}

// Bot deliveries carry the serialized platform event; manual test runs only
// carry the typed message; nested runs come from a Call Workflow node.
export function executionTriggerLabel(
  execution: WorkflowExecution,
  t: (key: string) => string,
): string {
  if (execution.trigger_type === 'workflow_call')
    return t('workflows.run.triggerWorkflow');
  if (execution.trigger_data && 'type' in execution.trigger_data)
    return t('workflows.run.triggerBot');
  return t('workflows.run.triggerManual');
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  const empty =
    value == null ||
    (typeof value === 'object' && Object.keys(value as object).length === 0);
  return (
    <div className="min-w-0 space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">{title}</p>
      <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/40 p-3 text-xs leading-relaxed whitespace-pre-wrap break-all">
        {empty ? '—' : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function NodeStep({
  node,
  index,
  label,
}: {
  node: WorkflowExecutionNodeInfo;
  index: number;
  label: string;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(node.status === 'failed');
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="rounded-lg border bg-card">
        <CollapsibleTrigger className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-muted/40">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
            {index + 1}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{label}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {node.node_type}
            </span>
          </span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {executionDuration(
              node.started_at ?? node.start_time,
              node.completed_at ?? node.end_time,
            )}
          </span>
          <ExecutionStatusBadge status={node.status} />
          <ChevronRight
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-3 border-t px-3 py-3">
            {node.error && (
              <p className="flex items-start gap-2 rounded-lg border border-red-200/70 bg-red-50/70 p-2.5 text-xs text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300">
                <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
                <span className="break-all">{node.error}</span>
              </p>
            )}
            <div className="grid gap-3 md:grid-cols-2">
              <JsonBlock title={t('workflows.inputs')} value={node.inputs} />
              <JsonBlock title={t('workflows.outputs')} value={node.outputs} />
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

export function ExecutionDetail({
  execution,
}: {
  execution: WorkflowExecution;
}) {
  const { t } = useTranslation();
  const nodes = useWorkflowStore((state) => state.nodes);
  const labelOf = (nodeId: string) =>
    nodes.find((node) => node.id === nodeId)?.data.label || nodeId;
  const started = execution.started_at ?? execution.start_time;
  const finished = execution.completed_at ?? execution.end_time;
  const steps = execution.node_executions ?? [];
  return (
    <div className="space-y-4" data-testid="workflow-execution-detail">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border bg-card p-4">
        <ExecutionStatusBadge status={execution.status} />
        <Fact
          label={t('workflows.run.startedAt')}
          value={formatStartedAt(started)}
        />
        <Fact
          label={t('workflows.run.duration')}
          value={executionDuration(started, finished)}
        />
        <Fact
          label={t('workflows.run.trigger')}
          value={executionTriggerLabel(execution, t)}
        />
        <Fact
          label={t('workflows.version')}
          value={`v${execution.workflow_version}`}
        />
      </div>
      {execution.error && (
        <p className="flex items-start gap-2 rounded-xl border border-red-200/70 bg-red-50/70 p-3 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span className="break-all">{execution.error}</span>
        </p>
      )}
      <div className="space-y-2">
        <p className="text-sm font-medium">
          {t('workflows.run.steps', { count: steps.length })}
        </p>
        {steps.map((node, index) => (
          <NodeStep
            key={`${node.node_id}-${index}`}
            node={node}
            index={index}
            label={labelOf(node.node_id)}
          />
        ))}
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="truncate text-sm font-medium tabular-nums">{value}</p>
    </div>
  );
}
