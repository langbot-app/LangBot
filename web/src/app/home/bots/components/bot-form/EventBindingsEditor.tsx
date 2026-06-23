'use client';

import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { UseFormReturn } from 'react-hook-form';
import { Ban, Bot, Plus, Trash2, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { FormLabel } from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EventBinding, Agent, AgentKind } from '@/app/infra/entities/api';

interface EventBindingsEditorProps {
  form: UseFormReturn<any>;
  supportedEvents: string[];
  agentOptions: Agent[];
}

const DEFAULT_EVENTS = [
  'message.received',
  'feedback.received',
  'group.member_joined',
  'group.member_left',
  'friend.request_received',
  'bot.invited_to_group',
  'platform.specific',
];

function isMessageEventPattern(pattern: string): boolean {
  return pattern === 'message.*' || pattern.startsWith('message.');
}

function eventPatternCovers(
  supportedPattern: string,
  bindingPattern: string,
): boolean {
  if (supportedPattern === '*') return true;
  if (supportedPattern === bindingPattern) return true;
  if (bindingPattern === '*') return false;
  if (supportedPattern.endsWith('.*')) {
    const namespace = supportedPattern.replace('.*', '');
    return (
      bindingPattern === `${namespace}.*` ||
      bindingPattern.startsWith(`${namespace}.`)
    );
  }
  return false;
}

function agentSupportsEventPattern(
  agent: Agent,
  bindingPattern: string,
): boolean {
  const patterns = agent.supported_event_patterns ??
    agent.capability?.supported_event_patterns ?? ['*'];
  return patterns.some((pattern) =>
    eventPatternCovers(pattern, bindingPattern),
  );
}

function eventNamespaces(events: string[]): string[] {
  const namespaces = new Set<string>();
  for (const event of events) {
    const namespace = event.split('.')[0];
    if (namespace) namespaces.add(`${namespace}.*`);
  }
  return Array.from(namespaces).sort();
}

function targetLabel(agent: Agent): string {
  return `${agent.emoji ? `${agent.emoji} ` : ''}${agent.name}`;
}

