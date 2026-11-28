import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CircleAlert,
  CircleCheck,
  Forward,
  Loader2,
  RotateCcw,
  Send,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';
import { backendClient } from '@/app/infra/http';
import type {
  ApiRespWorkflowTest,
  WorkflowGraph,
} from '@/app/infra/entities/api';
import { describeError } from '../lib/issues';
import { STANDARD_EVENTS } from '../lib/platform';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import AgentEventDataEditor from '@/app/home/agents/components/AgentEventDataEditor';
import {
  createDebugEventData,
  parseDebugEventData,
} from '@/app/home/agents/components/debug-event-data';
import { OptionSelect } from './fields';
import { useEditor } from './EditorContext';

interface Turn {
  text: string;
  result?: ApiRespWorkflowTest;
  error?: string;
}

export default function TestRunPanel({
  workflowId,
  graph,
  onResult,
}: {
  workflowId: string;
  graph: WorkflowGraph;
  onResult: (result: ApiRespWorkflowTest | null) => void;
}) {
  const { t } = useTranslation();
  const { triggers } = useEditor();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState('');
  const [sessionType, setSessionType] = useState<'person' | 'group'>('person');
  const [running, setRunning] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  // Events the start step listens to, so a test can simulate one like a bot would.
  const testEvents = useMemo(() => {
    const patterns = triggers.flatMap((trigger) =>
      trigger.type === 'event' ? ((trigger.events as string[]) ?? []) : [],
    );
    return [
      ...new Set(
        patterns.flatMap((pattern) =>
          pattern === '*'
            ? STANDARD_EVENTS
            : pattern.endsWith('.*')
              ? STANDARD_EVENTS.filter((event) =>
                  event.startsWith(pattern.slice(0, -1)),
                )
              : [pattern],
        ),
      ),
    ];
  }, [triggers]);
  const [mode, setMode] = useState<'message' | 'event'>('message');
  const [eventType, setEventType] = useState('');
  const [eventText, setEventText] = useState('{}');
  const sample = (type: string) =>
    JSON.stringify(
      createDebugEventData(
        type,
        {
          user: t('agents.debugData.sampleUser'),
          message: t('agents.debugData.sampleMessage'),
          feedback: t('agents.debugData.sampleFeedback'),
        },
        true,
      ),
      null,
      2,
    );
  const pickEvent = (type: string) => {
    setEventType(type);
    setEventText(sample(type));
  };
  const eventMode = mode === 'event' && testEvents.length > 0;
  const currentEvent = testEvents.includes(eventType)
    ? eventType
    : (testEvents[0] ?? '');
  useEffect(() => {
    if (testEvents.length && !testEvents.includes(eventType))
      pickEvent(testEvents[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testEvents]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' });
  }, [turns, running]);

  const send = async () => {
    const eventData = eventMode ? parseDebugEventData(eventText) : null;
    const message = eventMode ? '' : text.trim();
    if ((!message && !eventData) || running) return;
    if (!eventMode) setText('');
    setRunning(true);
    setTurns((current) => [
      ...current,
      { text: eventMode ? eventPatternLabel(currentEvent, t) : message },
    ]);
    try {
      const result = await backendClient.testWorkflow(workflowId, {
        text: message,
        session_type: sessionType,
        graph,
        triggers,
        ...(eventData
          ? { event: { type: currentEvent, data: eventData } }
          : {}),
      });
      onResult(result);
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1 ? { ...turn, result } : turn,
        ),
      );
    } catch (error) {
      const reason =
        (error as { msg?: string; message?: string })?.msg ??
        (error as Error)?.message ??
        String(error);
      setTurns((current) =>
        current.map((turn, index) =>
          index === current.length - 1 ? { ...turn, error: reason } : turn,
        ),
      );
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="test-run">
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {turns.length === 0 && (
          <p className="pt-10 text-center text-sm text-muted-foreground">
            {t('workflows.test.empty')}
          </p>
        )}
        {turns.map((turn, index) => {
          const result = turn.result;
          const steps = result?.steps ?? [];
          const duration = steps.reduce(
            (sum, step) => sum + (step.duration_ms ?? 0),
            0,
          );
          return (
            <div key={index} className="space-y-2">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-3.5 py-2 text-sm whitespace-pre-wrap break-words text-primary-foreground">
                  {turn.text}
                </div>
              </div>
              {result?.replies.map((reply, replyIndex) => (
                <div key={replyIndex} className="flex">
                  <div
                    data-testid="test-reply"
                    className="max-w-[85%] rounded-2xl rounded-tl-sm border bg-card px-3.5 py-2 text-sm whitespace-pre-wrap break-words"
                  >
                    {reply}
                  </div>
                </div>
              ))}
              {result?.handoff && (
                <p className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300">
                  <Forward className="size-3.5" />
                  {t('workflows.test.handoff', {
                    name: result.handoff.name ?? result.handoff.target_uuid,
                  })}
                </p>
              )}
              {result && (
                <p
                  className={cn(
                    'flex items-start gap-1.5 text-xs',
                    result.status === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground',
                  )}
                >
                  {result.status === 'failed' ? (
                    <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
                  ) : (
                    <CircleCheck className="mt-0.5 size-3.5 shrink-0 text-emerald-500" />
                  )}
                  <span className="break-all">
                    {result.status === 'failed'
                      ? describeError(result.error, graph, t) ||
                        t('workflows.test.failed')
                      : t('workflows.test.summary', {
                          count: steps.length,
                          duration,
                        })}
                    {result.status !== 'failed' &&
                      result.replies.length === 0 &&
                      !result.handoff &&
                      ` · ${t('workflows.test.noReply')}`}
                  </span>
                </p>
              )}
              {turn.error && (
                <p className="flex items-start gap-1.5 text-xs text-destructive">
                  <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
                  <span className="break-all">{turn.error}</span>
                </p>
              )}
            </div>
          );
        })}
        {running && (
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            {t('workflows.test.running')}
          </p>
        )}
        <div ref={bottom} />
      </div>
      <div className="space-y-2 border-t p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {testEvents.length > 0 && (
              <ToggleGroup
                type="single"
                size="sm"
                variant="outline"
                value={mode}
                onValueChange={(value) =>
                  value && setMode(value as 'message' | 'event')
                }
              >
                <ToggleGroupItem value="message" className="px-3 text-xs">
                  {t('workflows.test.message')}
                </ToggleGroupItem>
                <ToggleGroupItem value="event" className="px-3 text-xs">
                  {t('workflows.test.event')}
                </ToggleGroupItem>
              </ToggleGroup>
            )}
            {!eventMode && (
              <ToggleGroup
                type="single"
                size="sm"
                variant="outline"
                value={sessionType}
                onValueChange={(value) =>
                  value && setSessionType(value as 'person' | 'group')
                }
              >
                <ToggleGroupItem value="person" className="px-3 text-xs">
                  {t('workflows.test.person')}
                </ToggleGroupItem>
                <ToggleGroupItem value="group" className="px-3 text-xs">
                  {t('workflows.test.group')}
                </ToggleGroupItem>
              </ToggleGroup>
            )}
          </div>
          {turns.length > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 text-xs text-muted-foreground"
              onClick={() => {
                setTurns([]);
                onResult(null);
              }}
            >
              <RotateCcw className="size-3.5" />
              {t('workflows.test.clear')}
            </Button>
          )}
        </div>
        {eventMode && (
          <div className="max-h-72 space-y-2 overflow-y-auto">
            <OptionSelect
              value={currentEvent}
              onChange={pickEvent}
              ariaLabel={t('workflows.test.eventType')}
              options={testEvents.map((event) => ({
                value: event,
                label: eventPatternLabel(event, t),
              }))}
            />
            <AgentEventDataEditor
              eventType={currentEvent}
              value={eventText}
              onChange={setEventText}
              processor
            />
            <Button
              type="button"
              className="w-full"
              disabled={running || !parseDebugEventData(eventText)}
              onClick={() => void send()}
            >
              <Send className="size-4" />
              {t('workflows.test.sendEvent')}
            </Button>
            <p className="text-xs text-muted-foreground">
              {t('workflows.test.mockHint')}
            </p>
          </div>
        )}
        <form
          className={cn('flex gap-2', eventMode && 'hidden')}
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <Input
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t('workflows.test.placeholder')}
            aria-label={t('workflows.test.placeholder')}
          />
          <Button
            type="submit"
            size="icon"
            disabled={running || !text.trim()}
            aria-label={t('workflows.test.send')}
          >
            <Send className="size-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}
