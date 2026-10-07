import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { backendClient } from '@/app/infra/http';
import type {
  ExecutionCallRow,
  ExecutionDetail,
  ExecutionRow,
} from '@/app/infra/entities/api/monitoring-executions';
import AgentExecutionTrace from '@/app/home/agents/components/AgentExecutionTrace';
import { formatRunDuration } from '@/app/home/agents/components/processor-run-timing';
import { formatDateTime } from '../../utils/dateUtils';
import {
  executionKindLabel,
  executionProcessorLabel,
  executionStatusLabel,
  executionStatusVariant,
  executionTargetLabel,
} from './ExecutionTable';

interface ExecutionDetailSheetProps {
  row: ExecutionRow | null;
  onClose: () => void;
}

/** Walk parsed JSON, collecting every `"text"` value (OpenAI-style content). */
function collectText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    return value.map(collectText).filter(Boolean).join(' ');
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (typeof record.text === 'string') return record.text;
    return Object.values(record).map(collectText).filter(Boolean).join(' ');
  }
  return '';
}

function messagePreview(raw: string | null | undefined): string {
  if (!raw) return '';
  try {
    return collectText(JSON.parse(raw)).trim() || raw;
  } catch {
    return raw;
  }
}

function callTitle(call: ExecutionCallRow, index: number): string {
  const candidates = [
    call.model_name,
    call.model,
    call.name,
    call.tool_name,
    call.function,
    call.error_type,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate) return candidate;
  }
  return typeof call.id === 'string' && call.id ? call.id : `#${index + 1}`;
}

