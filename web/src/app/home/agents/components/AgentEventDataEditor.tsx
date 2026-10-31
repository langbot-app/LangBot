import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowLeftRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  debugEventDefinition,
  parseDebugEventData,
  getDebugEventField,
  setDebugEventField,
} from './debug-event-data';

export default function AgentEventDataEditor({
  eventType,
  value,
  onChange,
  custom = false,
  processor = false,
}: {
  eventType: string;
  custom?: boolean;
  processor?: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const [showJson, setShowJson] = useState(false);
  const fields = custom
    ? []
    : (debugEventDefinition(eventType, processor)?.fields ?? []);
  const data = parseDebugEventData(value);
  const chainKey =
    processor &&
    (eventType === 'message.received'
      ? 'message_chain'
      : eventType === 'message.edited'
        ? 'new_content'
        : undefined);
  const chain = chainKey && data?.[chainKey];
  const richMessage =
    chainKey &&
    (!Array.isArray(chain) || chain.length !== 1 || chain[0]?.type !== 'Plain');
  const jsonMode = showJson || !fields.length || !!richMessage;

  function updateField(key: string, next: string | number | undefined) {
    if (data)
      onChange(JSON.stringify(setDebugEventField(data, key, next), null, 2));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium">
          {t('agents.debugData.title')}
        </span>
        {fields.length > 0 && !richMessage && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 gap-1.5 px-1.5 text-xs text-muted-foreground"
            disabled={jsonMode && !data}
            onClick={() => setShowJson(!showJson)}
          >
            <ArrowLeftRight className="size-3.5" aria-hidden="true" />
            {t(jsonMode ? 'agents.debugData.form' : 'agents.debugData.json')}
          </Button>
        )}
      </div>
      {jsonMode ? (
        <>
          <Textarea
            aria-label={t('agents.debugData.json')}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            rows={6}
            className="min-h-28 font-mono text-xs"
            spellCheck={false}
            aria-invalid={!data}
          />
          {!data && (
            <p role="alert" className="text-xs text-destructive">
              {t('agents.debugInvalidPayload')}
            </p>
          )}
        </>
      ) : (
        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          {fields.map((field) => {
            const id = `agent-debug-data-${field.key}`;
            const current = getDebugEventField(data, field.key);
            const text =
              typeof current === 'string' || typeof current === 'number'
                ? current
                : '';
            return (
              <div
                key={field.key}
                className={`min-w-0 space-y-1 ${field.multiline ? 'col-span-2' : ''}`}
              >
                <Label htmlFor={id} className="text-xs text-muted-foreground">
                  {t(`agents.debugData.${field.label}`)}
                </Label>
                {field.multiline ? (
                  <Textarea
                    id={id}
                    value={text}
                    rows={2}
                    required={field.required}
                    onChange={(event) =>
                      updateField(field.key, event.target.value)
                    }
                    className="min-h-16 resize-y text-sm"
                  />
                ) : (
                  <Input
                    id={id}
                    value={text}
                    type={typeof field.value === 'number' ? 'number' : 'text'}
                    min={field.min}
                    max={field.max}
                    step={1}
                    className="h-8 text-sm"
                    placeholder={
                      field.placeholder
                        ? t(`agents.debugData.${field.placeholder}`)
                        : undefined
                    }
                    onChange={(event) =>
                      updateField(
                        field.key,
                        typeof field.value === 'number'
                          ? event.target.value === ''
                            ? undefined
                            : Number(event.target.value)
                          : event.target.value,
                      )
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
