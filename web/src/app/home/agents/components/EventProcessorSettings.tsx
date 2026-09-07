import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { EventProcessorDescriptor } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';

export default function EventProcessorSettings({
  components,
  value,
  parameters,
  onChange,
  onParametersChange,
  onValidate,
}: {
  components: EventProcessorDescriptor[];
  value: string;
  parameters: Record<string, unknown>;
  onChange: (value: string) => void;
  onParametersChange: (value: Record<string, unknown>) => void;
  onValidate?: (validate: () => Promise<boolean>) => void;
}) {
  const { t } = useTranslation();
  const selected = components.find((item) => item.id === value);
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label
          className="text-sm font-medium"
          htmlFor="event-processor-component"
        >
          {t('agents.eventProcessor.component')}
        </label>
        <Select value={value} onValueChange={onChange}>
          <SelectTrigger id="event-processor-component">
            <SelectValue
              placeholder={t('agents.eventProcessor.selectComponent')}
            />
          </SelectTrigger>
          <SelectContent>
            {value && !selected && (
              <SelectItem value={value}>
                {t('agents.eventProcessor.unavailable')}
              </SelectItem>
            )}
            {components.map((component) => (
              <SelectItem key={component.id} value={component.id}>
                {extractI18nObject({
                  en_US: component.id,
                  zh_Hans: component.id,
                  ...component.label,
                })}{' '}
                · {component.plugin_author}/{component.plugin_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {components.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {t('agents.eventProcessor.noComponents')}{' '}
            <Link className="text-primary underline" to="/home/plugins">
              {t('agents.eventProcessor.installPlugin')}
            </Link>
          </p>
        )}
      </div>
      {selected && (
        <p className="break-words text-xs text-muted-foreground">
          {selected.supported_event_patterns.join(' · ')}
        </p>
      )}
      {selected && selected.config_schema.length > 0 && (
        <DynamicFormComponent
          key={value}
          itemConfigList={selected.config_schema}
          initialValues={parameters}
          onSubmit={(values) =>
            onParametersChange(values as Record<string, unknown>)
          }
          onValidate={onValidate}
        />
      )}
    </div>
  );
}
