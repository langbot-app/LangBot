import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, Cpu, MessageCircle, Send, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { ProcessorPayload } from '@/app/home/agents/components/PluginProcessorTrace';
import { toolSummary } from '@/app/home/agents/components/tool-summary';
import { MessageContentRenderer } from './MessageContentRenderer';
import { ConversationTurn } from '../utils/conversationTurns';

interface ConversationTurnListProps {
  turns: ConversationTurn[];
  expandedTurnId: string | null;
  onToggleTurn: (turnId: string) => void;
}

function formatDuration(ms: number) {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`;
}

function parsePayload(value?: string): unknown {
  if (!value) return null;
  try { return JSON.parse(value); } catch { return value; }
}

function MessageBody({ content }: { content: string }) {
  return (
    <div className="min-w-0 whitespace-pre-wrap break-words text-sm leading-7 [overflow-wrap:anywhere]">
      <MessageContentRenderer content={content} maxLines={0} />
    </div>
  );
}

export function ConversationTurnList({ turns, expandedTurnId, onToggleTurn }: ConversationTurnListProps) {
  const { t } = useTranslation();
  const turn = turns.find((item) => item.id === expandedTurnId) ?? turns[0];
  if (!turn) return null;

  const statusBadge = (status: ConversationTurn['status']) => (
    <Badge status={status} className="shrink-0">
      {t(`monitoring.pipelineTrace.${status}`)}
    </Badge>
  );
  const steps = [
    ...turn.llmCalls.map((call) => ({ kind: 'model' as const, call })),
    ...turn.toolCalls.map((call) => ({ kind: 'tool' as const, call })),
    ...turn.errors.map((call) => ({ kind: 'error' as const, call })),
  ].sort((a, b) => a.call.timestamp.getTime() - b.call.timestamp.getTime());

  return (
    <div className="grid min-h-0 gap-5 lg:h-full lg:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="min-h-0 lg:overflow-y-auto lg:pr-1">
        <div className="mb-3 text-sm font-medium">
          {t('monitoring.messageList.turns', { count: turns.length })}
        </div>
        <div className="max-h-72 overflow-y-auto rounded-xl border lg:max-h-none">
          {turns.map((item) => (
            <div
              key={item.id}
              role="button"
              tabIndex={0}
              aria-pressed={turn.id === item.id}
              onClick={() => onToggleTurn(item.id)}
              onKeyDown={(event) => {
                if (event.target === event.currentTarget && (event.key === 'Enter' || event.key === ' ')) {
                  event.preventDefault();
                  onToggleTurn(item.id);
                }
              }}
              className={cn(
                'cursor-pointer border-b border-l-2 border-l-transparent p-3 text-left last:border-b-0 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring',
                turn.id === item.id && 'border-l-primary bg-primary/5',
              )}
            >
              <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                <span className="truncate font-medium">{item.botName}</span>
                {statusBadge(item.status)}
              </div>
              <div className="pointer-events-none max-h-12 overflow-hidden break-words text-sm">
                {item.userMessage ? (
                  <MessageContentRenderer content={item.userMessage.messageContent} maxLines={2} />
                ) : t('monitoring.messageList.noUserMessage')}
              </div>
              <div className="mt-2 text-xs tabular-nums text-muted-foreground">
                {item.startedAt.toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </aside>

      <article key={turn.id} className="min-w-0 space-y-5 lg:overflow-y-auto lg:pr-2">
        <header className="space-y-3 border-b pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{turn.botName}</h3>
            {statusBadge(turn.status)}
            <span className="text-sm text-muted-foreground">{turn.userName || turn.userId}</span>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs tabular-nums text-muted-foreground">
            <span>{turn.startedAt.toLocaleString()}</span>
            <span>{t('monitoring.llmCalls.title')} {turn.llmCalls.length}</span>
            <span>{t('monitoring.toolCalls.title')} {turn.toolCalls.length}</span>
            <span>{t('monitoring.llmCalls.totalTokens')} {turn.totalTokens.toLocaleString()}</span>
          </div>
        </header>

        <section className="rounded-xl border p-4">
          <h4 className="mb-3 flex items-center gap-2 text-sm font-medium">
            <MessageCircle className="size-4 text-muted-foreground" />
            {t('monitoring.pipelineTrace.received')}
          </h4>
          {turn.userMessage ? <MessageBody content={turn.userMessage.messageContent} /> : (
            <p className="text-sm text-muted-foreground">{t('monitoring.messageList.noUserMessage')}</p>
          )}
        </section>

        <section>
          <h4 className="mb-3 text-sm font-medium">
            {t('monitoring.pipelineTrace.processing')}
            <span className="ml-2 font-normal text-muted-foreground">{steps.length}</span>
          </h4>
          {steps.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('monitoring.pipelineTrace.noSteps')}</p>
          ) : (
            <ol className="space-y-3">
              {steps.map((step, index) => {
                const { call } = step;
                const parameters = step.kind === 'tool' ? parsePayload(step.call.arguments) : null;
                const summary = step.kind === 'tool' && parameters && typeof parameters === 'object' && !Array.isArray(parameters)
                  ? toolSummary(step.call.toolName, parameters as Record<string, unknown>).text : '';
                return (
                  <li key={`${step.kind}:${call.id}`} className="relative flex gap-3">
                    {index < steps.length - 1 && <div className="absolute bottom-[-12px] left-4 top-8 w-px bg-border" />}
                    <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full border bg-background text-xs tabular-nums text-muted-foreground">{index + 1}</span>
                    <div className="min-w-0 flex-1 overflow-hidden rounded-xl border">
                      <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-4 py-3 text-sm">
                        {step.kind === 'model' ? <Cpu className="size-4" /> : step.kind === 'tool' ? <Wrench className="size-4" /> : <AlertCircle className="size-4 text-destructive" />}
                        <span className="min-w-0 flex-1 break-words font-medium">
                          {step.kind === 'model' ? step.call.modelName : step.kind === 'tool' ? step.call.toolName : step.call.errorType}
                        </span>
                        {statusBadge(step.kind === 'error' ? 'error' : step.call.status)}
                      </div>
                      <div className="space-y-3 p-4">
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs tabular-nums text-muted-foreground">
                          <span>{call.timestamp.toLocaleTimeString()}</span>
                          {step.kind !== 'error' && <span>{formatDuration(step.call.duration)}</span>}
                          {step.kind === 'tool' && <span>{step.call.toolSource}</span>}
                          {step.kind === 'model' && <>
                            <span>{t('monitoring.llmCalls.inputTokens')} {step.call.tokens.input.toLocaleString()}</span>
                            <span>{t('monitoring.llmCalls.outputTokens')} {step.call.tokens.output.toLocaleString()}</span>
                          </>}
                        </div>
                        {summary && <p className="whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">{summary}</p>}
                        {call.errorMessage && <p className="whitespace-pre-wrap break-words text-sm text-destructive [overflow-wrap:anywhere]">{call.errorMessage}</p>}
                        {step.kind === 'tool' && <div>
                          {step.call.arguments && <ProcessorPayload title={t('monitoring.toolCalls.arguments')} value={parameters} />}
                          {step.call.result && step.call.result !== 'null' && <ProcessorPayload title={t('monitoring.toolCalls.result')} value={parsePayload(step.call.result)} />}
                        </div>}
                        {step.kind === 'error' && step.call.stackTrace && <ProcessorPayload title={t('monitoring.unified.metadata')} value={step.call.stackTrace} />}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </section>

        <section className="rounded-xl border p-4">
          <h4 className="mb-3 flex items-center gap-2 text-sm font-medium">
            <Send className="size-4 text-muted-foreground" />
            {t('monitoring.pipelineTrace.replies')}
            <span className="font-normal text-muted-foreground">{turn.assistantMessages.length}</span>
          </h4>
          {turn.assistantMessages.length ? turn.assistantMessages.map((message) => (
            <div key={message.id} className="space-y-2 border-t py-3 first:border-t-0 first:pt-0 last:pb-0">
              <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                <span>{message.timestamp.toLocaleTimeString()}</span>
                {statusBadge(message.status)}
              </div>
              <MessageBody content={message.messageContent} />
            </div>
          )) : <p className="text-sm text-muted-foreground">{t('monitoring.messageList.noAssistantMessage')}</p>}
        </section>
        <ProcessorPayload title={t('monitoring.unified.metadata')} value={{
          turn_id: turn.id, session_id: turn.sessionId, bot: turn.botName,
          pipeline: turn.pipelineName, runner: turn.runnerName, platform: turn.platform,
          user_id: turn.userId, messages: turn.messages,
        }} />
      </article>
    </div>
  );
}
