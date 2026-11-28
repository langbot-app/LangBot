import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import type { AgentPlatformTool } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import {
  API_GROUPS,
  API_PARAMS,
  PARAM_DEFAULTS,
  STANDARD_EVENTS,
  type ApiParam,
} from '../lib/platform';
import { useEditor } from './EditorContext';
import { Field, GroupedSelect, OptionSelect, useFieldError } from './fields';
import { Advanced, OnError, str, type FormProps } from './forms';
import TemplateField from './TemplateField';

/** Messages go out through the reply/send steps so the bot's output policy applies. */
const STEP_ONLY = new Set([
  'event_reply',
  'platform_send_message',
  'request_interaction',
]);
/** Catalog tools already cover these standard APIs. */
const SPECIFIC = 'specific:';
const CUSTOM = 'call_platform_api';

type Params = Record<string, unknown>;

interface ParamField {
  key: string;
  kind: 'text' | 'number' | 'bool' | 'enum' | 'media' | 'message';
  options?: string[];
  optional?: boolean;
  hint?: string;
}

/** Turn a tool's JSON schema into form fields. */
function schemaFields(tool: AgentPlatformTool): ParamField[] {
  const schema = tool.parameters as {
    properties?: Record<
      string,
      { type?: string; enum?: string[]; description?: string }
    >;
    required?: string[];
  };
  return Object.entries(schema.properties ?? {}).map(([key, field]) => ({
    key,
    kind: field.enum
      ? 'enum'
      : field.type === 'boolean'
        ? 'bool'
        : field.type === 'integer'
          ? 'number'
          : 'text',
    options: field.enum,
    optional: !(schema.required ?? []).includes(key),
    hint: field.description,
  }));
}

function apiFields(params: ApiParam[]): ParamField[] {
  return params.map((param) => ({
    key: param.key,
    kind: param.kind === 'chat_type' ? 'enum' : (param.kind ?? 'text'),
    options: param.kind === 'chat_type' ? ['group', 'private'] : undefined,
    optional: param.optional,
  }));
}

function defaults(fields: ParamField[], scope: 'event' | 'platform') {
  return Object.fromEntries(
    fields.flatMap((field) => {
      if (field.kind === 'bool') return [[field.key, true]];
      if (field.key === 'duration') return [[field.key, '600']];
      if (scope === 'event' || PARAM_DEFAULTS[field.key] === undefined)
        return [];
      return [[field.key, PARAM_DEFAULTS[field.key]]];
    }),
  );
}

/** Event patterns this workflow can start from, for event-bound actions. */
function triggerEvents(
  triggers: { type: string; events?: unknown }[],
): string[] {
  return triggers.flatMap((trigger) => {
    if (trigger.type === 'message' || trigger.type === 'command')
      return ['message.received'];
    if (trigger.type === 'event') return (trigger.events as string[]) ?? [];
    return [];
  });
}

/** Whether any event the workflow starts from fits one of the tool's patterns. */
function matches(patterns: string[], toolPatterns: string[]) {
  const glob = (pattern: string, event: string) =>
    new RegExp(
      `^${pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*')}$`,
    ).test(event);
  const concrete = patterns.flatMap((pattern) =>
    pattern.includes('*')
      ? ['message.received', ...STANDARD_EVENTS].filter((event) =>
          glob(pattern, event),
        )
      : [pattern],
  );
  return concrete.some((event) =>
    toolPatterns.some((toolPattern) => glob(toolPattern, event)),
  );
}

