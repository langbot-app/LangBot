import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  AlarmClock,
  Copy,
  MessageCircle,
  Plus,
  Radio,
  SquareTerminal,
  Trash2,
  Webhook,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import type { WorkflowTrigger } from '@/app/infra/entities/api';
import { eventPatternLabel } from '@/app/home/components/event-patterns/event-pattern-groups';
import { useEditor } from './EditorContext';
import { Field, ListInput, OptionSelect } from './fields';

type Kind = WorkflowTrigger['type'];
type Row = Record<string, unknown>;

const ICONS: Record<Kind, typeof MessageCircle> = {
  message: MessageCircle,
  command: SquareTerminal,
  schedule: AlarmClock,
  event: Radio,
  webhook: Webhook,
};

export const EVENT_TYPES = [
  'group.member_joined',
  'group.member_left',
  'group.member_banned',
  'group.info_updated',
  'message.deleted',
  'message.reaction',
  'friend.request_received',
  'friend.added',
  'bot.invited_to_group',
];

const SINGLE: Kind[] = ['message', 'event'];
const WEEKDAYS = [1, 2, 3, 4, 5, 6, 0];

const str = (value: unknown) => (typeof value === 'string' ? value : '');

type ScheduleMode = 'daily' | 'weekly' | 'interval' | 'cron';

function scheduleMode(trigger: Row): ScheduleMode {
  if (trigger.every) return 'interval';
  const cron = str(trigger.cron);
  if (/^\d{1,2} \d{1,2} \* \* \*$/.test(cron)) return 'daily';
  if (/^\d{1,2} \d{1,2} \* \* \d$/.test(cron)) return 'weekly';
  return 'cron';
}

