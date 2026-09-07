import { useState } from 'react';
import { Settings2, Puzzle } from 'lucide-react';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/popover';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { EventProcessorDescriptor } from '@/app/infra/entities/api';
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
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';

function ProcessorComponentContent({
  component,
  option = false,
}: {
  component: EventProcessorDescriptor;
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

export default function EventProcessorSettings({
  components,
  value,
  parameters,
  onChange,
  onParametersChange,
  onValidate,
  disabled = false,
}: {
  components: EventProcessorDescriptor[];
  value: string;
  parameters: Record<string, unknown>;
  onChange: (value: string) => void;
  onParametersChange: (value: Record<string, unknown>) => void;
  onValidate?: (validate: () => Promise<boolean>) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const selected = components.find((item) => item.id === value);
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <div className="flex min-w-0 items-center gap-2">
      <Label className="sr-only" htmlFor="event-processor-component">
        {t('agents.eventProcessor.component')}
      </Label>
      <Select
        value={value}
        disabled={disabled}
        onValueChange={(next) => {
          onChange(next);
          const component = components.find((item) => item.id === next);
          setSettingsOpen(
            Boolean(
              component?.config_schema.some(
                (field) =>
                  field.required &&
                  (field.default == null || field.default === ''),
              ),
            ),
          );
        }}
      >
        <SelectTrigger
          id="event-processor-component"
          className="w-[22rem] max-w-[calc(100vw-8rem)] bg-[#ffffff] dark:bg-[#2a2a2e]"
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
      {selected && selected.config_schema.length > 0 && (
        <Popover open={settingsOpen} onOpenChange={setSettingsOpen}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              disabled={disabled}
              aria-label={t('agents.eventProcessor.pluginSettings')}
              title={t('agents.eventProcessor.pluginSettings')}
            >
              <Settings2 className="size-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            align="start"
            className="max-h-[70vh] overflow-y-auto space-y-3"
          >
            <p className="text-sm font-medium">
              {t('agents.eventProcessor.pluginSettings')}
            </p>
            <p className="text-xs text-muted-foreground">
              {t('agents.eventProcessor.pluginSettingsDescription')}
            </p>
            <fieldset disabled={disabled}>
              <DynamicFormComponent
                key={value}
                itemConfigList={selected.config_schema}
                initialValues={parameters}
                onSubmit={(values) =>
                  onParametersChange(values as Record<string, unknown>)
                }
                onValidate={onValidate}
              />
            </fieldset>
          </PopoverContent>
        </Popover>
      )}
    </div>
  );
}
