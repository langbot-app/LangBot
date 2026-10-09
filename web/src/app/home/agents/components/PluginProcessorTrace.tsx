import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight, ScrollText } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { DebugExecutionEvent } from './debug-execution';

export function ProcessorPayload({
  title,
  value,
}: {
  title: ReactNode;
  value: unknown;
}) {
  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          className="h-auto w-full justify-start whitespace-normal text-left group"
        >
          <ChevronRight className="size-4 shrink-0 transition-transform group-data-[state=open]:rotate-90" />
          <span className="min-w-0 break-words">{title}</span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="p-3 text-xs whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
          {JSON.stringify(value, null, 2)}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function PluginProcessorTrace({
  events,
  toolLabels = {},
}: {
  events: DebugExecutionEvent[];
  toolLabels?: Record<string, string>;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
      {events.map((event, index) =>
        event.type === 'processor.log' ? (
          <div
            key={event.sequence ?? index}
            className="min-w-0 overflow-hidden rounded-lg border bg-background"
          >
              <div className="flex items-center gap-2 border-b bg-muted/30 px-4 py-3">
                <ScrollText className="size-4 text-muted-foreground" />
                <span className="flex-1 text-sm font-medium">{t('agents.eventProcessor.logsTab')}</span>
                <Badge status={String(event.data.level)}>{String(event.data.level)}</Badge>
              </div>
              <p className={`min-w-0 whitespace-pre-wrap break-words p-4 text-sm leading-7 [overflow-wrap:anywhere] ${event.data.level === 'error' ? 'text-destructive' : ''}`}>
                {String(event.data.text)}
              </p>
          </div>
        ) : (
          <div key={event.sequence ?? index} className="rounded-lg border bg-background p-3">
          <ProcessorPayload
            title={
              <>
                {t(
                  `agents.eventProcessor.trace_${event.type.replaceAll('.', '_')}`,
                  { defaultValue: event.type },
                )}
                {typeof event.data.tool_name === 'string' && (
                  <span className="ml-2 text-muted-foreground">
                    {toolLabels[event.data.tool_name] || event.data.tool_name}
                  </span>
                )}
              </>
            }
            value={event.data}
          />
          </div>
        ),
      )}
    </div>
  );
}
