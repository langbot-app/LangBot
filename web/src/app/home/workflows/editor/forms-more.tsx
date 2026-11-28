import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useEditor } from './EditorContext';
import {
  Field,
  ListInput,
  ModelSelect,
  OptionSelect,
  useFieldError,
} from './fields';
import { Advanced, OnError, str, type FormProps } from './forms';
import TemplateField from './TemplateField';

const num = (value: unknown, fallback = '') =>
  typeof value === 'number' ? String(value) : fallback;

export function KnowledgeForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  const error = useFieldError(step.id);
  return (
    <>
      <Field label={t('workflows.knowledge.base')} error={error('kb_uuid')}>
        {resources.knowledgeBases.length ? (
          <OptionSelect
            value={str(config.kb_uuid)}
            onChange={(value) => set({ kb_uuid: value })}
            options={resources.knowledgeBases.map((base) => ({
              value: base.uuid ?? '',
              label: base.name,
            }))}
          />
        ) : (
          <p className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
            {t('workflows.knowledge.none')}
          </p>
        )}
      </Field>
      <Field label={t('workflows.knowledge.query')} error={error('query')}>
        <TemplateField
          stepId={step.id}
          value={str(config.query)}
          onChange={(value) => set({ query: value })}
        />
      </Field>
      <Field
        label={t('workflows.knowledge.topK')}
        hint={t('workflows.knowledge.topKHint')}
      >
        <Input
          type="number"
          min={1}
          max={20}
          value={num(config.top_k, '5')}
          onChange={(event) => set({ top_k: Number(event.target.value) || 5 })}
        />
      </Field>
    </>
  );
}

