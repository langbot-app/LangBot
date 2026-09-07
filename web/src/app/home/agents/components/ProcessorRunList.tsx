import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight } from 'lucide-react';
import type { ProcessorRun } from '@/app/infra/entities/api';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  processorRunDuration,
  formatRunDuration,
} from './processor-run-timing';

export default function ProcessorRunList({
  runs,
  selectedId,
  onSelect,
  footer,
}: {
  runs: ProcessorRun[];
  selectedId?: string;
  onSelect: (run: ProcessorRun) => void;
  footer?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t('agents.eventProcessor.runs')}
      className="max-h-56 shrink-0 overflow-y-auto rounded-md border"
    >
      {runs.map((run) => {
        const duration = processorRunDuration(run);
        const selected = selectedId === run.run_id;
        const event = run.metadata.event_type ?? '';
        const label = eventPatternLabel(event, t);
        return (
          <Button
            key={run.run_id}
            variant="ghost"
            aria-pressed={selected}
            onClick={() => onSelect(run)}
            aria-label={`${label} ${event} ${new Date(run.created_at * 1000).toLocaleString()}`}
            title={event}
            className="flex h-auto min-h-12 w-full justify-start gap-3 rounded-none border-b px-3 py-2 text-left text-sm font-normal last:border-b-0 aria-pressed:bg-accent"
          >
            <span className="min-w-0 flex-1 space-y-1">
              <span className="block truncate font-medium">{label}</span>
              <time
                className="block text-xs text-muted-foreground"
                dateTime={new Date(run.created_at * 1000).toISOString()}
              >
                {new Date(run.created_at * 1000).toLocaleString()}
              </time>
            </span>
            <span className="flex shrink-0 flex-col items-end gap-1">
              <Badge
                variant={
                  run.status === 'failed' || run.status === 'timeout'
                    ? 'destructive'
                    : 'outline'
                }
                className="px-1.5 py-0 text-xs"
              >
                {t(`agents.eventProcessor.status_${run.status}`, {
                  defaultValue: run.status,
                })}
              </Badge>
              {duration !== null && (
                <span className="font-mono text-xs text-muted-foreground">
                  {formatRunDuration(duration)}
                </span>
              )}
            </span>
            <ChevronRight
              className={`size-4 shrink-0 ${selected ? 'text-foreground' : 'text-muted-foreground'}`}
            />
          </Button>
        );
      })}
      {footer}
    </div>
  );
}