export default function EventBindingsEditor({
  form,
  supportedEvents,
  agentOptions,
}: EventBindingsEditorProps) {
  const { t } = useTranslation();
  const bindings: EventBinding[] = form.watch('event_bindings') || [];

  const eventOptions = useMemo(() => {
    const concreteEvents =
      supportedEvents.length > 0 ? supportedEvents : DEFAULT_EVENTS;
    return ['*', ...eventNamespaces(concreteEvents), ...concreteEvents].filter(
      (event, index, list) => list.indexOf(event) === index,
    );
  }, [supportedEvents]);

  function updateBindings(nextBindings: EventBinding[]) {
    form.setValue('event_bindings', nextBindings, { shouldDirty: true });
  }

  function addBinding() {
    updateBindings([
      ...bindings,
      {
        event_pattern: 'message.received',
        target_type: 'agent',
        target_uuid: '',
        priority: bindings.length,
        enabled: true,
        description: '',
        filters: [],
      },
    ]);
  }

  function updateBinding(index: number, patch: Partial<EventBinding>) {
    const updated = [...bindings];
    updated[index] = { ...updated[index], ...patch };
    updateBindings(updated);
  }

  function removeBinding(index: number) {
    const updated = [...bindings];
    updated.splice(index, 1);
    updateBindings(updated);
  }

  function getTargetOptions(binding: EventBinding, kind: AgentKind): Agent[] {
    return agentOptions.filter((agent) => {
      if (agent.kind !== kind) return false;
      if (kind === 'pipeline') {
        return isMessageEventPattern(binding.event_pattern);
      }
      if (kind === 'agent') {
        return agentSupportsEventPattern(agent, binding.event_pattern);
      }
      return true;
    });
  }

  return (
    <div className="mt-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <FormLabel>{t('bots.eventBindings')}</FormLabel>
          <p className="text-sm text-muted-foreground mt-1">
            {t('bots.eventOrchestrationDescription')}
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={addBinding}>
          <Plus className="h-4 w-4 mr-1" />
          {t('bots.addEventBinding')}
        </Button>
      </div>

      {bindings.length === 0 && (
        <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
          {t('bots.noEventBindings')}
        </div>
      )}

      <div className="space-y-2">
        {bindings.map((binding, index) => {
          const pipelineAllowed = isMessageEventPattern(binding.event_pattern);
          const targetType = binding.target_type || 'agent';
          const targetOptions =
            targetType === 'discard'
              ? []
              : getTargetOptions(binding, targetType as AgentKind);

          return (
            <div
              key={binding.id ?? index}
              className="grid gap-2 rounded-md border bg-muted/30 p-3 lg:grid-cols-[1.2fr_0.9fr_1.4fr_80px_72px_36px]"
            >
              <Select
                value={binding.event_pattern}
                onValueChange={(eventPattern) => {
                  const patch: Partial<EventBinding> = {
                    event_pattern: eventPattern,
                  };
                  if (
                    binding.target_type === 'pipeline' &&
                    !isMessageEventPattern(eventPattern)
                  ) {
                    patch.target_type = 'agent';
                    patch.target_uuid = '';
                  }
                  updateBinding(index, patch);
                }}
              >
                <SelectTrigger>
                  <SelectValue
                    placeholder={t('bots.eventPatternPlaceholder')}
                  />
                </SelectTrigger>
                <SelectContent>
                  {eventOptions.map((event) => (
                    <SelectItem key={event} value={event}>
                      {event === '*'
                        ? t('bots.eventWildcard')
                        : event.endsWith('.*')
                          ? t('bots.eventNamespaceWildcard', {
                              namespace: event.replace('.*', ''),
                            })
                          : event}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={targetType}
                onValueChange={(nextType) => {
                  updateBinding(index, {
                    target_type: nextType as EventBinding['target_type'],
                    target_uuid: '',
                  });
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="agent">
                    <div className="flex items-center gap-2">
                      <Bot className="size-3.5" />
                      {t('bots.targetAgent')}
                    </div>
                  </SelectItem>
                  <SelectItem value="pipeline" disabled={!pipelineAllowed}>
                    <div className="flex items-center gap-2">
                      <Workflow className="size-3.5" />
                      {t('bots.targetPipeline')}
                    </div>
                  </SelectItem>
                  <SelectSeparator />
                  <SelectItem value="discard">
                    <div className="flex items-center gap-2 text-destructive">
                      <Ban className="size-3.5" />
                      {t('bots.targetDiscard')}
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              {targetType === 'discard' ? (
                <div className="flex items-center rounded-md border bg-background px-3 text-sm text-destructive">
                  <Ban className="mr-2 size-3.5" />
                  {t('bots.targetDiscard')}
                </div>
              ) : (
                <Select
                  value={binding.target_uuid}
                  onValueChange={(targetUuid) =>
                    updateBinding(index, { target_uuid: targetUuid })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('bots.selectTarget')} />
                  </SelectTrigger>
                  <SelectContent>
                    {targetOptions.map((agent) => (
                      <SelectItem key={agent.uuid} value={agent.uuid || ''}>
                        {targetLabel(agent)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}

              <Input
                type="number"
                value={binding.priority ?? 0}
                onChange={(event) =>
                  updateBinding(index, {
                    priority: Number(event.target.value || 0),
                  })
                }
                aria-label={t('bots.priority')}
              />

              <div className="flex items-center justify-center rounded-md border bg-background">
                <Switch
                  checked={binding.enabled ?? true}
                  onCheckedChange={(enabled) =>
                    updateBinding(index, { enabled })
                  }
                  aria-label={t('bots.enabled')}
                />
              </div>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeBinding(index)}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>

              {!pipelineAllowed && binding.target_type === 'pipeline' && (
                <div className="lg:col-span-6 text-xs text-destructive">
                  {t('bots.unsupportedPipelineEvent')}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
