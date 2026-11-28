import { useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { ChevronRight, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { WorkflowStep } from '@/app/infra/entities/api';
import { stepOutputs } from '../lib/catalog';
import { useEditor } from './EditorContext';
import {
  Field,
  GroupedSelect,
  ModelSelect,
  OptionSelect,
  useFieldError,
} from './fields';
import TemplateField from './TemplateField';
import { useOutputLabel } from './variables';

type Config = Record<string, unknown>;
type Row = Record<string, unknown>;

export interface FormProps {
  step: WorkflowStep;
  config: Config;
  set: (patch: Config) => void;
}

const str = (value: unknown) => (typeof value === 'string' ? value : '');
const rowsOf = (value: unknown): Row[] =>
  Array.isArray(value) ? (value as Row[]) : [];

function nextId(rows: Row[], prefix: string) {
  const taken = new Set(rows.map((row) => String(row.id)));
  let index = rows.length + 1;
  while (taken.has(`${prefix}${index}`)) index += 1;
  return `${prefix}${index}`;
}

function Advanced({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <ChevronRight
          className={cn('size-3.5 transition-transform', open && 'rotate-90')}
        />
        {t('workflows.form.advanced')}
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4 pt-3">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}

function RowList({
  rows,
  render,
  onAdd,
  onRemove,
  addLabel,
  minRows = 1,
}: {
  rows: Row[];
  render: (row: Row, index: number) => ReactNode;
  onAdd: () => void;
  onRemove: (index: number) => void;
  addLabel: string;
  minRows?: number;
}) {
  return (
    <div className="space-y-2">
      {rows.map((row, index) => (
        <div
          key={String(row.id ?? index)}
          className="relative space-y-2 rounded-lg border p-3 pr-10"
        >
          {render(row, index)}
          {rows.length > minRows && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-2 right-2 size-7 text-muted-foreground"
              onClick={() => onRemove(index)}
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
        onClick={onAdd}
      >
        <Plus className="size-4" />
        {addLabel}
      </Button>
    </div>
  );
}

function OnError({ config, set }: Omit<FormProps, 'step'>) {
  const { t } = useTranslation();
  return (
    <Field label={t('workflows.form.onError')}>
      <OptionSelect
        value={str(config.on_error) || 'stop'}
        onChange={(value) => set({ on_error: value })}
        options={[
          { value: 'stop', label: t('workflows.form.onErrorStop') },
          { value: 'continue', label: t('workflows.form.onErrorContinue') },
        ]}
      />
    </Field>
  );
}

export function StartForm() {
  const { t } = useTranslation();
  return (
    <div className="space-y-4 text-sm">
      <div className="rounded-lg border bg-muted/30 p-3">
        <p className="font-medium">{t('workflows.start.messageTitle')}</p>
        <p className="mt-1 text-muted-foreground">
          {t('workflows.start.messageHint')}
        </p>
        <Button asChild variant="link" className="mt-1 h-auto p-0">
          <Link to="/home/bots">{t('workflows.start.openBots')}</Link>
        </Button>
      </div>
    </div>
  );
}

export function LlmForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  return (
    <>
      <Field label={t('workflows.form.model')} error={error('model_uuid')}>
        <ModelSelect
          value={str(config.model_uuid)}
          onChange={(value) => set({ model_uuid: value })}
          invalid={Boolean(error('model_uuid'))}
        />
      </Field>
      <Field
        label={t('workflows.llm.prompt')}
        hint={t('workflows.llm.promptHint')}
        error={error('prompt')}
      >
        <TemplateField
          stepId={step.id}
          multiline
          value={str(config.prompt)}
          onChange={(value) => set({ prompt: value })}
          invalid={Boolean(error('prompt'))}
          ariaLabel={t('workflows.llm.prompt')}
        />
      </Field>
      <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
        <div>
          <p className="text-sm font-medium">{t('workflows.llm.history')}</p>
          <p className="text-xs text-muted-foreground">
            {t('workflows.llm.historyHint')}
          </p>
        </div>
        <Switch
          checked={config.use_history !== false}
          onCheckedChange={(value) => set({ use_history: value })}
        />
      </div>
      <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
        <div>
          <p className="text-sm font-medium">{t('workflows.llm.images')}</p>
          <p className="text-xs text-muted-foreground">
            {t('workflows.llm.imagesHint')}
          </p>
        </div>
        <Switch
          checked={config.use_images === true}
          onCheckedChange={(value) => set({ use_images: value })}
        />
      </div>
      <Advanced>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('workflows.llm.temperature')}>
            <Input
              type="number"
              step="0.1"
              min={0}
              max={2}
              value={
                config.temperature === undefined
                  ? ''
                  : String(config.temperature)
              }
              placeholder={t('workflows.form.default')}
              onChange={(event) =>
                set({
                  temperature:
                    event.target.value === ''
                      ? undefined
                      : Number(event.target.value),
                })
              }
            />
          </Field>
          <Field label={t('workflows.llm.maxTokens')}>
            <Input
              type="number"
              min={1}
              value={
                config.max_tokens === undefined ? '' : String(config.max_tokens)
              }
              placeholder={t('workflows.form.default')}
              onChange={(event) =>
                set({
                  max_tokens:
                    event.target.value === ''
                      ? undefined
                      : Number(event.target.value),
                })
              }
            />
          </Field>
        </div>
        <OnError config={config} set={set} />
      </Advanced>
    </>
  );
}

export function ClassifyForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const categories = rowsOf(config.categories);
  const update = (index: number, patch: Row) =>
    set({
      categories: categories.map((row, i) =>
        i === index ? { ...row, ...patch } : row,
      ),
    });
  return (
    <>
      <Field label={t('workflows.form.model')} error={error('model_uuid')}>
        <ModelSelect
          value={str(config.model_uuid)}
          onChange={(value) => set({ model_uuid: value })}
          invalid={Boolean(error('model_uuid'))}
        />
      </Field>
      <Field
        label={t('workflows.classify.categories')}
        hint={t('workflows.classify.categoriesHint')}
        error={error('categories')}
      >
        <RowList
          rows={categories}
          addLabel={t('workflows.classify.add')}
          onAdd={() =>
            set({
              categories: [
                ...categories,
                { id: nextId(categories, 'c'), label: '', description: '' },
              ],
            })
          }
          onRemove={(index) =>
            set({ categories: categories.filter((_, i) => i !== index) })
          }
          render={(row, index) => (
            <>
              <Input
                value={str(row.label)}
                placeholder={t('workflows.classify.labelPlaceholder')}
                onChange={(event) =>
                  update(index, { label: event.target.value })
                }
              />
              <Input
                value={str(row.description)}
                placeholder={t('workflows.classify.descriptionPlaceholder')}
                onChange={(event) =>
                  update(index, { description: event.target.value })
                }
              />
            </>
          )}
        />
      </Field>
      <Advanced>
        <Field
          label={t('workflows.classify.instruction')}
          hint={t('workflows.classify.instructionHint')}
        >
          <TemplateField
            stepId={step.id}
            multiline
            value={str(config.instruction)}
            onChange={(value) => set({ instruction: value })}
          />
        </Field>
      </Advanced>
    </>
  );
}

export function ExtractForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const fields = rowsOf(config.fields);
  const update = (index: number, patch: Row) =>
    set({
      fields: fields.map((row, i) =>
        i === index ? { ...row, ...patch } : row,
      ),
    });
  return (
    <>
      <Field label={t('workflows.form.model')} error={error('model_uuid')}>
        <ModelSelect
          value={str(config.model_uuid)}
          onChange={(value) => set({ model_uuid: value })}
          invalid={Boolean(error('model_uuid'))}
        />
      </Field>
      <Field
        label={t('workflows.extract.fields')}
        hint={t('workflows.extract.fieldsHint')}
        error={error('fields')}
      >
        <RowList
          rows={fields}
          addLabel={t('workflows.extract.add')}
          onAdd={() =>
            set({
              fields: [...fields, { key: '', description: '', type: 'text' }],
            })
          }
          onRemove={(index) =>
            set({ fields: fields.filter((_, i) => i !== index) })
          }
          render={(row, index) => (
            <>
              <div className="grid grid-cols-[1fr_96px] gap-2">
                <Input
                  value={str(row.key)}
                  placeholder={t('workflows.extract.keyPlaceholder')}
                  onChange={(event) =>
                    update(index, {
                      key: event.target.value.replace(/[^\w一-鿿]/g, ''),
                    })
                  }
                />
                <OptionSelect
                  value={str(row.type) || 'text'}
                  onChange={(value) => update(index, { type: value })}
                  options={['text', 'number', 'boolean'].map((value) => ({
                    value,
                    label: t(`workflows.extract.type.${value}`),
                  }))}
                />
              </div>
              <Input
                value={str(row.description)}
                placeholder={t('workflows.extract.descriptionPlaceholder')}
                onChange={(event) =>
                  update(index, { description: event.target.value })
                }
              />
            </>
          )}
        />
      </Field>
    </>
  );
}

const OPS = [
  'contains',
  'not_contains',
  'equals',
  'not_equals',
  'starts_with',
  'ends_with',
  'is_empty',
  'not_empty',
  'gt',
  'lt',
  'regex',
];

export function ConditionForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const cases = rowsOf(config.cases);
  const updateCase = (index: number, patch: Row) =>
    set({
      cases: cases.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    });
  return (
    <Field
      label={t('workflows.condition.cases')}
      hint={t('workflows.condition.casesHint')}
      error={error('cases')}
    >
      <RowList
        rows={cases}
        addLabel={t('workflows.condition.addCase')}
        onAdd={() =>
          set({
            cases: [
              ...cases,
              {
                id: nextId(cases, 'case'),
                label: '',
                match: 'all',
                rules: [
                  { left: '{{ start.text }}', op: 'contains', right: '' },
                ],
              },
            ],
          })
        }
        onRemove={(index) =>
          set({ cases: cases.filter((_, i) => i !== index) })
        }
        render={(row, index) => {
          const rules = rowsOf(row.rules);
          const updateRule = (ruleIndex: number, patch: Row) =>
            updateCase(index, {
              rules: rules.map((rule, i) =>
                i === ruleIndex ? { ...rule, ...patch } : rule,
              ),
            });
          return (
            <>
              <div className="grid grid-cols-[1fr_120px] gap-2">
                <Input
                  value={str(row.label)}
                  placeholder={t('workflows.branches.unnamed', {
                    index: index + 1,
                  })}
                  onChange={(event) =>
                    updateCase(index, { label: event.target.value })
                  }
                />
                <OptionSelect
                  value={str(row.match) || 'all'}
                  onChange={(value) => updateCase(index, { match: value })}
                  options={[
                    { value: 'all', label: t('workflows.condition.all') },
                    { value: 'any', label: t('workflows.condition.any') },
                  ]}
                />
              </div>
              {rules.map((rule, ruleIndex) => {
                const op = str(rule.op) || 'contains';
                const unary = op === 'is_empty' || op === 'not_empty';
                return (
                  <div
                    key={ruleIndex}
                    className="space-y-1.5 rounded-md bg-muted/40 p-2"
                  >
                    <TemplateField
                      stepId={step.id}
                      value={str(rule.left)}
                      onChange={(value) =>
                        updateRule(ruleIndex, { left: value })
                      }
                      placeholder={t('workflows.condition.left')}
                    />
                    <div className="flex gap-1.5">
                      <OptionSelect
                        className="w-32 shrink-0"
                        value={op}
                        onChange={(value) =>
                          updateRule(ruleIndex, { op: value })
                        }
                        options={OPS.map((value) => ({
                          value,
                          label: t(`workflows.condition.op.${value}`),
                        }))}
                      />
                      {!unary && (
                        <TemplateField
                          className="min-w-0 flex-1"
                          stepId={step.id}
                          value={str(rule.right)}
                          onChange={(value) =>
                            updateRule(ruleIndex, { right: value })
                          }
                          placeholder={t('workflows.condition.right')}
                        />
                      )}
                      {rules.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-9 shrink-0 text-muted-foreground"
                          onClick={() =>
                            updateCase(index, {
                              rules: rules.filter((_, i) => i !== ruleIndex),
                            })
                          }
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() =>
                  updateCase(index, {
                    rules: [...rules, { left: '', op: 'contains', right: '' }],
                  })
                }
              >
                <Plus className="size-3.5" />
                {t('workflows.condition.addRule')}
              </Button>
            </>
          );
        }}
      />
    </Field>
  );
}

export function RememberForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const items = rowsOf(config.items);
  const update = (index: number, patch: Row) =>
    set({
      items: items.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    });
  return (
    <>
      <Field
        label={t('workflows.remember.scopeLabel')}
        hint={t(`workflows.remember.scopeHint.${str(config.scope) || 'run'}`)}
      >
        <OptionSelect
          value={str(config.scope) || 'run'}
          onChange={(value) => set({ scope: value })}
          options={['run', 'user', 'group', 'workflow'].map((value) => ({
            value,
            label: t(`workflows.remember.scope.${value}`),
          }))}
        />
      </Field>
      <Field
        label={t('workflows.remember.items')}
        hint={t('workflows.remember.itemsHint')}
        error={error('items')}
      >
        <RowList
          rows={items}
          addLabel={t('workflows.remember.add')}
          onAdd={() =>
            set({ items: [...items, { key: '', op: 'set', value: '' }] })
          }
          onRemove={(index) =>
            set({ items: items.filter((_, i) => i !== index) })
          }
          render={(row, index) => {
            const op = str(row.op) || 'set';
            return (
              <>
                <div className="grid grid-cols-[1fr_120px] gap-2">
                  <Input
                    value={str(row.key)}
                    placeholder={t('workflows.remember.keyPlaceholder')}
                    onChange={(event) =>
                      update(index, { key: event.target.value })
                    }
                  />
                  <OptionSelect
                    value={op}
                    onChange={(value) => update(index, { op: value })}
                    options={['set', 'increment', 'append', 'remove'].map(
                      (value) => ({
                        value,
                        label: t(`workflows.remember.op.${value}`),
                      }),
                    )}
                  />
                </div>
                {op !== 'remove' && (
                  <TemplateField
                    stepId={step.id}
                    value={str(row.value)}
                    onChange={(value) => update(index, { value })}
                    placeholder={
                      op === 'increment'
                        ? '1'
                        : t('workflows.remember.valuePlaceholder')
                    }
                  />
                )}
              </>
            );
          }}
        />
      </Field>
    </>
  );
}

export function ReplyForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  return (
    <Field
      label={t('workflows.reply.text')}
      hint={t('workflows.reply.textHint')}
      error={error('content') ?? error('text')}
    >
      <TemplateField
        stepId={step.id}
        multiline
        value={str(config.text)}
        onChange={(value) => set({ text: value })}
        invalid={Boolean(error('content') ?? error('text'))}
        ariaLabel={t('workflows.reply.text')}
      />
    </Field>
  );
}

export function SendForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  const error = useFieldError(step.id);
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
      <div className="grid grid-cols-[120px_1fr] gap-2">
        <Field label={t('workflows.send.targetType')}>
          <OptionSelect
            value={str(config.target_type) || 'group'}
            onChange={(value) => set({ target_type: value })}
            options={[
              { value: 'group', label: t('workflows.send.group') },
              { value: 'person', label: t('workflows.send.person') },
            ]}
          />
        </Field>
        <Field label={t('workflows.send.targetId')} error={error('target_id')}>
          <TemplateField
            stepId={step.id}
            value={str(config.target_id)}
            onChange={(value) => set({ target_id: value })}
            invalid={Boolean(error('target_id'))}
          />
        </Field>
      </div>
      <Field
        label={t('workflows.reply.text')}
        error={error('content') ?? error('text')}
      >
        <TemplateField
          stepId={step.id}
          multiline
          value={str(config.text)}
          onChange={(value) => set({ text: value })}
        />
      </Field>
    </>
  );
}

export function HttpForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const error = useFieldError(step.id);
  const method = str(config.method) || 'GET';
  const headers = rowsOf(config.headers);
  return (
    <>
      <div className="grid grid-cols-[104px_1fr] gap-2">
        <Field label={t('workflows.http.method')}>
          <OptionSelect
            value={method}
            onChange={(value) => set({ method: value })}
            options={['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({
              value,
              label: value,
            }))}
          />
        </Field>
        <Field label={t('workflows.http.url')} error={error('url')}>
          <TemplateField
            stepId={step.id}
            value={str(config.url)}
            onChange={(value) => set({ url: value })}
            placeholder="https://"
            invalid={Boolean(error('url'))}
          />
        </Field>
      </div>
      {method !== 'GET' && (
        <Field
          label={t('workflows.http.body')}
          hint={t('workflows.http.bodyHint')}
        >
          <TemplateField
            stepId={step.id}
            multiline
            value={str(config.body)}
            onChange={(value) => set({ body: value })}
          />
        </Field>
      )}
      <p className="text-xs text-muted-foreground">
        {t('workflows.http.outputsHint')}
      </p>
      <Advanced>
        <Field label={t('workflows.http.headers')}>
          <div className="space-y-2">
            {headers.map((header, index) => (
              <div key={index} className="flex gap-1.5">
                <Input
                  className="w-36 shrink-0"
                  value={str(header.key)}
                  placeholder="Authorization"
                  onChange={(event) =>
                    set({
                      headers: headers.map((row, i) =>
                        i === index ? { ...row, key: event.target.value } : row,
                      ),
                    })
                  }
                />
                <TemplateField
                  className="min-w-0 flex-1"
                  stepId={step.id}
                  value={str(header.value)}
                  onChange={(value) =>
                    set({
                      headers: headers.map((row, i) =>
                        i === index ? { ...row, value } : row,
                      ),
                    })
                  }
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-9 shrink-0 text-muted-foreground"
                  onClick={() =>
                    set({ headers: headers.filter((_, i) => i !== index) })
                  }
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
                set({ headers: [...headers, { key: '', value: '' }] })
              }
            >
              <Plus className="size-4" />
              {t('workflows.http.addHeader')}
            </Button>
          </div>
        </Field>
        <Field label={t('workflows.http.timeout')}>
          <Input
            type="number"
            min={1}
            max={30}
            value={String(config.timeout ?? 15)}
            onChange={(event) =>
              set({ timeout: Number(event.target.value) || 15 })
            }
          />
        </Field>
        <OnError config={config} set={set} />
      </Advanced>
    </>
  );
}

export function HandoffForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const { resources, workflowId } = useEditor();
  const error = useFieldError(step.id);
  const value = config.target_uuid
    ? `${str(config.target_type)}:${str(config.target_uuid)}`
    : '';
  return (
    <>
      <Field
        label={t('workflows.handoff.target')}
        hint={t('workflows.handoff.targetHint')}
        error={error('target_uuid')}
      >
        <GroupedSelect
          value={value}
          invalid={Boolean(error('target_uuid'))}
          placeholder={t('workflows.handoff.pick')}
          onChange={(next) => {
            const [type, ...rest] = next.split(':');
            set({ target_type: type, target_uuid: rest.join(':') });
          }}
          groups={[
            {
              label: t('workflows.handoff.chat'),
              options: resources.processors
                .filter((item) => item.kind === 'pipeline' && item.uuid)
                .map((item) => ({
                  value: `chat:${item.uuid}`,
                  label: `${item.emoji ?? ''} ${item.name}`.trim(),
                })),
            },
            {
              label: t('workflows.handoff.agent'),
              options: resources.processors
                .filter((item) => item.kind === 'agent' && item.uuid)
                .map((item) => ({
                  value: `agent:${item.uuid}`,
                  label: `${item.emoji ?? ''} ${item.name}`.trim(),
                })),
            },
            {
              label: t('workflows.handoff.workflow'),
              options: resources.workflows
                .filter((item) => item.uuid !== workflowId)
                .map((item) => ({
                  value: `workflow:${item.uuid}`,
                  label: `${item.emoji ?? ''} ${item.name}`.trim(),
                })),
            },
          ]}
        />
      </Field>
      <Field
        label={t('workflows.handoff.text')}
        hint={t('workflows.handoff.textHint')}
      >
        <TemplateField
          stepId={step.id}
          multiline
          value={str(config.text)}
          onChange={(text) => set({ text })}
          placeholder={t('workflows.handoff.textPlaceholder')}
        />
      </Field>
    </>
  );
}

export function OutputsPreview({ step }: { step: WorkflowStep }) {
  const { t } = useTranslation();
  const outputLabel = useOutputLabel();
  const outputs = stepOutputs(step);
  if (!outputs.length) return null;
  return (
    <div className="space-y-1.5 border-t pt-4">
      <p className="text-sm font-medium">{t('workflows.form.outputs')}</p>
      <div className="flex flex-wrap gap-1.5">
        {outputs.map((key) => (
          <span
            key={key}
            className="rounded-md border border-blue-200 bg-blue-50 px-1.5 text-xs leading-5 text-blue-700 dark:border-blue-900 dark:bg-blue-950/50 dark:text-blue-300"
          >
            {outputLabel(key)}
          </span>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('workflows.form.outputsHint')}
      </p>
    </div>
  );
}
