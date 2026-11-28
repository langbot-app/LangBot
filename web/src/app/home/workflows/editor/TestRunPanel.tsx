import { useEffect, useRef, useState } from 'react';
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
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState('');
  const [sessionType, setSessionType] = useState<'person' | 'group'>('person');
  const [running, setRunning] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' });
  }, [turns, running]);

  const send = async () => {
    const message = text.trim();
    if (!message || running) return;
    setText('');
    setRunning(true);
    setTurns((current) => [...current, { text: message }]);
    try {
      const result = await backendClient.testWorkflow(workflowId, {
        text: message,
        session_type: sessionType,
        graph,
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
        <div className="flex items-center justify-between">
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
        <form
          className="flex gap-2"
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
