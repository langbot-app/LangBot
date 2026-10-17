import { useTranslation } from 'react-i18next';
import type { RunnerDescriptor } from '@/app/infra/entities/api';
import RunnerSelect from './RunnerSelect';

export default function PluginProcessorSettings({
  components,
  value,
  onChange,
  disabled = false,
  installScope,
  onInstalled,
}: {
  components: RunnerDescriptor[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  installScope: string;
  onInstalled: (component: RunnerDescriptor) => void;
}) {
  const { t } = useTranslation();
  const options = components.map((component) => ({
    name: component.id,
    label: { en_US: component.id, zh_Hans: component.id, ...component.label },
  }));
  if (value && !components.some((component) => component.id === value))
    options.push({
      name: value,
      label: {
        en_US: t('agents.eventProcessor.unavailable'),
        zh_Hans: t('agents.eventProcessor.unavailable'),
      },
    });
  return (
    <div
      id="event-processor-component"
      className="w-[20rem] max-w-[calc(100vw-8rem)]"
    >
      <RunnerSelect
        usage="event"
        options={options}
        value={value}
        label={t('agents.eventProcessor.component')}
        disabled={disabled}
        installScope={installScope}
        onValueChange={onChange}
        onEventProcessorInstalled={onInstalled}
      />
    </div>
  );
}
