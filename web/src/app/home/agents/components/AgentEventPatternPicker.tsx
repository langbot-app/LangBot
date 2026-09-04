import { useMemo, useState } from 'react';
import { Check, ChevronDown, Plus, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentPlatformTool } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  eventGroupLabel,
  eventNamespaces,
  eventPatternDescription,
  eventPatternLabel,
  groupEventPatterns,
} from '@/app/home/components/event-patterns/event-pattern-groups';

const FALLBACK_EVENTS = ['message.received'];

interface AgentEventPatternPickerProps {
  events: string[];
  value: string[];
  onChange: (patterns: string[]) => void;
  tools: AgentPlatformTool[];
  catalogAvailable?: boolean;
}

function eventPatternsIntersect(left: string, right: string) {
  if (left === '*' || right === '*' || left === right) return true;
  if (!left.includes('*')) {
    return right.endsWith('.*') && left.startsWith(right.slice(0, -1));
  }
  if (!right.includes('*')) {
    return left.endsWith('.*') && right.startsWith(left.slice(0, -1));
  }
  const leftPrefix = left.slice(0, left.indexOf('*'));
  const rightPrefix = right.slice(0, right.indexOf('*'));
  return (
    leftPrefix.startsWith(rightPrefix) || rightPrefix.startsWith(leftPrefix)
  );
}

export function isEventToolCompatibleWithPattern(
  tool: AgentPlatformTool,
  pattern: string,
) {
  return (
    tool.scope === 'event' &&
    tool.event_patterns.some((toolPattern) =>
      eventPatternsIntersect(toolPattern, pattern),
    )
  );
}

