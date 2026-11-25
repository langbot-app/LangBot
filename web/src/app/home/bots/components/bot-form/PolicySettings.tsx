import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  AtSign,
  ChevronRight,
  Clock,
  FileText,
  Gauge,
  Layers,
  MessageSquareOff,
  MessagesSquare,
  Quote,
  ShieldAlert,
  UserCheck,
  X,
  type LucideIcon,
} from 'lucide-react';
import type {
  MessagePolicy,
  MessagePolicySectionName,
} from '@/app/infra/entities/api';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

type Values = Record<string, unknown>;
type Write = (
  section: MessagePolicySectionName,
  stage: string,
  values: Values,
) => void;

const k = (key: string) => `bots.policy.settings.${key}`;

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}
function num(value: unknown, fallback = 0): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/** Chips plus an input; Enter or the add button appends a value. */
function ListInput({
  value,
  onChange,
  placeholder,
  mono,
  disabled,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  mono?: boolean;
  disabled?: boolean;
}) {
  const [draft, setDraft] = useState('');
  function add() {
    const item = draft.trim();
    if (!item || value.includes(item)) return setDraft('');
    onChange([...value, item]);
    setDraft('');
  }
  return (
    <div className="space-y-2">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((item) => (
            <Badge
              key={item}
              variant="secondary"
              className={cn('gap-1 pr-1 text-xs', mono && 'font-mono')}
            >
              {item}
              <button
                type="button"
                disabled={disabled}
                aria-label={`remove ${item}`}
                className="rounded-sm p-0.5 hover:bg-background/60"
                onClick={() => onChange(value.filter((v) => v !== item))}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        value={draft}
        disabled={disabled}
        placeholder={placeholder}
        className={cn('h-8 max-w-sm text-sm', mono && 'font-mono')}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            add();
          }
        }}
        onBlur={add}
      />
    </div>
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  disabled,
  className,
}: {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <Input
      type="number"
      value={value}
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      className={cn('h-8 w-20 text-sm tabular-nums', className)}
      onChange={(event) => {
        const next = Number(event.target.value);
        if (Number.isFinite(next)) onChange(next);
      }}
    />
  );
}

function ToggleLine({
  id,
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="space-y-0.5">
        <Label htmlFor={id} className="text-sm font-normal">
          {label}
        </Label>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <Switch
        id={id}
        checked={checked}
        disabled={disabled}
        onCheckedChange={onChange}
      />
    </div>
  );
}

