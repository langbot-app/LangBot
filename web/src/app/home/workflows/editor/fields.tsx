import { useState, type ReactNode } from 'react';
import { Input } from '@/components/ui/input';
import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useEditor } from './EditorContext';

export function Field({
  label,
  hint,
  error,
  children,
  action,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <Label className="text-sm font-medium">{label}</Label>
        {action}
      </div>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

/** First error message reported for a step field (or any nested path of it). */
export function useFieldError(stepId: string) {
  const { t } = useTranslation();
  const { issues } = useEditor();
  return (field: string) => {
    const issue = issues.find(
      (item) =>
        item.node_id === stepId &&
        item.severity === 'error' &&
        (item.field === field ||
          item.field === `config.${field}` ||
          item.field?.startsWith(`config.${field}.`)),
    );
    return issue
      ? t(`workflows.issues.${issue.code}`, { defaultValue: issue.code })
      : undefined;
  };
}

export function ModelSelect({
  value,
  onChange,
  invalid,
  kind = 'llm',
}: {
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  kind?: 'llm' | 'tts' | 'asr';
}) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  const models =
    kind === 'tts'
      ? resources.ttsModels
      : kind === 'asr'
        ? resources.asrModels
        : resources.models;
  if (!models.length) {
    return (
      <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
        {t(`workflows.form.noModels${kind === 'llm' ? '' : 'Speech'}`)}
      </p>
    );
  }
  return (
    <Select value={value || undefined} onValueChange={onChange}>
      <SelectTrigger
        className={cn('w-full', invalid && 'border-destructive')}
        aria-label={t('workflows.form.model')}
      >
        <SelectValue placeholder={t('workflows.form.pickModel')} />
      </SelectTrigger>
      <SelectContent>
        {models.map((model) => (
          <SelectItem key={model.uuid} value={model.uuid!}>
            {model.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function OptionSelect({
  value,
  options,
  onChange,
  ariaLabel,
  className,
}: {
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className={cn('w-full', className)} aria-label={ariaLabel}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function GroupedSelect({
  value,
  groups,
  onChange,
  placeholder,
  invalid,
}: {
  value: string;
  groups: { label: string; options: { value: string; label: string }[] }[];
  onChange: (value: string) => void;
  placeholder: string;
  invalid?: boolean;
}) {
  return (
    <Select value={value || undefined} onValueChange={onChange}>
      <SelectTrigger className={cn('w-full', invalid && 'border-destructive')}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {groups
          .filter((group) => group.options.length)
          .map((group) => (
            <SelectGroup key={group.label}>
              <SelectLabel>{group.label}</SelectLabel>
              {group.options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectGroup>
          ))}
      </SelectContent>
    </Select>
  );
}

/** Free-text list (commas or spaces); parsed when the field loses focus. */
export function ListInput({
  value,
  onChange,
  clean = (item) => item,
  placeholder,
  className,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  clean?: (item: string) => string;
  placeholder?: string;
  className?: string;
}) {
  const [text, setText] = useState(value.join(' '));
  const commit = () => {
    const items = text
      .split(/[\s,，]+/)
      .map(clean)
      .filter(Boolean);
    setText(items.join(' '));
    onChange(items);
  };
  return (
    <Input
      className={className}
      value={text}
      placeholder={placeholder}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
    />
  );
}