export default function ExecutionDetailSheet({
  row,
  onClose,
}: ExecutionDetailSheetProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!row) {
      setDetail(null);
      setError(false);
      setLoading(false);
      return;
    }
    const requestId = requestRef.current + 1;
    requestRef.current = requestId;
    setLoading(true);
    setError(false);
    setDetail(null);
    backendClient
      .getExecutionDetail(row.source, row.id)
      .then((result) => {
        if (requestRef.current !== requestId) return;
        setDetail(result);
      })
      .catch(() => {
        if (requestRef.current !== requestId) return;
        setError(true);
      })
      .finally(() => {
        if (requestRef.current === requestId) setLoading(false);
      });
  }, [row]);

  const isAgent =
    detail != null ? detail.source === 'agent' : row?.source === 'agent';

  const metadata: { label: string; value: string }[] = [];
  if (row) {
    metadata.push({
      label: t('monitoring.execution.detail.executionId'),
      value: row.id,
    });
    if (row.event_id) {
      metadata.push({
        label: t('monitoring.execution.detail.eventId'),
        value: row.event_id,
      });
    }
    if (row.runner_id) {
      metadata.push({
        label: t('monitoring.execution.detail.runner'),
        value: row.runner_id,
      });
    }
    if (row.queue_name) {
      metadata.push({
        label: t('monitoring.execution.detail.queue'),
        value: row.queue_name,
      });
    }
    if (row.created_at_ms != null) {
      metadata.push({
        label: t('monitoring.execution.detail.created'),
        value: formatDateTime(new Date(row.created_at_ms)),
      });
    }
    if (row.duration_ms != null) {
      metadata.push({
        label: t('monitoring.execution.detail.duration'),
        value: formatRunDuration(row.duration_ms),
      });
    }
    if (isAgent && row.usage?.total_tokens != null) {
      metadata.push({
        label: t('monitoring.execution.detail.usage'),
        value: row.usage.total_tokens.toLocaleString(),
      });
    }
  }

  const objectHref = row
    ? row.target_kind === 'agent' && row.target_id
      ? `/home/agents?id=${encodeURIComponent(row.target_id)}`
      : row.target_kind === 'pipeline' && row.target_id
        ? `/home/pipelines?id=${encodeURIComponent(row.target_id)}`
        : null
    : null;

  const renderCalls = (title: string, calls: ExecutionCallRow[]) => (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">{title}</h3>
      {calls.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t('monitoring.execution.detail.noEvents')}
        </p>
      ) : (
        <div className="space-y-1">
          {calls.map((call, index) => {
            const duration =
              typeof call.duration === 'number' ? call.duration : null;
            return (
              <div
                key={`${title}-${call.id}-${index}`}
                className="flex items-start justify-between gap-2 rounded-md border px-3 py-2 text-sm"
              >
                <div className="min-w-0">
                  <div className="truncate">{callTitle(call, index)}</div>
                  {call.error_message && (
                    <div className="truncate text-xs text-muted-foreground">
                      {call.error_message}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {call.status && (
                    <Badge
                      variant={executionStatusVariant(
                        String(call.status).toLowerCase(),
                      )}
                    >
                      {call.status}
                    </Badge>
                  )}
                  <span className="w-16 text-right tabular-nums text-muted-foreground">
                    {duration == null ? '—' : formatRunDuration(duration)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );

  return (
    <Sheet
      open={row != null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent side="right" className="w-full p-0 sm:max-w-2xl">
        <SheetDescription className="sr-only">
          {t('monitoring.execution.detail.a11yDescription')}
        </SheetDescription>
        <ScrollArea className="h-full">
          <div className="space-y-6 p-6">
            {row && (
              <>
                <SheetHeader className="space-y-3">
                  <SheetTitle className="pr-8 text-left">
                    {executionProcessorLabel(row)}
                  </SheetTitle>
                  <p className="text-sm text-muted-foreground">
                    {t('monitoring.execution.triggeredBy', {
                      trigger: executionTargetLabel(row, t),
                    })}
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge variant="outline">
                      {executionKindLabel(row, t)}
                    </Badge>
                    <Badge variant={executionStatusVariant(row.status_group)}>
                      {executionStatusLabel(row, t)}
                    </Badge>
                    {row.debug && (
                      <Badge variant="secondary">
                        {t('monitoring.execution.debug')}
                      </Badge>
                    )}
                    {objectHref && (
                      <Button
                        asChild
                        size="sm"
                        variant="outline"
                        className="ml-auto h-7"
                      >
                        <Link to={objectHref}>
                          <ExternalLink className="mr-1 h-3.5 w-3.5" />
                          {t('monitoring.execution.detail.openObject')}
                        </Link>
                      </Button>
                    )}
                  </div>
                </SheetHeader>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {metadata.map((item) => (
                    <div key={item.label} className="min-w-0 space-y-0.5">
                      <div className="text-xs text-muted-foreground">
                        {item.label}
                      </div>
                      <div className="truncate text-sm font-medium">
                        {item.value}
                      </div>
                    </div>
                  ))}
                </div>

                <Separator />

                {isAgent ? (
                  <div className="space-y-3">
                    <h3 className="text-sm font-medium">
                      {t('monitoring.execution.detail.timeline')}
                    </h3>
                    {loading && (
                      <div className="space-y-2">
                        <Skeleton className="h-16 w-full" />
                        <Skeleton className="h-16 w-full" />
                      </div>
                    )}
                    {!loading && error && (
                      <p className="text-sm text-destructive">
                        {t('monitoring.execution.detail.loadError')}
                      </p>
                    )}
                    {!loading &&
                      !error &&
                      detail?.source === 'agent' &&
                      (detail.events.length > 0 ? (
                        <AgentExecutionTrace
                          events={detail.events}
                          finished={row.status_group !== 'running'}
                          toolLabels={{}}
                        />
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          {t('monitoring.execution.detail.noEvents')}
                        </p>
                      ))}
                  </div>
                ) : (
                  <div className="space-y-5">
                    {loading && (
                      <div className="space-y-2">
                        <Skeleton className="h-20 w-full" />
                        <Skeleton className="h-20 w-full" />
                      </div>
                    )}
                    {!loading && error && (
                      <p className="text-sm text-destructive">
                        {t('monitoring.execution.detail.loadError')}
                      </p>
                    )}
                    {!loading && !error && detail?.source === 'pipeline' && (
                      <>
                        <div className="space-y-2">
                          <h3 className="text-sm font-medium">
                            {t('monitoring.execution.detail.query')}
                          </h3>
                          <p className="whitespace-pre-wrap break-words rounded-md border bg-muted/40 px-3 py-2 text-sm">
                            {messagePreview(detail.message.message_content) ||
                              '—'}
                          </p>
                        </div>
                        {renderCalls(
                          t('monitoring.execution.detail.modelCalls'),
                          detail.llm_calls,
                        )}
                        {renderCalls(
                          t('monitoring.execution.detail.toolCalls'),
                          detail.tool_calls,
                        )}
                        {renderCalls(
                          t('monitoring.execution.detail.errors'),
                          detail.errors,
                        )}
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
