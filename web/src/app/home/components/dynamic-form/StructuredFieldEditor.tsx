import { useEffect, useRef, useState } from 'react';
import type { ControllerRenderProps } from 'react-hook-form';
import { useFormContext } from 'react-hook-form';
import { Textarea } from '@/components/ui/textarea';
import { useTranslation } from 'react-i18next';
import { parseStructuredDraft } from './StructuredFieldValue';

/** Draft text stays local: only explicitly parsed edits enter persisted state. */
export default function StructuredFieldEditor({
  field,
  prompt = false,
}: {
  field: ControllerRenderProps<any, any>;
  prompt?: boolean;
}) {
  const { t } = useTranslation();
  const form = useFormContext();
  const [draft, setDraft] = useState(
    () => JSON.stringify(field.value, null, 2) ?? '',
  );
  const [invalid, setInvalid] = useState(false);
  const emitted = useRef(field.value);
  const input = useRef<HTMLTextAreaElement | null>(null);
  const error = t('agents.debugData.invalidField', {
    field: `${field.name} (JSON)`,
  });
  useEffect(() => {
    if (JSON.stringify(field.value) !== JSON.stringify(emitted.current)) {
      emitted.current = field.value;
      setDraft(JSON.stringify(field.value, null, 2) ?? '');
      setInvalid(false);
      input.current?.setCustomValidity('');
    }
  }, [field.value]);
  return (
    <div className="space-y-2">
      <Textarea
        ref={(element) => {
          input.current = element;
          field.ref(element);
        }}
        name={field.name}
        aria-label={`${field.name} (JSON)`}
        data-testid={`structured-editor-${field.name}`}
        aria-invalid={invalid}
        className="min-h-48 font-mono"
        value={draft}
        onBlur={field.onBlur}
        onChange={(event) => {
          const next = event.target.value;
          setDraft(next);
          try {
            const value = parseStructuredDraft(next, prompt);
            event.target.setCustomValidity('');
            setInvalid(false);
            form.clearErrors(field.name);
            emitted.current = value;
            field.onChange(value);
          } catch {
            event.target.setCustomValidity(error);
            setInvalid(true);
            form.setError(field.name, { type: 'json', message: error });
          }
        }}
      />
      {invalid && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