export default function AgentEventPatternPicker({
  events,
  value,
  onChange,
  tools,
  catalogAvailable = true,
}: AgentEventPatternPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [expandedPatterns, setExpandedPatterns] = useState<Set<string>>(
    new Set(),
  );
  const selectedPatterns = value;
  const eventTools = useMemo(
    () => tools.filter((tool) => tool.scope === 'event'),
    [tools],
  );
  const options = useMemo(() => {
    const concreteEvents = Array.from(
      new Set([
        ...(events.length > 0 ? events : FALLBACK_EVENTS),
        ...selectedPatterns.filter(
          (pattern) => pattern !== '*' && !pattern.endsWith('.*'),
        ),
      ]),
    ).sort();
    const namespaces = Array.from(
      new Set([
        ...eventNamespaces(concreteEvents),
        ...selectedPatterns.filter((pattern) => pattern.endsWith('.*')),
      ]),
    ).sort();
    return ['*', ...namespaces, ...concreteEvents].filter(
      (pattern) => !selectedPatterns.includes(pattern),
    );
  }, [events, selectedPatterns]);
  const optionGroups = useMemo(() => groupEventPatterns(options), [options]);

  function addPattern(pattern: string) {
    let nextPatterns: string[];
    if (pattern === '*') {
      nextPatterns = ['*'];
    } else {
      const namespace = pattern.split('.')[0];
      nextPatterns = selectedPatterns.filter((item) => {
        if (item === '*') {
          return false;
        }
        const overlaps = pattern.endsWith('.*')
          ? item.split('.')[0] === namespace
          : item === `${namespace}.*`;
        return !overlaps;
      });
      nextPatterns.push(pattern);
    }

    onChange(Array.from(new Set(nextPatterns)));
    setOpen(false);
  }

  function removePattern(pattern: string) {
    onChange(selectedPatterns.filter((item) => item !== pattern));
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-background">
      <div className="flex items-center justify-between gap-3 border-b bg-muted/30 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">{t('agents.configuredEvents')}</p>
          <p className="text-xs text-muted-foreground">
            {t('agents.configuredEventsCount', {
              count: selectedPatterns.length,
            })}
          </p>
        </div>
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5"
            >
              <Plus className="size-4" />
              {t('agents.addEvent')}
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-96 max-w-[90vw] p-0">
            <Command>
              <CommandInput placeholder={t('agents.searchEvents')} />
              <CommandList>
                <CommandEmpty>{t('agents.noEventsFound')}</CommandEmpty>
                {optionGroups.map((group) => (
                  <CommandGroup
                    key={group.namespace}
                    heading={eventGroupLabel(group.namespace, t)}
                  >
                    {group.patterns.map((pattern) => (
                      <CommandItem
                        key={pattern}
                        value={`${eventPatternLabel(pattern, t)} ${pattern}`}
                        onSelect={() => addPattern(pattern)}
                        className="items-start gap-2 py-2"
                      >
                        <Plus className="mt-0.5 size-4 shrink-0" />
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 items-center gap-2">
                            <span className="truncate font-medium">
                              {eventPatternLabel(pattern, t)}
                            </span>
                            <code className="shrink-0 text-[10px] text-muted-foreground">
                              {pattern}
                            </code>
                          </span>
                          <span className="mt-0.5 block text-xs text-muted-foreground">
                            {eventPatternDescription(pattern, t)}
                          </span>
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                ))}
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      </div>

      <div className="divide-y">
        {selectedPatterns.length === 0 && (
          <div className="px-4 py-8 text-center">
            <p className="text-sm font-medium">
              {t('agents.noEventsConfigured')}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {t('agents.noEventsConfiguredDescription')}
            </p>
          </div>
        )}
        {selectedPatterns.map((pattern) => {
          const compatibleTools = eventTools.filter((tool) =>
            isEventToolCompatibleWithPattern(tool, pattern),
          );
          return (
            <Collapsible
              key={pattern}
              open={expandedPatterns.has(pattern)}
              onOpenChange={(expanded) => {
                setExpandedPatterns((current) => {
                  const next = new Set(current);
                  if (expanded) next.add(pattern);
                  else next.delete(pattern);
                  return next;
                });
              }}
            >
              <div className="flex items-center gap-1 bg-muted/20 px-3 py-2">
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-3 rounded-md px-1 py-1 text-left hover:bg-muted/50"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="flex min-w-0 items-baseline gap-2">
                        <span className="truncate text-sm font-medium">
                          {eventPatternLabel(pattern, t)}
                        </span>
                        <code className="shrink-0 text-[11px] text-muted-foreground">
                          {pattern}
                        </code>
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                        {eventPatternDescription(pattern, t)}
                      </span>
                    </span>
                    <span className="shrink-0 text-xs text-emerald-700 dark:text-emerald-300">
                      {t('agents.eventToolsEnabledCount', {
                        count: compatibleTools.length,
                      })}
                    </span>
                    <ChevronDown
                      className={cn(
                        'size-4 shrink-0 text-muted-foreground transition-transform',
                        expandedPatterns.has(pattern) && 'rotate-180',
                      )}
                    />
                  </button>
                </CollapsibleTrigger>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removePattern(pattern)}
                  aria-label={t('agents.removeEvent')}
                  className="size-8 shrink-0 text-muted-foreground"
                >
                  <X className="size-4" />
                </Button>
              </div>

              <CollapsibleContent className="border-t px-3 py-2.5">
                {!catalogAvailable ? (
                  <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
                    {t('agents.apiToolsCatalogUnavailable')}
                  </div>
                ) : compatibleTools.length === 0 ? (
                  <p className="rounded-lg border border-dashed px-3 py-4 text-center text-sm text-muted-foreground">
                    {t('agents.noEventActions')}
                  </p>
                ) : (
                  <div className="overflow-hidden rounded-lg border bg-background">
                    <div className="divide-y">
                      {compatibleTools.map((tool) => {
                        const label = extractI18nObject(tool.label);
                        return (
                          <div
                            key={tool.name}
                            className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3 bg-background px-3 py-2.5"
                          >
                            <span className="min-w-0">
                              <span className="flex min-w-0 items-center gap-2 text-sm font-medium leading-5">
                                <span className="truncate">{label}</span>
                                <span className="shrink-0 text-xs font-normal text-muted-foreground">
                                  {t(`agents.apiToolRisk.${tool.risk}`)}
                                </span>
                              </span>
                            </span>
                            <span className="flex shrink-0 items-center gap-1 pt-0.5 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                              <Check className="size-3.5" />
                              {t('agents.eventToolEnabled')}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>
    </div>
  );
}
