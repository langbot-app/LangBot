import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronRight } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
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

export default function EventProcessorTrace({
  events,
  toolLabels = {},
}: {
  events: DebugExecutionEvent[];
  toolLabels?: Record<string, string>;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-2">
      {events.map((event, index) =>
        event.type === 'processor.log' ? (
          <Alert
            key={event.sequence ?? index}
            variant={event.data.level === 'error' ? 'destructive' : 'default'}
          >
            <AlertDescription className="flex min-w-0 items-start gap-2">
              <Badge variant="outline">{String(event.data.level)}</Badge>
              <span className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {String(event.data.text)}
              </span>
            </AlertDescription>
          </Alert>
        ) : (
          <ProcessorPayload
            key={event.sequence ?? index}
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
        ),
      )}
    </div>
  );
}