/** One setting: icon, name and a plain-language summary; expands to edit. */
function SettingRow({
  id,
  icon: Icon,
  title,
  summary,
  warning,
  children,
}: {
  id: string;
  icon: LucideIcon;
  title: string;
  summary: string;
  warning?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} data-policy-setting={id}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
        >
          <Icon className="size-4 shrink-0 text-muted-foreground" />
          <span className="w-32 shrink-0 text-sm font-medium sm:w-40">
            {title}
          </span>
          <span
            className={cn(
              'min-w-0 flex-1 truncate text-sm text-muted-foreground',
              warning && 'text-amber-700 dark:text-amber-400',
            )}
            data-policy-summary
          >
            {warning && (
              <AlertTriangle className="mr-1 inline size-3.5 -translate-y-px" />
            )}
            {summary}
          </span>
          <ChevronRight
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-4 border-t bg-muted/20 px-4 py-4 sm:pl-11">
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function Group({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2" aria-label={title}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="divide-y overflow-hidden rounded-lg border bg-card">
        {children}
      </div>
    </section>
  );
}

/**
 * Message policy settings grouped by the questions a bot owner asks: who
 * gets replies, how incoming messages are read, abuse protection, how the
 * reply looks, and what happens on errors. Values keep the stored
 * ``trigger / safety / output`` keys.
 */
export default function PolicySettings({
  policy,
  neutral,
  onWrite,
  disabled,
  streamingNote,
}: {
  policy: MessagePolicy;
  neutral: MessagePolicy;
  onWrite: Write;
  disabled?: boolean;
  streamingNote: string;
}) {
  const { t } = useTranslation();
  const stage = (section: MessagePolicySectionName, name: string): Values => ({
    ...((neutral[section]?.[name] as Values) ?? {}),
    ...((policy[section]?.[name] as Values) ?? {}),
  });
  const patch =
    (section: MessagePolicySectionName, name: string) => (values: Values) =>
      onWrite(section, name, { ...stage(section, name), ...values });

  const group = stage('trigger', 'group-respond-rules');
  const setGroup = patch('trigger', 'group-respond-rules');
  const access = stage('trigger', 'access-control');
  const setAccess = patch('trigger', 'access-control');
  const ignore = stage('trigger', 'ignore-rules');
  const setIgnore = patch('trigger', 'ignore-rules');
  const aggregation = stage('trigger', 'message-aggregation');
  const setAggregation = patch('trigger', 'message-aggregation');
  const triggerMisc = stage('trigger', 'misc');
  const setTriggerMisc = patch('trigger', 'misc');
  const filter = stage('safety', 'content-filter');
  const setFilter = patch('safety', 'content-filter');
  const rate = stage('safety', 'rate-limit');
  const setRate = patch('safety', 'rate-limit');
  const longText = stage('output', 'long-text-processing');
  const setLongText = patch('output', 'long-text-processing');
  const delay = stage('output', 'force-delay');
  const setDelay = patch('output', 'force-delay');
  const outMisc = stage('output', 'misc');
  const setOutMisc = patch('output', 'misc');

  // --- Group reply conditions ---
  const prefixes = list(group.prefix);
  const regexps = list(group.regexp);
  const randomPct = Math.round(num(group.random) * 100);
  const groupConditions = [
    group.at ? t(k('group.whenAt')) : '',
    prefixes.length
      ? t(k('group.whenPrefix'), { prefixes: prefixes.join(' / ') })
      : '',
    regexps.length ? t(k('group.whenRegexp'), { count: regexps.length }) : '',
    randomPct > 0 ? t(k('group.whenRandom'), { percent: randomPct }) : '',
  ].filter(Boolean);
  const groupSummary = !group.enabled
    ? t(k('group.all'))
    : groupConditions.length
      ? t(k('group.some'), { conditions: groupConditions.join(t(k('or'))) })
      : t(k('group.none'));

  // --- Access list ---
  const accessMode = String(access.mode ?? 'blacklist');
  const blacklist = list(access.blacklist);
  const whitelist = list(access.whitelist);
  const accessChoice =
    accessMode === 'whitelist'
      ? 'whitelist'
      : blacklist.length
        ? 'blacklist'
        : 'everyone';
  const accessSummary =
    accessChoice === 'everyone'
      ? t(k('access.everyoneSummary'))
      : accessChoice === 'blacklist'
        ? t(k('access.blacklistSummary'), { count: blacklist.length })
        : whitelist.length
          ? t(k('access.whitelistSummary'), { count: whitelist.length })
          : t(k('access.whitelistEmpty'));

  // --- Ignore rules ---
  const ignorePrefixes = list(ignore.prefix);
  const ignoreRegexps = list(ignore.regexp);
  const ignoreCount = ignorePrefixes.length + ignoreRegexps.length;

  // --- Rate limit / delay / long text ---
  const delayMin = num(delay.min);
  const delayMax = num(delay.max);
  const longStrategy = String(longText.strategy ?? 'none');
  const exception = String(outMisc['exception-handling'] ?? 'show-hint');
  const hintKeys = [
    'failure-hint',
    'rate-limit-hint',
    'content-filter-hint',
    'content-filter-error-hint',
  ];
  const customHints = hintKeys.filter((key) => String(outMisc[key] ?? ''));

  const replyStyle = [
    outMisc['at-sender'] ? t(k('style.atSender')) : '',
    outMisc['quote-origin'] ? t(k('style.quote')) : '',
  ].filter(Boolean);

  return (
    <fieldset
      disabled={disabled}
      className={cn('flex flex-col gap-6', disabled && 'opacity-70')}
    >
      <Group title={t(k('who.title'))} hint={t(k('who.hint'))}>
        <SettingRow
          id="group-respond-rules"
          icon={MessagesSquare}
          title={t(k('group.title'))}
          summary={groupSummary}
          warning={Boolean(group.enabled) && groupConditions.length === 0}
        >
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={group.enabled ? 'some' : 'all'}
            onValueChange={(value) =>
              value && setGroup({ enabled: value === 'some' })
            }
            disabled={disabled}
          >
            <ToggleGroupItem value="all" className="px-3">
              {t(k('group.allOption'))}
            </ToggleGroupItem>
            <ToggleGroupItem value="some" className="px-3">
              {t(k('group.someOption'))}
            </ToggleGroupItem>
          </ToggleGroup>
          {Boolean(group.enabled) && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {t(k('group.anyHint'))}
              </p>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={Boolean(group.at)}
                  disabled={disabled}
                  onCheckedChange={(checked) =>
                    setGroup({ at: checked === true })
                  }
                />
                {t(k('group.atLabel'))}
              </label>
              <div className="space-y-1.5">
                <Label className="text-sm font-normal">
                  {t(k('group.prefixLabel'))}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t(k('group.prefixHint'))}
                </p>
                <ListInput
                  value={prefixes}
                  disabled={disabled}
                  placeholder={t(k('group.prefixPlaceholder'))}
                  onChange={(next) => setGroup({ prefix: next })}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm font-normal">
                  {t(k('group.regexpLabel'))}
                </Label>
                <ListInput
                  mono
                  value={regexps}
                  disabled={disabled}
                  placeholder={t(k('group.regexpPlaceholder'))}
                  onChange={(next) => setGroup({ regexp: next })}
                />
              </div>
              <div className="max-w-sm space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-sm font-normal">
                    {t(k('group.randomLabel'))}
                  </Label>
                  <span className="text-sm tabular-nums">{randomPct}%</span>
                </div>
                <Slider
                  value={[randomPct]}
                  min={0}
                  max={100}
                  step={5}
                  disabled={disabled}
                  onValueChange={([value]) => setGroup({ random: value / 100 })}
                />
                <p className="text-xs text-muted-foreground">
                  {t(k('group.randomHint'))}
                </p>
              </div>
            </div>
          )}
        </SettingRow>

        <SettingRow
          id="access-control"
          icon={UserCheck}
          title={t(k('access.title'))}
          summary={accessSummary}
          warning={accessChoice === 'whitelist' && whitelist.length === 0}
        >
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={accessChoice}
            disabled={disabled}
            onValueChange={(value) => {
              if (!value) return;
              if (value === 'everyone')
                setAccess({ mode: 'blacklist', blacklist: [] });
              else setAccess({ mode: value });
            }}
          >
            <ToggleGroupItem value="everyone" className="px-3">
              {t(k('access.everyone'))}
            </ToggleGroupItem>
            <ToggleGroupItem value="blacklist" className="px-3">
              {t(k('access.blacklist'))}
            </ToggleGroupItem>
            <ToggleGroupItem value="whitelist" className="px-3">
              {t(k('access.whitelist'))}
            </ToggleGroupItem>
          </ToggleGroup>
          {accessChoice !== 'everyone' && (
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">
                {t(k('access.format'))}
              </p>
              <ListInput
                mono
                value={accessChoice === 'whitelist' ? whitelist : blacklist}
                disabled={disabled}
                placeholder="group_123456"
                onChange={(next) =>
                  setAccess(
                    accessChoice === 'whitelist'
                      ? { whitelist: next }
                      : { blacklist: next },
                  )
                }
              />
            </div>
          )}
        </SettingRow>

        <SettingRow
          id="ignore-rules"
          icon={MessageSquareOff}
          title={t(k('ignore.title'))}
          summary={
            ignoreCount
              ? t(k('ignore.summary'), { count: ignoreCount })
              : t(k('ignore.none'))
          }
        >
          <p className="text-xs text-muted-foreground">{t(k('ignore.hint'))}</p>
          <div className="space-y-1.5">
            <Label className="text-sm font-normal">
              {t(k('ignore.prefixLabel'))}
            </Label>
            <ListInput
              value={ignorePrefixes}
              disabled={disabled}
              placeholder={t(k('ignore.prefixPlaceholder'))}
              onChange={(next) => setIgnore({ prefix: next })}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-sm font-normal">
              {t(k('group.regexpLabel'))}
            </Label>
            <ListInput
              mono
              value={ignoreRegexps}
              disabled={disabled}
              placeholder={t(k('group.regexpPlaceholder'))}
              onChange={(next) => setIgnore({ regexp: next })}
            />
          </div>
        </SettingRow>
      </Group>

      <Group title={t(k('read.title'))}>
        <SettingRow
          id="message-aggregation"
          icon={Layers}
          title={t(k('aggregate.title'))}
          summary={
            aggregation.enabled
              ? t(k('aggregate.on'), { seconds: num(aggregation.delay, 1.5) })
              : t(k('off'))
          }
        >
          <ToggleLine
            id="policy-aggregation"
            label={t(k('aggregate.label'))}
            hint={t(k('aggregate.hint'))}
            checked={Boolean(aggregation.enabled)}
            disabled={disabled}
            onChange={(enabled) => setAggregation({ enabled })}
          />
          {Boolean(aggregation.enabled) && (
            <div className="flex items-center gap-2 text-sm">
              {t(k('aggregate.wait'))}
              <NumberInput
                value={num(aggregation.delay, 1.5)}
                min={1}
                max={10}
                step={0.5}
                disabled={disabled}
                onChange={(value) =>
                  setAggregation({ delay: Math.min(10, Math.max(1, value)) })
                }
              />
              {t(k('seconds'))}
            </div>
          )}
        </SettingRow>
        <SettingRow
          id="combine-quote"
          icon={Quote}
          title={t(k('quoteIn.title'))}
          summary={
            triggerMisc['combine-quote-message']
              ? t(k('quoteIn.on'))
              : t(k('off'))
          }
        >
          <ToggleLine
            id="policy-combine-quote"
            label={t(k('quoteIn.label'))}
            hint={t(k('quoteIn.hint'))}
            checked={Boolean(triggerMisc['combine-quote-message'])}
            disabled={disabled}
            onChange={(value) =>
              setTriggerMisc({ 'combine-quote-message': value })
            }
          />
        </SettingRow>
      </Group>

      <Group title={t(k('safety.title'))}>
        <SettingRow
          id="content-filter"
          icon={ShieldAlert}
          title={t(k('filter.title'))}
          summary={
            filter['check-sensitive-words']
              ? t(k(`filter.scope.${String(filter.scope ?? 'all')}`))
              : t(k('off'))
          }
        >
          <ToggleLine
            id="policy-sensitive-words"
            label={t(k('filter.label'))}
            hint={t(k('filter.hint'))}
            checked={Boolean(filter['check-sensitive-words'])}
            disabled={disabled}
            onChange={(value) => setFilter({ 'check-sensitive-words': value })}
          />
          {Boolean(filter['check-sensitive-words']) && (
            <div className="flex items-center gap-2 text-sm">
              {t(k('filter.check'))}
              <Select
                value={String(filter.scope ?? 'all')}
                disabled={disabled}
                onValueChange={(scope) => setFilter({ scope })}
              >
                <SelectTrigger className="h-8 w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['all', 'income-msg', 'output-msg'].map((scope) => (
                    <SelectItem key={scope} value={scope}>
                      {t(k(`filter.scope.${scope}`))}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </SettingRow>
        <SettingRow
          id="rate-limit"
          icon={Gauge}
          title={t(k('rate.title'))}
          summary={
            rate.enabled
              ? t(k('rate.summary'), {
                  count: num(rate.limitation, 60),
                  seconds: num(rate['window-length'], 60),
                  strategy: t(k(`rate.strategy.${String(rate.strategy)}`)),
                })
              : t(k('off'))
          }
        >
          <ToggleLine
            id="policy-rate-limit"
            label={t(k('rate.label'))}
            hint={t(k('rate.hint'))}
            checked={Boolean(rate.enabled)}
            disabled={disabled}
            onChange={(enabled) => setRate({ enabled })}
          />
          {Boolean(rate.enabled) && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {t(k('rate.every'))}
                <NumberInput
                  value={num(rate['window-length'], 60)}
                  min={1}
                  disabled={disabled}
                  onChange={(value) =>
                    setRate({ 'window-length': Math.max(1, value) })
                  }
                />
                {t(k('rate.secondsAtMost'))}
                <NumberInput
                  value={num(rate.limitation, 60)}
                  min={1}
                  disabled={disabled}
                  onChange={(value) =>
                    setRate({ limitation: Math.max(1, value) })
                  }
                />
                {t(k('rate.messages'))}
              </div>
              <div className="flex items-center gap-2 text-sm">
                {t(k('rate.whenExceeded'))}
                <ToggleGroup
                  type="single"
                  variant="outline"
                  size="sm"
                  value={String(rate.strategy ?? 'drop')}
                  disabled={disabled}
                  onValueChange={(strategy) =>
                    strategy && setRate({ strategy })
                  }
                >
                  {['drop', 'wait'].map((strategy) => (
                    <ToggleGroupItem
                      key={strategy}
                      value={strategy}
                      className="px-3"
                    >
                      {t(k(`rate.strategy.${strategy}`))}
                    </ToggleGroupItem>
                  ))}
                </ToggleGroup>
              </div>
            </>
          )}
        </SettingRow>
      </Group>

      <Group title={t(k('reply.title'))} hint={streamingNote}>
        <SettingRow
          id="reply-style"
          icon={AtSign}
          title={t(k('style.title'))}
          summary={
            replyStyle.length ? replyStyle.join(' · ') : t(k('style.plain'))
          }
        >
          <ToggleLine
            id="policy-at-sender"
            label={t(k('style.atSenderLabel'))}
            checked={Boolean(outMisc['at-sender'])}
            disabled={disabled}
            onChange={(value) => setOutMisc({ 'at-sender': value })}
          />
          <ToggleLine
            id="policy-quote-origin"
            label={t(k('style.quoteLabel'))}
            checked={Boolean(outMisc['quote-origin'])}
            disabled={disabled}
            onChange={(value) => setOutMisc({ 'quote-origin': value })}
          />
        </SettingRow>
        <SettingRow
          id="force-delay"
          icon={Clock}
          title={t(k('delay.title'))}
          summary={
            delayMax > 0
              ? t(k('delay.summary'), { min: delayMin, max: delayMax })
              : t(k('delay.none'))
          }
        >
          <p className="text-xs text-muted-foreground">{t(k('delay.hint'))}</p>
          <div className="flex items-center gap-2 text-sm">
            {t(k('delay.wait'))}
            <NumberInput
              value={delayMin}
              min={0}
              disabled={disabled}
              onChange={(value) => {
                const min = Math.max(0, value);
                setDelay({ min, max: Math.max(min, delayMax) });
              }}
            />
            –
            <NumberInput
              value={delayMax}
              min={0}
              disabled={disabled}
              onChange={(value) => {
                const max = Math.max(0, value);
                setDelay({ max, min: Math.min(delayMin, max) });
              }}
            />
            {t(k('seconds'))}
          </div>
        </SettingRow>
        <SettingRow
          id="long-text"
          icon={FileText}
          title={t(k('long.title'))}
          summary={
            longStrategy === 'none'
              ? t(k('long.none'))
              : t(k('long.summary'), {
                  threshold: num(longText.threshold, 1000),
                  strategy: t(k(`long.strategy.${longStrategy}`)),
                })
          }
        >
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {t(k('long.when'))}
            <NumberInput
              value={num(longText.threshold, 1000)}
              min={1}
              className="w-24"
              disabled={disabled || longStrategy === 'none'}
              onChange={(value) =>
                setLongText({ threshold: Math.max(1, value) })
              }
            />
            {t(k('long.chars'))}
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={longStrategy}
              disabled={disabled}
              onValueChange={(strategy) =>
                strategy && setLongText({ strategy })
              }
            >
              {['none', 'forward', 'image'].map((strategy) => (
                <ToggleGroupItem
                  key={strategy}
                  value={strategy}
                  className="px-3"
                >
                  {t(k(`long.strategy.${strategy}`))}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          {longStrategy === 'image' && (
            <div className="space-y-1.5">
              <Label className="text-sm font-normal">{t(k('long.font'))}</Label>
              <Input
                value={String(longText['font-path'] ?? '')}
                disabled={disabled}
                placeholder={t(k('long.fontPlaceholder'))}
                className="h-8 max-w-sm font-mono text-sm"
                onChange={(event) =>
                  setLongText({ 'font-path': event.target.value })
                }
              />
            </div>
          )}
        </SettingRow>
      </Group>

      <Group title={t(k('errors.title'))}>
        <SettingRow
          id="exception-handling"
          icon={AlertTriangle}
          title={t(k('errors.rowTitle'))}
          summary={
            t(k(`errors.mode.${exception}`)) +
            (customHints.length
              ? ` · ${t(k('errors.customCount'), { count: customHints.length })}`
              : '')
          }
        >
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={exception}
            disabled={disabled}
            onValueChange={(value) =>
              value && setOutMisc({ 'exception-handling': value })
            }
          >
            {['show-hint', 'show-error', 'hide'].map((mode) => (
              <ToggleGroupItem key={mode} value={mode} className="px-3">
                {t(k(`errors.mode.${mode}`))}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p className="text-xs text-muted-foreground">
            {t(k(`errors.modeHint.${exception}`))}
          </p>
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {t(k('errors.hintsIntro'))}
            </p>
            {hintKeys.map((key) => (
              <div key={key} className="space-y-1">
                <Label className="text-sm font-normal">
                  {t(k(`errors.hints.${key}`))}
                </Label>
                <Input
                  value={String(outMisc[key] ?? '')}
                  disabled={disabled}
                  placeholder={t(k('errors.defaultPlaceholder'))}
                  className="h-8 max-w-md text-sm"
                  onChange={(event) =>
                    setOutMisc({ [key]: event.target.value })
                  }
                />
              </div>
            ))}
          </div>
        </SettingRow>
      </Group>
    </fieldset>
  );
}