export function RandomForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const mode = str(config.mode) || 'pick';
  const items = Array.isArray(config.items) ? (config.items as string[]) : [];
  return (
    <>
      <Field
        label={t('workflows.random.mode')}
        hint={t(`workflows.random.modeHint.${mode}`)}
      >
        <OptionSelect
          value={mode}
          onChange={(value) =>
            set({
              mode: value,
              ...(value === 'seeded_pick' && !config.seed
                ? { seed: '{{ start.sender_id }}' }
                : {}),
              ...(value === 'number' && config.min === undefined
                ? { min: 1, max: 100 }
                : {}),
            })
          }
          options={['pick', 'seeded_pick', 'number'].map((value) => ({
            value,
            label: t(`workflows.random.modes.${value}`),
          }))}
        />
      </Field>
      {mode === 'number' ? (
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('workflows.random.min')}>
            <Input
              type="number"
              value={num(config.min, '1')}
              onChange={(event) => set({ min: Number(event.target.value) })}
            />
          </Field>
          <Field label={t('workflows.random.max')}>
            <Input
              type="number"
              value={num(config.max, '100')}
              onChange={(event) => set({ max: Number(event.target.value) })}
            />
          </Field>
        </div>
      ) : (
        <Field
          label={t('workflows.random.items')}
          hint={t('workflows.random.itemsHint')}
          error={error('items')}
        >
          <div className="space-y-2">
            {items.map((item, index) => (
              <div key={index} className="flex gap-1.5">
                <TemplateField
                  className="min-w-0 flex-1"
                  stepId={step.id}
                  value={item}
                  onChange={(value) =>
                    set({
                      items: items.map((current, i) =>
                        i === index ? value : current,
                      ),
                    })
                  }
                />
                {items.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-9 shrink-0 text-muted-foreground"
                    onClick={() =>
                      set({ items: items.filter((_, i) => i !== index) })
                    }
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full border-dashed"
              onClick={() => set({ items: [...items, ''] })}
            >
              <Plus className="size-4" />
              {t('workflows.random.add')}
            </Button>
          </div>
        </Field>
      )}
      {mode === 'seeded_pick' && (
        <Field
          label={t('workflows.random.seed')}
          hint={t('workflows.random.seedHint')}
        >
          <TemplateField
            stepId={step.id}
            value={str(config.seed)}
            onChange={(value) => set({ seed: value })}
          />
        </Field>
      )}
    </>
  );
}

export function HistoryForm({ config, set }: FormProps) {
  const { t } = useTranslation();
  return (
    <>
      <Field label={t('workflows.history.scope')}>
        <OptionSelect
          value={str(config.scope) || 'conversation'}
          onChange={(value) => set({ scope: value })}
          options={['conversation', 'group'].map((value) => ({
            value,
            label: t(`workflows.history.scopes.${value}`),
          }))}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label={t('workflows.history.limit')}>
          <Input
            type="number"
            min={1}
            max={200}
            value={num(config.limit, '50')}
            onChange={(event) =>
              set({
                limit: Math.min(
                  200,
                  Math.max(1, Number(event.target.value) || 50),
                ),
              })
            }
          />
        </Field>
        <Field label={t('workflows.history.sinceHours')}>
          <Input
            type="number"
            min={1}
            value={num(config.since_hours)}
            placeholder={t('workflows.history.noLimit')}
            onChange={(event) =>
              set({
                since_hours:
                  event.target.value === ''
                    ? undefined
                    : Number(event.target.value),
              })
            }
          />
        </Field>
      </div>
      <p className="text-xs text-muted-foreground">
        {t('workflows.history.hint')}
      </p>
    </>
  );
}

export function CodeForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const inputs = Object.entries(
    (config.inputs as Record<string, string>) ?? {},
  );
  const outputs = Array.isArray(config.outputs)
    ? (config.outputs as unknown[]).filter(
        (key): key is string => typeof key === 'string',
      )
    : [];
  const setInputs = (entries: [string, string][]) =>
    set({ inputs: Object.fromEntries(entries) });
  return (
    <>
      <Field
        label={t('workflows.code.inputs')}
        hint={t('workflows.code.inputsHint')}
      >
        <div className="space-y-2">
          {inputs.map(([key, value], index) => (
            <div key={index} className="flex gap-1.5">
              <Input
                className="w-28 shrink-0 font-mono"
                value={key}
                placeholder="name"
                onChange={(event) => {
                  const next = [...inputs];
                  next[index] = [
                    event.target.value.replace(/[^\w]/g, ''),
                    value,
                  ];
                  setInputs(next);
                }}
              />
              <TemplateField
                className="min-w-0 flex-1"
                stepId={step.id}
                value={value}
                onChange={(next) => {
                  const entries = [...inputs];
                  entries[index] = [key, next];
                  setInputs(entries);
                }}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-9 shrink-0 text-muted-foreground"
                onClick={() => setInputs(inputs.filter((_, i) => i !== index))}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full border-dashed"
            onClick={() =>
              setInputs([...inputs, [`x${inputs.length + 1}`, '']])
            }
          >
            <Plus className="size-4" />
            {t('workflows.code.addInput')}
          </Button>
        </div>
      </Field>
      <Field
        label={t('workflows.code.code')}
        hint={t('workflows.code.codeHint')}
        error={error('code')}
      >
        <Textarea
          rows={10}
          spellCheck={false}
          className="font-mono text-xs leading-5"
          value={str(config.code)}
          placeholder={'total = int(inputs["x1"]) * 2\nreturn {"total": total}'}
          onChange={(event) => set({ code: event.target.value })}
        />
      </Field>
      <Field
        label={t('workflows.code.outputs')}
        hint={t('workflows.code.outputsHint')}
      >
        <ListInput
          className="font-mono"
          value={outputs}
          placeholder="total message"
          clean={(key) => key.replace(/[^\w]/g, '')}
          onChange={(keys) => set({ outputs: keys })}
        />
      </Field>
    </>
  );
}

export function TtsForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  return (
    <>
      <Field label={t('workflows.form.model')} error={error('model_uuid')}>
        <ModelSelect
          kind="tts"
          value={str(config.model_uuid)}
          onChange={(value) => set({ model_uuid: value })}
          invalid={Boolean(error('model_uuid'))}
        />
      </Field>
      <Field label={t('workflows.tts.text')} error={error('text')}>
        <TemplateField
          stepId={step.id}
          multiline
          value={str(config.text)}
          onChange={(value) => set({ text: value })}
        />
      </Field>
      <p className="text-xs text-muted-foreground">{t('workflows.tts.hint')}</p>
      <Advanced>
        <Field
          label={t('workflows.tts.voice')}
          hint={t('workflows.tts.voiceHint')}
        >
          <Input
            value={str(config.voice)}
            placeholder={t('workflows.form.default')}
            onChange={(event) =>
              set({ voice: event.target.value || undefined })
            }
          />
        </Field>
      </Advanced>
    </>
  );
}

export function AsrForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  return (
    <>
      <Field label={t('workflows.form.model')} error={error('model_uuid')}>
        <ModelSelect
          kind="asr"
          value={str(config.model_uuid)}
          onChange={(value) => set({ model_uuid: value })}
          invalid={Boolean(error('model_uuid'))}
        />
      </Field>
      <Field
        label={t('workflows.asr.voice')}
        hint={t('workflows.asr.voiceHint')}
        error={error('voice')}
      >
        <TemplateField
          stepId={step.id}
          value={str(config.voice)}
          onChange={(value) => set({ voice: value })}
        />
      </Field>
    </>
  );
}

const PLATFORM_PARAMS: Record<string, string[]> = {
  mute_member: ['group_id', 'user_id', 'duration'],
  unmute_member: ['group_id', 'user_id'],
  kick_member: ['group_id', 'user_id'],
  delete_message: ['chat_type', 'chat_id', 'message_id'],
  set_group_name: ['group_id', 'name'],
  get_group_info: ['group_id'],
  get_group_member_info: ['group_id', 'user_id'],
  get_group_member_list: ['group_id'],
  get_user_info: ['user_id'],
  call_platform_api: [],
};

const PARAM_DEFAULTS: Record<string, string> = {
  group_id: '{{ start.group_id }}',
  user_id: '{{ start.sender_id }}',
  chat_id: '{{ start.group_id }}',
  chat_type: 'group',
  duration: '600',
};

export function PlatformForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  const error = useFieldError(step.id);
  const action = str(config.action);
  const params = (config.params as Record<string, unknown>) ?? {};
  const [json, setJson] = useState(() =>
    JSON.stringify(params.params ?? {}, null, 2),
  );
  const [jsonError, setJsonError] = useState(false);
  const setParam = (key: string, value: unknown) =>
    set({ params: { ...params, [key]: value } });
  return (
    <>
      <Field label={t('workflows.send.bot')} hint={t('workflows.send.botHint')}>
        <OptionSelect
          value={str(config.bot_uuid) || '_current'}
          onChange={(value) =>
            set({ bot_uuid: value === '_current' ? undefined : value })
          }
          options={[
            { value: '_current', label: t('workflows.send.currentBot') },
            ...resources.bots.map((bot) => ({
              value: bot.uuid,
              label: bot.name,
            })),
          ]}
        />
      </Field>
      <Field
        label={t('workflows.platform.action')}
        hint={t('workflows.platform.actionHint')}
        error={error('action')}
      >
        <OptionSelect
          value={action}
          onChange={(value) =>
            set({
              action: value,
              params: Object.fromEntries(
                (PLATFORM_PARAMS[value] ?? []).map((key) => [
                  key,
                  PARAM_DEFAULTS[key] ?? '',
                ]),
              ),
            })
          }
          options={Object.keys(PLATFORM_PARAMS).map((value) => ({
            value,
            label: t(`workflows.platform.actions.${value}`),
          }))}
        />
      </Field>
      {(PLATFORM_PARAMS[action] ?? []).map((key) =>
        key === 'chat_type' ? (
          <Field key={key} label={t(`workflows.platform.params.${key}`)}>
            <OptionSelect
              value={str(params[key]) || 'group'}
              onChange={(value) => setParam(key, value)}
              options={[
                { value: 'group', label: t('workflows.send.group') },
                { value: 'person', label: t('workflows.send.person') },
              ]}
            />
          </Field>
        ) : (
          <Field key={key} label={t(`workflows.platform.params.${key}`)}>
            <TemplateField
              stepId={step.id}
              value={str(params[key])}
              onChange={(value) => setParam(key, value)}
            />
          </Field>
        ),
      )}
      {action === 'call_platform_api' && (
        <>
          <Field
            label={t('workflows.platform.rawAction')}
            hint={t('workflows.platform.rawActionHint')}
          >
            <Input
              className="font-mono"
              value={str(params.action)}
              placeholder="set_group_card"
              onChange={(event) => setParam('action', event.target.value)}
            />
          </Field>
          <Field
            label={t('workflows.platform.rawParams')}
            error={jsonError ? t('workflows.platform.invalidJson') : undefined}
          >
            <Textarea
              rows={6}
              spellCheck={false}
              className="font-mono text-xs"
              value={json}
              onChange={(event) => {
                setJson(event.target.value);
                try {
                  setParam('params', JSON.parse(event.target.value || '{}'));
                  setJsonError(false);
                } catch {
                  setJsonError(true);
                }
              }}
            />
          </Field>
        </>
      )}
      <Advanced>
        <OnError config={config} set={set} />
      </Advanced>
    </>
  );
}

/** Optional image and voice attached to a reply or a send. */
export function Attachments({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const build = (patch: Record<string, unknown>) => {
    const next = { ...config, ...patch };
    const text = str(next.text);
    const image = str(next.image);
    const voice = str(next.voice);
    const content =
      image || voice
        ? [
            ...(text ? [{ type: 'text', text }] : []),
            ...(image ? [{ type: 'image', ref: image }] : []),
            ...(voice ? [{ type: 'voice', ref: voice }] : []),
          ]
        : undefined;
    set({ ...patch, content });
  };
  return (
    <Advanced>
      <Field
        label={t('workflows.reply.image')}
        hint={t('workflows.reply.imageHint')}
      >
        <TemplateField
          stepId={step.id}
          value={str(config.image)}
          onChange={(value) => build({ image: value })}
          placeholder="https://"
        />
      </Field>
      <Field
        label={t('workflows.reply.voice')}
        hint={t('workflows.reply.voiceHint')}
      >
        <TemplateField
          stepId={step.id}
          value={str(config.voice)}
          onChange={(value) => build({ voice: value })}
        />
      </Field>
    </Advanced>
  );
}
