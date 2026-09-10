import { Puzzle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { RunnerDescriptor } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

function ProcessorComponentContent({
  component,
  option = false,
}: {
  component: RunnerDescriptor;
  option?: boolean;
}) {
  const label = extractI18nObject({
    en_US: component.id,
    zh_Hans: component.id,
    ...component.label,
  });
  const pluginId = `${component.plugin_author}/${component.plugin_name}`;
  return (
    <span
      className={
        option
          ? 'grid w-full min-w-0 grid-cols-[1.75rem_minmax(0,1fr)] items-center gap-x-2 text-left'
          : 'flex min-w-0 items-center gap-2'
      }
    >
      <img
        src={httpClient.getPluginIconURL(
          component.plugin_author,
          component.plugin_name,
        )}
        alt=""
        className={
          option
            ? 'row-span-2 size-7 shrink-0 rounded-md object-cover'
            : 'size-5 shrink-0 rounded object-cover'
        }
      />
      <span className={option ? 'truncate font-medium leading-5' : 'truncate'}>
        {label}
      </span>
      {option && (
        <span
          className="truncate text-xs leading-4 text-muted-foreground"
          title={pluginId}
        >
          {pluginId}
        </span>
      )}
    </span>
  );
}

export default function PluginProcessorSettings({
  components,
  value,
  onChange,
  disabled = false,
}: {
  components: RunnerDescriptor[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const selected = components.find((item) => item.id === value);
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Label className="sr-only" htmlFor="event-processor-component">
        {t('agents.eventProcessor.component')}
      </Label>
      <Select value={value} disabled={disabled} onValueChange={onChange}>
        <SelectTrigger
          id="event-processor-component"
          className="w-[13.2rem] max-w-[calc(100vw-8rem)] bg-[#ffffff] dark:bg-[#2a2a2e]"
        >
          {selected ? (
            <ProcessorComponentContent component={selected} />
          ) : (
            <span className="flex min-w-0 items-center gap-2">
              <Puzzle className="size-4 shrink-0 text-muted-foreground" />
              <SelectValue
                placeholder={t('agents.eventProcessor.selectComponent')}
              />
            </span>
          )}
        </SelectTrigger>
        <SelectContent className="max-h-72 w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-2rem)]">
          {value && !selected && (
            <SelectItem value={value}>
              {t('agents.eventProcessor.unavailable')}
            </SelectItem>
          )}
          {components.map((component) => (
            <SelectItem
              key={component.id}
              value={component.id}
              className="py-1.5 [&>span:last-child]:min-w-0 [&>span:last-child]:flex-1"
            >
              <ProcessorComponentContent component={component} option />
            </SelectItem>
          ))}
          {components.length === 0 && (
            <div className="p-2 text-sm text-muted-foreground">
              {t('agents.eventProcessor.noComponents')}
              <Button asChild variant="link" className="h-auto px-0">
                <Link to="/home/plugins">
                  {t('agents.eventProcessor.installPlugin')}
                </Link>
              </Button>
            </div>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}
