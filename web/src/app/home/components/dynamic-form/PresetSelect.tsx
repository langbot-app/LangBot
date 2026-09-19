import { useState } from 'react';
import { ControllerRenderProps } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export default function PresetSelect({
  config,
  field,
}: {
  config: IDynamicFormItemSchema;
  field: ControllerRenderProps;
}) {
  const { t } = useTranslation();
  const options = config.options?.filter((option) => option.name.trim()) ?? [];
  const presetIndex = options.findIndex(
    (option) => option.name === field.value,
  );
  // Selecting custom keeps the existing template until the user edits it.
  const [editingValue, setEditingValue] = useState<string | null>(null);
  const custom = presetIndex < 0 || editingValue === field.value;

  return (
    <div className="w-full max-w-md space-y-2">
      <Select
        value={custom ? 'custom' : `preset-${presetIndex}`}
        onValueChange={(value) => {
          if (value === 'custom') {
            setEditingValue(field.value ?? '');
          } else {
            setEditingValue(null);
            field.onChange(options[Number(value.slice(7))].name);
          }
        }}
      >
        <SelectTrigger
          className="w-full"
          onBlur={field.onBlur}
          disabled={field.disabled}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option, index) => (
            <SelectItem
              key={option.name}
              value={`preset-${index}`}
              description={option.name}
            >
              {extractI18nObject(option.label)}
            </SelectItem>
          ))}
          <SelectItem value="custom">{t('common.customValue')}</SelectItem>
        </SelectContent>
      </Select>
      {custom && (
        <Input
          {...field}
          value={field.value ?? ''}
          aria-label={`${extractI18nObject(config.label)} — ${t('common.customValue')}`}
          onChange={(event) => {
            setEditingValue(event.target.value);
            field.onChange(event.target.value);
          }}
        />
      )}
    </div>
  );
}
