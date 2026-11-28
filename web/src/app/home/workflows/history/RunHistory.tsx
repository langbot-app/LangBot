import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight, History, RefreshCw } from 'lucide-react';
import { backendClient } from '@/app/infra/http';
import type { WorkflowExecution } from '@/app/infra/entities/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  ExecutionDetail,
  StatusDot,
  formatDuration,
  formatStartedAt,
  triggerLabel,
} from './ExecutionDetail';

const PAGE_SIZE = 20;

export default function RunHistory({ workflowId }: { workflowId: string }) {
  const { t } = useTranslation();
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [selected, setSelected] = useState<WorkflowExecution>();
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const select = useCallback(
    async (uuid: string) => {
      try {
        setSelected(
          (await backendClient.getWorkflowExecution(workflowId, uuid))
            .execution,
        );
      } catch (error) {
        setError(String(error));
      }
    },
    [workflowId],
  );

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const result = await backendClient.getWorkflowExecutions(
        workflowId,
        PAGE_SIZE,
        offset,
      );
      setExecutions(result.executions);
      setTotal(result.total);
      setError('');
      if (result.executions[0]) void select(result.executions[0].uuid);
      else setSelected(undefined);
    } catch (error) {
      setError(String(error));
    } finally {
      setLoading(false);
    }
  }, [workflowId, offset, select]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!loading && !error && executions.length === 0) {
    return (
      <div className="flex h-full min-h-80 flex-col items-center justify-center gap-3 rounded-xl border border-dashed p-8 text-center">
        <History className="size-8 text-muted-foreground" />
        <p className="text-sm font-medium">{t('workflows.run.noExecutions')}</p>
        <p className="max-w-sm text-sm text-muted-foreground">
          {t('workflows.run.noExecutionsHint')}
        </p>
      </div>
    );
  }

  return (
    <div className="grid h-full min-h-0 gap-4 lg:grid-cols-[minmax(260px,340px)_1fr]">
      <div className="flex min-h-0 flex-col rounded-xl border">
        <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
          <span className="text-sm font-medium">
            {t('workflows.run.total', { count: total })}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={t('common.refresh')}
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw className={cn('size-4', loading && 'animate-spin')} />
          </Button>
        </div>
        {error && (
          <p role="alert" className="px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto p-1.5">
          {executions.map((execution) => {
            const active = selected?.uuid === execution.uuid;
            return (
              <button
                key={execution.uuid}
                type="button"
                aria-pressed={active}
                data-testid="workflow-execution-row"
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-muted/60',
                  active && 'bg-muted',
                )}
                onClick={() => void select(execution.uuid)}
              >
                <StatusDot status={execution.status} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium tabular-nums">
                    {formatStartedAt(execution.started_at)}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {triggerLabel(execution.trigger, t)} ·{' '}
                    {execution.input_text ||
                      t(`workflows.run.status.${execution.status}`)}
                  </span>
                </span>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {formatDuration(execution.duration_ms)}
                </span>
              </button>
            );
          })}
        </div>
        {total > PAGE_SIZE && (
          <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={t('common.previous')}
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="tabular-nums">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={t('common.next')}
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        )}
      </div>
      <div className="min-h-0 overflow-y-auto">
        {selected ? (
          <ExecutionDetail execution={selected} />
        ) : (
          <div className="flex h-full min-h-60 items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">
            {t('workflows.run.selectExecution')}
          </div>
        )}
      </div>
    </div>
  );
}
