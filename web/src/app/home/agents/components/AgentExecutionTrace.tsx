import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Brain, MessageSquare, Wrench } from 'lucide-react';
import { executionSteps, type DebugExecutionEvent } from './debug-execution';

function formatValue(value: unknown) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function isMockResult(value: unknown): boolean {
  return (
    typeof value === 'object' &&
    value !== null &&
    'mock' in value &&
    value.mock === true
  );
}

const textClass =
  'whitespace-pre-wrap break-words [overflow-wrap:anywhere] font-sans text-sm leading-relaxed';

export default function AgentExecutionTrace({
  events,
  finished = false,
  toolLabels = {},
}: {
  events: DebugExecutionEvent[];
  finished?: boolean;
  toolLabels?: Record<string, string>;
}) {
  const { t } = useTranslation();
  const steps = useMemo(() => executionSteps(events), [events]);
  const toolCount = steps.filter((step) => step.kind === 'tool').length;
  const ended =
    finished ||
    events.some((event) =>
      ['run.completed', 'run.failed'].includes(event.type),
    );
  return (
    <div className="min-w-0 space-y-3">
      {ended && toolCount > 0 && (
        <p className="text-xs text-muted-foreground">
          {t('agents.debugToolCount', {
            count: toolCount,
          })}
        </p>
      )}
      {steps.map((step, index) =>
        step.kind === 'message' ? (
          <div key={index} className="space-y-3">
            {step.reasoning && (
              <details open className="rounded-md border bg-muted/30 p-3">
                <summary className="cursor-pointer text-xs font-medium text-muted-foreground">
                  <Brain className="mr-1.5 inline size-3.5" />
                  {t('agents.debugReasoning')}
                </summary>
                <pre className={`${textClass} mt-2 text-muted-foreground`}>
                  {step.reasoning}
                </pre>
              </details>
            )}
            {step.text && (
              <section className="space-y-2">
                <p className="text-xs font-medium">
                  <MessageSquare className="mr-1.5 inline size-3.5" />
                  {t('agents.debugTextOutput')}
                </p>
                <pre className={textClass}>{step.text}</pre>
              </section>
            )}
          </div>
        ) : (
          <details
            key={index}
            className="min-w-0 rounded-md border bg-background p-3"
          >
            <summary className="cursor-pointer text-xs">
              <span className="min-w-0 break-all font-medium">
                <Wrench className="mr-1.5 inline size-3.5" />
                {toolLabels[step.name] || step.name}
              </span>
              {toolLabels[step.name] && toolLabels[step.name] !== step.name && (
                <code className="ml-2 break-all font-mono text-xs text-muted-foreground">
                  {step.name}
                </code>
              )}
            </summary>
            <div className="mt-2 space-y-2">
              <span
                className={
                  step.status === 'failed'
                    ? 'text-destructive'
                    : 'text-muted-foreground'
                }
              >
                {isMockResult(step.result)
                  ? t(
                      step.status === 'failed'
                        ? 'agents.debugToolMockFailed'
                        : 'agents.debugToolSimulated',
                    )
                  : t(
                      step.status === 'running'
                        ? ended
                          ? 'agents.debugToolInterrupted'
                          : 'agents.debugToolRunning'
                        : step.status === 'failed'
                          ? 'agents.debugToolFailed'
                          : 'agents.debugToolCompleted',
                    )}
              </span>
              {step.parameters !== undefined && (
                <div>
                  <p className="text-xs text-muted-foreground">
                    {t('agents.debugToolArguments')}
                  </p>
                  <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-muted/40 p-2 font-mono text-xs">
                    {formatValue(step.parameters)}
                  </pre>
                </div>
              )}
              {step.result !== undefined && step.result !== null && (
                <div>
                  <p className="text-xs text-muted-foreground">
                    {t('agents.debugToolResult')}
                  </p>
                  <pre className="mt-1 whitespace-pre-wrap break-all rounded bg-muted/40 p-2 font-mono text-xs">
                    {formatValue(step.result)}
                  </pre>
                </div>
              )}
              {step.error && (
                <pre className={`${textClass} text-destructive`}>
                  {step.error}
                </pre>
              )}
            </div>
          </details>
        ),
      )}
    </div>
  );
}
