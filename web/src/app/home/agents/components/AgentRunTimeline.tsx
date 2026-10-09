import { useTranslation } from 'react-i18next';
import { MessageSquare, Send, Wrench } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { ProcessorPayload } from './PluginProcessorTrace';
import type { ExecutionStep } from './debug-execution';
import { toolDisplay, toolSummary } from './tool-summary';

export function isReplyStep(step: ExecutionStep) {
  return step.kind === 'tool' &&
    toolDisplay(step.name)?.kind === 'reply';
}

export function isMockStep(step: ExecutionStep) {
  return step.kind === 'tool' && !!step.result &&
    typeof step.result === 'object' && 'mock' in step.result && step.result.mock === true;
}

export default function AgentRunTimeline({ steps, labels, active }: {
  steps: ExecutionStep[];
  labels: Record<string, string>;
  active: boolean;
}) {
  const { t } = useTranslation();
  return (
    <ol className="space-y-0">
      {steps.map((step, index) => {
        const reply = isReplyStep(step);
        const mock = isMockStep(step);
        const params = step.kind === 'tool' && step.parameters && typeof step.parameters === 'object'
          ? step.parameters as Record<string, unknown> : {};
        const summary = toolSummary(step.kind === 'tool' ? step.name : '', params);
        const replyText = reply ? summary.text : '';
        const actionText = reply ? '' : summary.text;
        const Icon = step.kind === 'message' ? MessageSquare : reply ? Send : Wrench;
        const status = step.kind === 'tool' ? step.status : null;
        const statusKey = status === 'running' ? (active ? 'Running' : 'Interrupted')
          : mock ? (status === 'failed' ? 'MockFailed' : 'Simulated')
          : status === 'failed' ? 'Failed' : 'Completed';
        return (
          <li key={step.kind === 'tool' ? step.id : `message-${index}`} className="relative flex min-w-0 gap-3 pb-5 last:pb-0">
            {index < steps.length - 1 && <span className="absolute bottom-0 left-4 top-8 w-px bg-border" aria-hidden="true" />}
            <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-medium text-muted-foreground">{index + 1}</span>
            <div className="min-w-0 flex-1 rounded-lg border bg-background">
              <div className="flex flex-wrap items-center gap-2 border-b bg-muted/30 px-4 py-3">
                <Icon className="size-4 shrink-0 text-muted-foreground" />
                <h4 className="min-w-0 flex-1 break-words text-sm font-medium">
                  {step.kind === 'message' ? t('agents.debugTextOutput') : labels[step.name] || step.name}
                </h4>
                {status && <Badge status={status === 'failed' ? 'failed' : mock ? 'simulated' : status === 'running' && !active ? 'cancelled' : status}>{t(`agents.debugTool${statusKey}`)}</Badge>}
              </div>
              <div className="space-y-3 p-4 text-sm">
                {step.kind === 'message' ? <>
                  {step.text && <p className="whitespace-pre-wrap break-words leading-7 [overflow-wrap:anywhere]">{step.text}</p>}
                  {step.reasoning && <ProcessorPayload title={t('agents.debugReasoning')} value={step.reasoning} />}
                </> : <>
                  {replyText && <p className="whitespace-pre-wrap break-words leading-7 [overflow-wrap:anywhere]">{replyText}</p>}
                  {!reply && actionText && <p className="whitespace-pre-wrap break-words rounded-md bg-muted/50 p-3 font-mono text-xs leading-6 [overflow-wrap:anywhere]">{actionText}</p>}
                  {summary.recipient && <p className="break-all text-xs text-muted-foreground">{t('agents.monitoring.recipient')}: {summary.recipient}</p>}
                  {step.error && <p role="alert" className="whitespace-pre-wrap break-words text-destructive">{step.error}</p>}
                  {status === 'completed' && (mock || !reply) && <p className="text-xs text-muted-foreground">{t(`agents.monitoring.${mock ? 'simulatedAction' : 'actionCompleted'}`)}</p>}
                  {(step.parameters != null || step.result != null) && <div className="rounded-md border border-dashed text-muted-foreground">
                    {step.parameters != null && <ProcessorPayload title={t('agents.debugToolArguments')} value={step.parameters} />}
                    {step.result != null && <ProcessorPayload title={t('agents.debugToolResult')} value={step.result} />}
                  </div>}
                </>}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
