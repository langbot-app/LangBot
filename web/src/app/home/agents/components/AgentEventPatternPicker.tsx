import { useMemo, useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
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
import { cn } from '@/lib/utils';
import {
  eventGroupLabel,
  eventNamespaces,
  groupEventPatterns,
} from '@/app/home/components/event-patterns/event-pattern-groups';

const FALLBACK_EVENTS = ['message.received'];

interface AgentEventPatternPickerProps {
  events: string[];
  value: string[];
  onChange: (patterns: string[]) => void;
}

export default function AgentEventPatternPicker({
  events,
  value,
  onChange,
}: AgentEventPatternPickerProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const selectedPatterns = useMemo(
    () => (value.length > 0 ? value : ['*']),
    [value],
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
    return ['*', ...namespaces, ...concreteEvents];
  }, [events, selectedPatterns]);
  const optionGroups = useMemo(() => groupEventPatterns(options), [options]);

  function eventLabel(pattern: string) {
    if (pattern === '*') return t('bots.eventWildcard');
    if (pattern.endsWith('.*')) {
      return t('bots.eventNamespaceWildcard', {
        namespace: pattern.replace('.*', ''),
      });
    }
    const key = `bots.eventNames.${pattern.replace(/\./g, '_')}`;
    const label = t(key);
    return label === key ? pattern : label;
  }

  function eventDescription(pattern: string) {
    if (pattern === '*') return t('bots.eventDescriptions.all');
    if (pattern.endsWith('.*')) {
      return t('bots.eventDescriptions.namespace');
    }
    const key = `bots.eventDescriptions.${pattern.replace(/\./g, '_')}`;
    const description = t(key);
    return description === key
      ? t('bots.eventDescriptions.custom')
      : description;
  }

  function togglePattern(pattern: string) {
    if (pattern === '*') {
      onChange(['*']);
      return;
    }

    if (selectedPatterns.includes(pattern)) {
      const next = selectedPatterns.filter((item) => item !== pattern);
      onChange(next.length > 0 ? next : ['*']);
      return;
    }

    let next = selectedPatterns.filter((item) => item !== '*');
    const namespace = pattern.split('.')[0];
    if (pattern.endsWith('.*')) {
      next = next.filter(
        (item) => item.split('.')[0] !== namespace || item.endsWith('.*'),
      );
    } else {
      next = next.filter((item) => item !== `${namespace}.*`);
    }
    onChange(Array.from(new Set([...next, pattern])));
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label={t('agents.supportedEvents')}
          className="h-auto min-h-10 w-full min-w-0 justify-between gap-2 px-3 py-2 font-normal"
        >
          <span className="flex min-w-0 flex-1 flex-wrap gap-1.5">
            {selectedPatterns.slice(0, 3).map((pattern) => (
              <Badge
                key={pattern}
                variant="secondary"
                className="max-w-full rounded-md font-normal"
              >
                <span className="truncate">{eventLabel(pattern)}</span>
              </Badge>
            ))}
            {selectedPatterns.length > 3 && (
              <Badge variant="outline" className="rounded-md font-normal">
                +{selectedPatterns.length - 3}
              </Badge>
            )}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-trigger-width)] p-0"
      >
        <Command>
          <CommandInput placeholder={t('agents.searchEvents')} />
          <CommandList>
            <CommandEmpty>{t('agents.noEventsFound')}</CommandEmpty>
            {optionGroups.map((group) => (
              <CommandGroup
                key={group.namespace}
                heading={eventGroupLabel(group.namespace, t)}
              >
                {group.patterns.map((pattern) => {
                  const selected = selectedPatterns.includes(pattern);
                  return (
                    <CommandItem
                      key={pattern}
                      value={`${eventLabel(pattern)} ${pattern}`}
                      onSelect={() => togglePattern(pattern)}
                      className="items-start gap-2 py-2"
                    >
                      <Check
                        className={cn(
                          'mt-0.5 size-4 shrink-0',
                          selected ? 'opacity-100' : 'opacity-0',
                        )}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex min-w-0 items-center gap-2">
                          <span className="truncate font-medium">
                            {eventLabel(pattern)}
                          </span>
                          <code className="shrink-0 text-[10px] text-muted-foreground">
                            {pattern}
                          </code>
                        </span>
                        <span className="mt-0.5 block text-xs text-muted-foreground">
                          {eventDescription(pattern)}
                        </span>
                      </span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