function cronTime(cron: string) {
  const [minute = '0', hour = '8'] = cron.split(' ');
  return `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
}

/** Short description of a trigger for the start step's summary line. */
export function triggerSummary(
  trigger: WorkflowTrigger,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  switch (trigger.type) {
    case 'command':
      return `/${str(trigger.name) || '…'}`;
    case 'schedule': {
      const mode = scheduleMode(trigger);
      const cron = str(trigger.cron);
      if (mode === 'interval')
        return t('workflows.triggers.summary.every', { count: trigger.every });
      if (mode === 'daily')
        return t('workflows.triggers.summary.daily', { time: cronTime(cron) });
      if (mode === 'weekly')
        return t('workflows.triggers.summary.weekly', {
          day: t(`workflows.triggers.weekdays.${cron.split(' ')[4]}`),
          time: cronTime(cron),
        });
      return cron;
    }
    case 'event':
      return t('workflows.triggers.summary.event', {
        count: ((trigger.events as string[]) ?? []).length,
      });
    default:
      return t(`workflows.triggers.kinds.${trigger.type}`);
  }
}

function Card({
  kind,
  onRemove,
  children,
}: {
  kind: Kind;
  onRemove?: () => void;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const Icon = ICONS[kind];
  return (
    <div
      className="space-y-3 rounded-lg border p-3"
      data-testid={`trigger-${kind}`}
    >
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <span className="text-sm font-medium">
          {t(`workflows.triggers.kinds.${kind}`)}
        </span>
        {onRemove && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="ml-auto size-7 text-muted-foreground"
            aria-label={t('common.delete')}
            onClick={onRemove}
          >
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
      {children}
    </div>
  );
}

function BotPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  if (!resources.bots.length) {
    return (
      <p className="text-xs text-muted-foreground">
        {t('workflows.triggers.noBots')}
      </p>
    );
  }
  return (
    <OptionSelect
      value={value}
      onChange={onChange}
      ariaLabel={t('workflows.triggers.bot')}
      options={resources.bots.map((bot) => ({
        value: bot.uuid,
        label: bot.name,
      }))}
    />
  );
}

function CommandFields({
  trigger,
  update,
}: {
  trigger: Row;
  update: (patch: Row) => void;
}) {
  const { t } = useTranslation();
  const { resources } = useEditor();
  const args = (trigger.args as Row[]) ?? [];
  const bots =
    trigger.bots === 'all' || !trigger.bots
      ? 'all'
      : (trigger.bots as string[]);
  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <Field label={t('workflows.triggers.command.name')}>
          <div className="flex items-center rounded-md border pl-2.5 focus-within:ring-[3px] focus-within:ring-ring/50">
            <span className="text-sm text-muted-foreground">/</span>
            <Input
              className="border-0 pl-0.5 shadow-none focus-visible:ring-0"
              value={str(trigger.name)}
              placeholder={t('workflows.triggers.command.namePlaceholder')}
              onChange={(event) =>
                update({ name: event.target.value.replace(/[\s/]/g, '') })
              }
            />
          </div>
        </Field>
        <Field label={t('workflows.triggers.command.aliases')}>
          <ListInput
            value={(trigger.aliases as string[]) ?? []}
            placeholder={t('workflows.triggers.command.aliasesPlaceholder')}
            clean={(item) => item.replace(/\//g, '')}
            onChange={(aliases) => update({ aliases })}
          />
        </Field>
      </div>
      <Field
        label={t('workflows.triggers.command.args')}
        hint={t('workflows.triggers.command.argsHint')}
      >
        <div className="space-y-1.5">
          {args.map((arg, index) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                className="h-8"
                value={str(arg.name)}
                placeholder={t('workflows.triggers.command.argPlaceholder')}
                onChange={(event) =>
                  update({
                    args: args.map((item, i) =>
                      i === index
                        ? { ...item, name: event.target.value.trim() }
                        : item,
                    ),
                  })
                }
              />
              <label className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                <Checkbox
                  checked={arg.required === true}
                  onCheckedChange={(checked) =>
                    update({
                      args: args.map((item, i) =>
                        i === index
                          ? { ...item, required: checked === true }
                          : item,
                      ),
                    })
                  }
                />
                {t('workflows.triggers.command.required')}
              </label>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="size-8 shrink-0 text-muted-foreground"
                onClick={() =>
                  update({ args: args.filter((_, i) => i !== index) })
                }
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() =>
              update({ args: [...args, { name: '', required: false }] })
            }
          >
            <Plus className="size-3.5" />
            {t('workflows.triggers.command.addArg')}
          </Button>
        </div>
      </Field>
      <Field label={t('workflows.triggers.command.description')}>
        <Input
          value={str(trigger.description)}
          placeholder={t('workflows.triggers.command.descriptionPlaceholder')}
          onChange={(event) => update({ description: event.target.value })}
        />
      </Field>
      <Field label={t('workflows.triggers.command.bots')}>
        <div className="space-y-1.5 rounded-md border p-2">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={bots === 'all'}
              onCheckedChange={(checked) =>
                update({ bots: checked === true ? 'all' : [] })
              }
            />
            {t('workflows.triggers.command.allBots')}
          </label>
          {bots !== 'all' &&
            resources.bots.map((bot) => (
              <label
                key={bot.uuid}
                className="flex items-center gap-2 pl-6 text-sm"
              >
                <Checkbox
                  checked={bots.includes(bot.uuid)}
                  onCheckedChange={(checked) =>
                    update({
                      bots:
                        checked === true
                          ? [...bots, bot.uuid]
                          : bots.filter((item) => item !== bot.uuid),
                    })
                  }
                />
                {bot.name}
              </label>
            ))}
        </div>
      </Field>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium">
            {t('workflows.triggers.command.adminOnly')}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('workflows.triggers.command.adminOnlyHint')}
          </p>
        </div>
        <Switch
          checked={trigger.admin_only === true}
          onCheckedChange={(checked) => update({ admin_only: checked })}
        />
      </div>
    </>
  );
}

function ScheduleFields({
  trigger,
  update,
}: {
  trigger: Row;
  update: (patch: Row) => void;
}) {
  const { t } = useTranslation();
  const { timezone } = useEditor();
  const mode = scheduleMode(trigger);
  const cron = str(trigger.cron) || '0 8 * * *';
  const targets = (trigger.targets as Row[]) ?? [];
  const setTime = (time: string, weekday?: string) => {
    const [hour = '8', minute = '0'] = time.split(':');
    const day = weekday ?? (mode === 'weekly' ? cron.split(' ')[4] : '*');
    update({
      cron: `${Number(minute)} ${Number(hour)} * * ${day}`,
      every: undefined,
    });
  };
  return (
    <>
      <Field
        label={t('workflows.triggers.schedule.when')}
        hint={t('workflows.triggers.schedule.timezone', { timezone })}
      >
        <div className="flex flex-wrap gap-1.5">
          <OptionSelect
            className="w-32"
            value={mode}
            onChange={(value) => {
              if (value === 'interval') update({ every: 60, cron: undefined });
              else if (value === 'daily')
                update({ cron: '0 8 * * *', every: undefined });
              else if (value === 'weekly')
                update({ cron: '0 8 * * 1', every: undefined });
              else update({ cron, every: undefined });
            }}
            options={(['daily', 'weekly', 'interval', 'cron'] as const).map(
              (value) => ({
                value,
                label: t(`workflows.triggers.schedule.modes.${value}`),
              }),
            )}
          />
          {mode === 'weekly' && (
            <OptionSelect
              className="w-28"
              value={cron.split(' ')[4]}
              onChange={(value) => setTime(cronTime(cron), value)}
              options={WEEKDAYS.map((day) => ({
                value: String(day),
                label: t(`workflows.triggers.weekdays.${day}`),
              }))}
            />
          )}
          {(mode === 'daily' || mode === 'weekly') && (
            <Input
              type="time"
              className="w-28"
              value={cronTime(cron)}
              onChange={(event) => setTime(event.target.value)}
            />
          )}
          {mode === 'interval' && (
            <div className="flex items-center gap-1.5 text-sm">
              <Input
                type="number"
                min={1}
                max={1440}
                className="w-24"
                value={String(trigger.every ?? 60)}
                onChange={(event) =>
                  update({
                    every: Math.min(
                      1440,
                      Math.max(1, Number(event.target.value) || 1),
                    ),
                  })
                }
              />
              {t('workflows.triggers.schedule.minutes')}
            </div>
          )}
          {mode === 'cron' && (
            <Input
              className="w-40 font-mono"
              value={cron}
              placeholder="0 8 * * 1-5"
              onChange={(event) => update({ cron: event.target.value })}
            />
          )}
        </div>
      </Field>
      <Field
        label={t('workflows.triggers.bot')}
        hint={t('workflows.triggers.schedule.botHint')}
      >
        <BotPicker
          value={str(trigger.bot_uuid)}
          onChange={(value) => update({ bot_uuid: value })}
        />
      </Field>
      <Field
        label={t('workflows.triggers.schedule.targets')}
        hint={t('workflows.triggers.schedule.targetsHint')}
      >
        <div className="space-y-1.5">
          {targets.map((target, index) => (
            <div key={index} className="flex gap-1.5">
              <OptionSelect
                className="w-24 shrink-0"
                value={str(target.type) || 'group'}
                onChange={(value) =>
                  update({
                    targets: targets.map((item, i) =>
                      i === index ? { ...item, type: value } : item,
                    ),
                  })
                }
                options={[
                  { value: 'group', label: t('workflows.send.group') },
                  { value: 'person', label: t('workflows.send.person') },
                ]}
              />
              <Input
                value={str(target.id)}
                placeholder={t('workflows.send.targetId')}
                onChange={(event) =>
                  update({
                    targets: targets.map((item, i) =>
                      i === index
                        ? { ...item, id: event.target.value.trim() }
                        : item,
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
                  update({ targets: targets.filter((_, i) => i !== index) })
                }
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() =>
              update({ targets: [...targets, { type: 'group', id: '' }] })
            }
          >
            <Plus className="size-3.5" />
            {t('workflows.triggers.schedule.addTarget')}
          </Button>
        </div>
      </Field>
    </>
  );
}

function EventFields({
  trigger,
  update,
}: {
  trigger: Row;
  update: (patch: Row) => void;
}) {
  const { t } = useTranslation();
  const events = (trigger.events as string[]) ?? [];
  return (
    <>
      <div className="grid grid-cols-1 gap-1.5">
        {EVENT_TYPES.map((event) => (
          <label key={event} className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={events.includes(event)}
              onCheckedChange={(checked) =>
                update({
                  events:
                    checked === true
                      ? [...events, event]
                      : events.filter((item) => item !== event),
                })
              }
            />
            {eventPatternLabel(event, t)}
          </label>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {t('workflows.triggers.event.hint')}
      </p>
      <Button asChild variant="link" className="h-auto p-0 text-xs">
        <Link to="/home/bots">{t('workflows.start.openBots')}</Link>
      </Button>
    </>
  );
}

function WebhookFields({
  trigger,
  update,
}: {
  trigger: Row;
  update: (patch: Row) => void;
}) {
  const { t } = useTranslation();
  const { workflowId } = useEditor();
  const secret = str(trigger.secret);
  const bot = str(trigger.bot_uuid);
  const url =
    secret && bot
      ? `${window.location.origin}/api/v1/workflows/hooks/${bot}/${workflowId}/${secret}`
      : '';
  return (
    <>
      <Field
        label={t('workflows.triggers.bot')}
        hint={t('workflows.triggers.webhook.botHint')}
      >
        <BotPicker
          value={bot}
          onChange={(value) => update({ bot_uuid: value })}
        />
      </Field>
      <Field
        label={t('workflows.triggers.webhook.url')}
        hint={t('workflows.triggers.webhook.urlHint')}
      >
        {url ? (
          <div className="flex gap-1.5">
            <Input readOnly value={url} className="font-mono text-xs" />
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label={t('common.copy', { defaultValue: 'Copy' })}
              onClick={() => {
                void navigator.clipboard.writeText(url);
                toast.success(t('workflows.triggers.webhook.copied'));
              }}
            >
              <Copy className="size-4" />
            </Button>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {t('workflows.triggers.webhook.saveFirst')}
          </p>
        )}
      </Field>
    </>
  );
}

export default function TriggersEditor() {
  const { t } = useTranslation();
  const { triggers, setTriggers, setTimezone, timezone, readOnly } =
    useEditor();
  const update = (index: number, patch: Row) =>
    setTriggers((current) =>
      current.map((item, i) => {
        if (i !== index) return item;
        const next: Row = { ...item, ...patch };
        for (const key of Object.keys(next)) {
          if (next[key] === undefined) delete next[key];
        }
        return next as WorkflowTrigger;
      }),
    );
  const add = (kind: Kind) => {
    const defaults: Record<Kind, WorkflowTrigger> = {
      message: { type: 'message' },
      command: {
        type: 'command',
        name: '',
        aliases: [],
        args: [],
        bots: 'all',
      },
      schedule: {
        type: 'schedule',
        cron: '0 8 * * *',
        bot_uuid: '',
        targets: [{ type: 'group', id: '' }],
      },
      event: { type: 'event', events: ['group.member_joined'] },
      webhook: { type: 'webhook', bot_uuid: '' },
    };
    if (kind === 'schedule' && timezone === 'UTC') {
      setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');
    }
    setTriggers((current) => [...current, defaults[kind]]);
  };
  const available = (
    ['message', 'command', 'schedule', 'event', 'webhook'] as Kind[]
  ).filter(
    (kind) =>
      !SINGLE.includes(kind) || !triggers.some((item) => item.type === kind),
  );
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {t('workflows.triggers.intro')}
      </p>
      {triggers.map((trigger, index) => (
        <Card
          key={index}
          kind={trigger.type}
          onRemove={
            readOnly || triggers.length === 1
              ? undefined
              : () =>
                  setTriggers((current) =>
                    current.filter((_, i) => i !== index),
                  )
          }
        >
          {trigger.type === 'message' && (
            <>
              <p className="text-xs text-muted-foreground">
                {t('workflows.start.messageHint')}
              </p>
              <Button asChild variant="link" className="h-auto p-0 text-xs">
                <Link to="/home/bots">{t('workflows.start.openBots')}</Link>
              </Button>
            </>
          )}
          {trigger.type === 'command' && (
            <CommandFields
              trigger={trigger}
              update={(patch) => update(index, patch)}
            />
          )}
          {trigger.type === 'schedule' && (
            <ScheduleFields
              trigger={trigger}
              update={(patch) => update(index, patch)}
            />
          )}
          {trigger.type === 'event' && (
            <EventFields
              trigger={trigger}
              update={(patch) => update(index, patch)}
            />
          )}
          {trigger.type === 'webhook' && (
            <WebhookFields
              trigger={trigger}
              update={(patch) => update(index, patch)}
            />
          )}
        </Card>
      ))}
      {!readOnly && available.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-full border-dashed"
            >
              <Plus className="size-4" />
              {t('workflows.triggers.add')}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            {available.map((kind) => {
              const Icon = ICONS[kind];
              return (
                <DropdownMenuItem
                  key={kind}
                  onClick={() => add(kind)}
                  className="items-start gap-2.5 py-2"
                >
                  <Icon className="mt-0.5 size-4" />
                  <span>
                    <span className="block text-sm">
                      {t(`workflows.triggers.kinds.${kind}`)}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {t(`workflows.triggers.descriptions.${kind}`)}
                    </span>
                  </span>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
