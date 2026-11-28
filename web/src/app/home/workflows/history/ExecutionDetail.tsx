import { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, CircleAlert, Forward } from 'lucide-react';
import type {
  WorkflowExecution,
  WorkflowStepRun,
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
import { STEP_META, stepBranches } from '../lib/catalog';
import { describeError } from '../lib/issues';
import { EditorContext } from '../editor/EditorContext';

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

export function StatusDot({ status }: { status: string }) {
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

export function ExecutionStatusBadge({ status }: { status: string }) {
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
      {t(`workflows.run.status.${status}`, { defaultValue: status })}
    </Badge>
  );
}

export function formatStartedAt(value?: string | null): string {
  if (!value) return '—';
  const date = parseUTCTimestamp(value);
  return Number.isNaN(date.getTime()) ? '—' : formatDateTime(date);
}

export function formatDuration(ms?: number | null): string {
  if (ms == null) return '—';
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
}

export function triggerLabel(trigger: string, t: (key: string) => string) {
  return t(`workflows.run.trigger.${trigger}`);
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

function StepRow({ step, index }: { step: WorkflowStepRun; index: number }) {
  const { t } = useTranslation();
  const editor = useContext(EditorContext);
  const definition = editor?.graph.nodes.find(
    (node) => node.id === step.node_id,
  );
  const branch =
    step.branch &&
    ((definition &&
      stepBranches(definition, t('workflows.branches.else'), (i) =>
        t('workflows.branches.unnamed', { index: i + 1 }),
      )?.find((item) => item.id === step.branch)?.label) ||
      (step.branch === 'else' ? t('workflows.branches.else') : step.branch));
  const [open, setOpen] = useState(step.status === 'failed');
  const meta = STEP_META[step.node_type];
  const Icon = meta?.icon;
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="rounded-lg border bg-card">
        <CollapsibleTrigger className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-muted/40">
          <span className="w-5 shrink-0 text-center text-xs text-muted-foreground tabular-nums">
            {index + 1}
          </span>
          {Icon && (
            <span
              className={cn(
                'grid size-7 shrink-0 place-items-center rounded-lg',
                meta.tone,
              )}
            >
              <Icon className="size-3.5" />
            </span>
          )}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {step.node_name || t(`workflows.steps.${step.node_type}`)}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {t(`workflows.steps.${step.node_type}`, {
                defaultValue: step.node_type,
              })}
              {branch ? ` · → ${branch}` : ''}
            </span>
          </span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {formatDuration(step.duration_ms)}
          </span>
          <ExecutionStatusBadge status={step.status} />
          <ChevronRight
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-3 border-t px-3 py-3">
            {step.error && (
              <p className="flex items-start gap-2 rounded-lg border border-red-200/70 bg-red-50/70 p-2.5 text-xs text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300">
                <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
                <span className="break-all">{step.error}</span>
              </p>
            )}
            <div className="grid gap-3 md:grid-cols-2">
              <JsonBlock
                title={t('workflows.form.runInputs')}
                value={step.inputs}
              />
              <JsonBlock
                title={t('workflows.form.runOutputs')}
                value={step.outputs}
              />
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
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

export function ExecutionDetail({
  execution,
}: {
  execution: WorkflowExecution;
}) {
  const { t } = useTranslation();
  const editor = useContext(EditorContext);
  const steps = execution.steps ?? [];
  return (
    <div className="space-y-4" data-testid="workflow-execution-detail">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border bg-card p-4">
        <ExecutionStatusBadge status={execution.status} />
        <Fact
          label={t('workflows.run.startedAt')}
          value={formatStartedAt(execution.started_at)}
        />
        <Fact
          label={t('workflows.run.duration')}
          value={formatDuration(execution.duration_ms)}
        />
        <Fact
          label={t('workflows.run.triggerLabel')}
          value={triggerLabel(execution.trigger, t)}
        />
        {execution.input_text && (
          <Fact label={t('workflows.run.input')} value={execution.input_text} />
        )}
      </div>
      {execution.error && (
        <p className="flex items-start gap-2 rounded-xl border border-red-200/70 bg-red-50/70 p-3 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-950/30 dark:text-red-300">
          <CircleAlert className="mt-0.5 size-4 shrink-0" />
          <span className="break-all">
            {editor
              ? describeError(execution.error, editor.graph, t)
              : execution.error}
          </span>
        </p>
      )}
      {execution.handoff && (
        <p className="flex items-center gap-2 rounded-xl border border-amber-200/70 bg-amber-50/70 p-3 text-sm text-amber-800 dark:border-amber-800/50 dark:bg-amber-950/30 dark:text-amber-300">
          <Forward className="size-4 shrink-0" />
          {t('workflows.test.handoff', {
            name: execution.handoff.name ?? execution.handoff.target_uuid,
          })}
        </p>
      )}
      <div className="space-y-2">
        <p className="text-sm font-medium">
          {t('workflows.run.steps', { count: steps.length })}
        </p>
        {steps.map((step, index) => (
          <StepRow
            key={`${step.node_id}-${step.seq}`}
            step={step}
            index={index}
          />
        ))}
      </div>
    </div>
  );
}