export function PlatformForm({ step, config, set }: FormProps) {
  const { t } = useTranslation();
  const { resources, triggers } = useEditor();
  const error = useFieldError(step.id);
  const action = str(config.action);
  const params = (config.params as Params) ?? {};
  const tools = resources.platformTools.filter(
    (tool) => !STEP_ONLY.has(tool.name),
  );
  const tool = tools.find((item) => item.name === action);
  const events = triggerEvents(triggers);
  const eventTools = tools.filter(
    (item) =>
      item.scope === 'event' &&
      (matches(events, item.event_patterns) || item.name === action),
  );
  const botAdapters = config.bot_uuid
    ? resources.bots
        .filter((bot) => bot.uuid === config.bot_uuid)
        .map((bot) => bot.adapter)
    : [...new Set(resources.bots.map((bot) => bot.adapter))];
  const specificActions = [
    ...new Map(
      botAdapters.flatMap((name) =>
        (resources.adapters[name]?.specific ?? []).map((item) => [
          item.action,
          { ...item, adapter: resources.adapters[name]?.label ?? name },
        ]),
      ),
    ).values(),
  ];
  const specificName =
    action === CUSTOM && typeof params.action === 'string' ? params.action : '';
  const value =
    action === CUSTOM &&
    specificActions.some((item) => item.action === specificName)
      ? `${SPECIFIC}${specificName}`
      : action;
  const label = (item: AgentPlatformTool) => extractI18nObject(item.label);
  const groups = [
    ...(eventTools.length
      ? [
          {
            label: t('workflows.platform.groups.event'),
            options: eventTools.map((item) => ({
              value: item.name,
              label: label(item),
            })),
          },
        ]
      : []),
    ...['message', 'group', 'moderation', 'identity'].map((category) => ({
      label: t(`workflows.platform.groups.${category}`),
      options: tools
        .filter(
          (item) => item.scope === 'platform' && item.category === category,
        )
        .map((item) => ({ value: item.name, label: label(item) })),
    })),
    {
      label: t('workflows.platform.groups.more'),
      options: API_GROUPS.flatMap((group) => Object.keys(group.apis))
        .filter(
          (api) =>
            !tools.some(
              (item) => item.scope === 'platform' && item.api === api,
            ) || api === action,
        )
        .map((api) => ({
          value: api,
          label: t(`workflows.platform.actions.${api}`),
        })),
    },
    {
      label: t('workflows.platform.groups.specific'),
      options: [
        ...specificActions.map((item) => ({
          value: `${SPECIFIC}${item.action}`,
          label: item.description
            ? `${item.description} (${item.action})`
            : item.action,
        })),
        { value: CUSTOM, label: t('workflows.platform.actions.custom') },
      ],
    },
  ].filter((group) => group.options.length);

  const choose = (next: string) => {
    if (next.startsWith(SPECIFIC)) {
      set({
        action: CUSTOM,
        params: { action: next.slice(SPECIFIC.length), params: {} },
      });
      return;
    }
    if (next === CUSTOM) {
      set({ action: CUSTOM, params: { action: '', params: {} } });
      return;
    }
    const picked = tools.find((item) => item.name === next);
    const fields = picked
      ? schemaFields(picked)
      : apiFields(API_PARAMS[next] ?? []);
    set({
      action: next,
      bot_uuid: picked?.scope === 'event' ? undefined : config.bot_uuid,
      params: defaults(fields, picked?.scope ?? 'platform'),
    });
  };

  const fields = tool
    ? schemaFields(tool)
    : action === CUSTOM
      ? []
      : apiFields(API_PARAMS[action] ?? []);
  const api = tool?.api ?? (action === CUSTOM ? CUSTOM : action);
  const supported = botAdapters.filter((name) =>
    resources.adapters[name]?.apis.includes(api),
  );
  const setParam = (key: string, next: unknown) =>
    set({ params: { ...params, [key]: next } });

  return (
    <>
      <Field
        label={t('workflows.platform.action')}
        hint={
          tool?.scope === 'event'
            ? t('workflows.platform.eventHint')
            : t('workflows.platform.actionHint')
        }
        error={error('action')}
      >
        <GroupedSelect
          value={value}
          groups={groups}
          onChange={choose}
          placeholder={t('workflows.platform.choose')}
          invalid={Boolean(error('action'))}
        />
      </Field>
      {tool && (
        <p className="-mt-2 text-xs text-muted-foreground">
          {extractI18nObject(tool.description)}
        </p>
      )}
      {action && botAdapters.length > 0 && (
        <p
          className={
            supported.length
              ? '-mt-2 text-xs text-muted-foreground'
              : '-mt-2 text-xs text-amber-700 dark:text-amber-300'
          }
        >
          {supported.length
            ? t('workflows.platform.supportedBy', {
                names: supported
                  .map((name) => resources.adapters[name]?.label ?? name)
                  .join(' · '),
              })
            : t('workflows.platform.unsupported')}
        </p>
      )}
      {tool?.scope !== 'event' && (
        <Field
          label={t('workflows.send.bot')}
          hint={t('workflows.send.botHint')}
        >
          <OptionSelect
            value={str(config.bot_uuid) || '_current'}
            onChange={(next) =>
              set({ bot_uuid: next === '_current' ? undefined : next })
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
      )}
      {fields.map((field) => (
        <ParamInput
          key={field.key}
          stepId={step.id}
          field={field}
          value={params[field.key]}
          onChange={(next) => setParam(field.key, next)}
        />
      ))}
      {action === CUSTOM && (
        <CustomAction
          stepId={step.id}
          params={params}
          fixedName={value.startsWith(SPECIFIC)}
          onChange={(next) => set({ params: next })}
        />
      )}
      <Advanced>
        <OnError config={config} set={set} />
      </Advanced>
    </>
  );
}

function paramLabel(
  t: (key: string) => string,
  exists: (key: string) => boolean,
  key: string,
) {
  const name = `workflows.platform.params.${key}`;
  return exists(name) ? t(name) : key;
}

function ParamInput({
  stepId,
  field,
  value,
  onChange,
}: {
  stepId: string;
  field: ParamField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const { t, i18n } = useTranslation();
  const label = paramLabel(t, (key) => i18n.exists(key), field.key);
  if (field.kind === 'bool') {
    return (
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm">{label}</span>
        <Switch
          checked={value !== false && value !== 'false'}
          onCheckedChange={onChange}
        />
      </div>
    );
  }
  if (field.kind === 'enum') {
    const options = (field.options ?? []).filter((item) => item !== 'person');
    return (
      <Field label={label}>
        <OptionSelect
          value={str(value) || '{{ start.chat_type }}'}
          onChange={onChange}
          options={[
            {
              value: '{{ start.chat_type }}',
              label: t('workflows.platform.currentChat'),
            },
            ...options.map((item) => ({
              value: item,
              label: t(`workflows.platform.chatTypes.${item}`),
            })),
          ]}
        />
      </Field>
    );
  }
  return (
    <Field
      label={
        field.optional
          ? `${label} (${t('workflows.platform.optional')})`
          : label
      }
      hint={
        field.kind === 'media'
          ? t('workflows.platform.mediaHint')
          : field.kind === 'message'
            ? t('workflows.platform.messageHint')
            : undefined
      }
    >
      <TemplateField
        stepId={stepId}
        value={
          typeof value === 'string' ? value : value == null ? '' : String(value)
        }
        onChange={onChange}
      />
    </Field>
  );
}

/** A platform-specific action: its name plus key/value parameters. */
function CustomAction({
  stepId,
  params,
  fixedName,
  onChange,
}: {
  stepId: string;
  params: Params;
  fixedName: boolean;
  onChange: (params: Params) => void;
}) {
  const { t } = useTranslation();
  const values = (params.params as Params) ?? {};
  const [rows, setRows] = useState(() =>
    Object.entries(values).map(([key, value]) => ({
      key,
      value: typeof value === 'string' ? value : JSON.stringify(value),
    })),
  );
  const commit = (next: { key: string; value: string }[]) => {
    setRows(next);
    onChange({
      ...params,
      params: Object.fromEntries(
        next
          .filter((row) => row.key.trim())
          .map((row) => [row.key.trim(), row.value]),
      ),
    });
  };
  return (
    <>
      {!fixedName && (
        <Field
          label={t('workflows.platform.rawAction')}
          hint={t('workflows.platform.rawActionHint')}
        >
          <Input
            className="font-mono"
            value={str(params.action)}
            placeholder="set_group_card"
            onChange={(event) =>
              onChange({ ...params, action: event.target.value.trim() })
            }
          />
        </Field>
      )}
      <Field
        label={t('workflows.platform.rawParams')}
        hint={t('workflows.platform.rawParamsHint')}
      >
        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={index} className="flex items-start gap-2">
              <Input
                className="w-32 shrink-0 font-mono text-xs"
                value={row.key}
                placeholder="user_id"
                aria-label={t('workflows.platform.paramName')}
                onChange={(event) =>
                  commit(
                    rows.map((item, i) =>
                      i === index ? { ...item, key: event.target.value } : item,
                    ),
                  )
                }
              />
              <div className="min-w-0 flex-1">
                <TemplateField
                  stepId={stepId}
                  value={row.value}
                  onChange={(value) =>
                    commit(
                      rows.map((item, i) =>
                        i === index ? { ...item, value } : item,
                      ),
                    )
                  }
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8 shrink-0 text-muted-foreground"
                aria-label={t('workflows.platform.removeParam')}
                onClick={() => commit(rows.filter((_, i) => i !== index))}
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
            onClick={() => setRows([...rows, { key: '', value: '' }])}
          >
            <Plus className="size-4" />
            {t('workflows.platform.addParam')}
          </Button>
        </div>
      </Field>
    </>
  );
}
