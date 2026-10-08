import React from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import type { ExecutionRow } from '@/app/infra/entities/api/monitoring-executions';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import { formatRunDuration } from '@/app/home/agents/components/processor-run-timing';
import { formatDateTime } from '../../utils/dateUtils';

interface ExecutionTableProps {
  rows: ExecutionRow[];
  selectedId?: string | null;
  onSelect: (row: ExecutionRow) => void;
}

const STATUS_GROUPS = [
  'completed',
  'failed',
  'running',
  'queued',
  'cancelled',
  'ignored',
];

export function executionStatusLabel(row: ExecutionRow, t: TFunction): string {
  if (STATUS_GROUPS.includes(row.status_group)) {
    return t(`monitoring.execution.status.${row.status_group}`);
  }
  return row.status;
}

export function executionStatusVariant(
  statusGroup: string,
): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (statusGroup === 'failed') return 'destructive';
  if (statusGroup === 'ignored' || statusGroup === 'queued') return 'secondary';
  return 'outline';
}

const KIND_GROUPS = [
  'agent',
  'pipeline',
  'processor',
  'event_processor',
  'event',
];

export function executionKindLabel(row: ExecutionRow, t: TFunction): string {
  if (KIND_GROUPS.includes(row.target_kind)) {
    if (row.target_kind === 'event_processor')
      return t('monitoring.execution.kind.processor');
    if (row.target_kind === 'event') return t('monitoring.unified.unhandled');
    return t(`monitoring.execution.kind.${row.target_kind}`);
  }
  return row.target_kind;
}

export function executionTargetLabel(row: ExecutionRow, t: TFunction): string {
  if (row.source !== 'pipeline') {
    return eventPatternLabel(row.title, t);
  }
  const title = row.title ?? '';
  return title.length > 48 ? `${title.slice(0, 48)}…` : title;
}

// The processor the row ran: the Agent or Pipeline that handled it. A run whose
// Agent was deleted still names the Runner that executed it.
export function executionProcessorLabel(row: ExecutionRow): string {
  return row.target_name || row.runner_id || row.target_id || '—';
}

export default function ExecutionTable({
  rows,
  selectedId,
  onSelect,
}: ExecutionTableProps) {
  const { t } = useTranslation();

  return (
    // The page hands this table a fixed-height region: the table's own scroll
    // container takes that height so the header stays sticky while rows scroll
    // under it.
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border">
      <Table containerClassName="min-h-0 flex-1 overflow-y-auto">
        <TableHeader className="bg-card sticky top-0 z-10">
          <TableRow>
            <TableHead>{t('monitoring.execution.columns.time')}</TableHead>
            <TableHead>{t('monitoring.execution.columns.target')}</TableHead>
            <TableHead>{t('monitoring.unified.inputs')}</TableHead>
            <TableHead>{t('monitoring.execution.columns.status')}</TableHead>
            <TableHead className="text-right">
              {t('monitoring.execution.columns.duration')}
            </TableHead>
            <TableHead className="text-right">
              {t('monitoring.execution.columns.tokens')}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const selected = selectedId === row.id;
            return (
              <TableRow
                key={`${row.source}-${row.id}`}
                role="button"
                tabIndex={0}
                aria-pressed={selected}
                data-state={selected ? 'selected' : undefined}
                className="cursor-pointer data-[state=selected]:bg-muted"
                onClick={() => onSelect(row)}
                onKeyDown={(
                  event: React.KeyboardEvent<HTMLTableRowElement>,
                ) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelect(row);
                  }
                }}
              >
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {row.created_at_ms == null
                    ? '—'
                    : formatDateTime(new Date(row.created_at_ms))}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">
                        {executionKindLabel(row, t)}
                      </Badge>
                      <span className="truncate font-medium">
                        {row.source === 'event'
                          ? t('monitoring.unified.unhandled')
                          : executionProcessorLabel(row)}
                      </span>
                    </div>
                    <span className="truncate text-xs text-muted-foreground">
                      {t('monitoring.execution.triggeredBy', {
                        trigger: executionTargetLabel(row, t),
                      })}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="max-w-xs">
                  <div className="line-clamp-2 break-words text-sm">
                    {row.input_preview || '—'}
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {[row.bot_name, row.user_name || row.user_id]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant={executionStatusVariant(row.status_group)}>
                      {executionStatusLabel(row, t)}
                    </Badge>
                    {row.debug && (
                      <Badge variant="secondary">
                        {t('monitoring.execution.debug')}
                      </Badge>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.duration_ms == null
                    ? '—'
                    : formatRunDuration(row.duration_ms)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {row.usage?.total_tokens != null
                    ? row.usage.total_tokens.toLocaleString()
                    : '—'}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
