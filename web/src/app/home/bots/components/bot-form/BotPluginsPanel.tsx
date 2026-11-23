import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Inbox,
  MessageSquareReply,
  Send,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  Workflow,
  Eye,
  Settings2,
  AlertCircle,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  Agent,
  BotCommandSettings,
  CommandProcessorDescriptor,
  EventBinding,
  HookProcessor,
  MessagePolicy,
  PlatformCommandCapability,
  PluginRegistration,
  PluginSelection,
} from '@/app/infra/entities/api';
import type { Plugin } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { AuthenticatedPluginIcon } from '@/components/AuthenticatedPluginIcon';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { pluginComponentIconMap } from '@/app/home/plugins/components/plugin-market/PluginComponentIcons';
import PolicyScopeSelect, { BOT_SCOPE } from './PolicyScopeSelect';
import CommandPrefixPopover from './CommandPrefixPopover';
import CommandConfigDialog from './CommandConfigDialog';
import PlatformCommandRegistration from './PlatformCommandRegistration';
import {
  DEFAULT_COMMAND_SETTINGS,
  commandProcessorPluginId,
  hasCommandSettings,
} from './command-processors';
import {
  DEFAULT_PLUGIN_SELECTION,
  LIFECYCLE_STEPS,
  LifecycleStep,
  eventStep,
  hasPluginOverride,
  isMessageRoute,
  routeKey,
  routeProcessor,
  selectionIncludes,
  toggleSelection,
} from './message-policy';

const STEP_ICONS: Record<LifecycleStep, React.ElementType> = {
  received: Inbox,
  command: TerminalSquare,
  admission: ShieldCheck,
  before: Sparkles,
  process: Workflow,
  after: MessageSquareReply,
  send: Send,
};

interface PluginRow {
  id: string;
  author: string;
  name: string;
  label: string;
  globallyEnabled: boolean;
  registration?: PluginRegistration;
  hasCommands: boolean;
  hasListeners: boolean;
}

interface HookState {
  event: string;
  step: LifecycleStep | null;
  active: boolean;
  reason?: string;
}

const COMPONENT_KINDS = new Set(['Command', 'EventListener']);
// Hooks come from EventListener components; reuse that component's icon.
const EventListenerIcon = pluginComponentIconMap.EventListener;

function pluginRows(
  plugins: Plugin[],
  registrations: Record<string, PluginRegistration> | null,
): PluginRow[] {
  const rows: PluginRow[] = [];
  for (const plugin of plugins) {
    const metadata = plugin.manifest?.manifest?.metadata;
    if (!metadata) continue;
    const author = metadata.author ?? '';
    const id = `${author}/${metadata.name}`;
    const kinds = new Set(
      (plugin.components ?? []).map((c) => c.manifest?.manifest?.kind),
    );
    const registration = registrations?.[id];
    const hasCommands =
      kinds.has('Command') || (registration?.commands?.length ?? 0) > 0;
    const hasListeners =
      kinds.has('EventListener') || (registration?.events?.length ?? 0) > 0;
    if (
      ![...kinds].some((kind) => COMPONENT_KINDS.has(kind)) &&
      !hasCommands &&
      !hasListeners
    )
      continue;
    rows.push({
      id,
      author,
      name: metadata.name,
      label: extractI18nObject(metadata.label) || metadata.name,
      globallyEnabled: plugin.enabled !== false,
      registration,
      hasCommands,
      hasListeners,
    });
  }
  return rows;
}

export default function BotPluginsPanel({
  botId,
  botPolicy,
  onBotPolicyChange,
  bindings,
  onBindingsChange,
  agents,
  scope,
  onScopeChange,
  commandSettings,
  onCommandSettingsChange,
  onAgentCreated,
  registrationCapability,
  dirty,
  children,
}: {
  botId: string;
  botPolicy: MessagePolicy | undefined;
  onBotPolicyChange: (policy: MessagePolicy) => void;
  bindings: EventBinding[];
  onBindingsChange: (bindings: EventBinding[]) => void;
  agents: Agent[];
  scope: string;
  onScopeChange: (scope: string) => void;
  commandSettings: BotCommandSettings | undefined;
  onCommandSettingsChange: (settings: BotCommandSettings) => void;
  onAgentCreated: (agent: Agent) => void;
  registrationCapability?: PlatformCommandCapability;
  dirty?: boolean;
  children?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const [plugins, setPlugins] = useState<Plugin[] | null>(null);
  const [registrations, setRegistrations] = useState<Record<
    string,
    PluginRegistration
  > | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [descriptors, setDescriptors] = useState<CommandProcessorDescriptor[]>(
    [],
  );
  const [configuring, setConfiguring] = useState<string | null>(null);

  const commands = { ...DEFAULT_COMMAND_SETTINGS, ...(commandSettings ?? {}) };
  const prefixes = commands.prefixes?.length ? commands.prefixes : ['/'];
  const commandPrefix = prefixes[0];

  useEffect(() => {
    let cancelled = false;
    httpClient
      .getAgentMetadata()
      .then((metadata) => {
        if (!cancelled) setDescriptors(metadata.command_processors ?? []);
      })
      .catch(() => {
        // Without descriptors plugins simply show no command settings.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      httpClient.getPlugins(),
      httpClient
        .getBotPluginRegistrations(botId, { includeDisabled: true })
        .catch(() => ({ plugins: null })),
    ])
      .then(([pluginResp, registrationResp]) => {
        if (cancelled) return;
        setPlugins(pluginResp.plugins ?? []);
        setRegistrations(registrationResp.plugins);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [botId]);

  const routeIndex = bindings.findIndex(
    (binding, index) =>
      isMessageRoute(binding) && routeKey(binding, index) === scope,
  );
  const route = routeIndex >= 0 ? bindings[routeIndex] : undefined;
  const effectiveScope = route ? scope : BOT_SCOPE;
  const botSelection = botPolicy?.plugins ?? DEFAULT_PLUGIN_SELECTION;
  const routeCustom = route ? hasPluginOverride(route.policy) : false;
  const selection: PluginSelection =
    route && routeCustom && route.policy?.plugins
      ? route.policy.plugins
      : botSelection;
  const editable = !route || routeCustom;

  const processors = useMemo(() => {
    const result = new Set<HookProcessor>(['command']);
    if (route) {
      result.add(routeProcessor(route));
    } else {
      for (const binding of bindings) {
        if (isMessageRoute(binding) && binding.enabled !== false)
          result.add(routeProcessor(binding));
      }
    }
    return result;
  }, [route, bindings]);

  const rows = useMemo(
    () => pluginRows(plugins ?? [], registrations),
    [plugins, registrations],
  );

  function processorName(processor: HookProcessor) {
    return t(`bots.pluginHooks.processors.${processor}`);
  }

  function hookStates(row: PluginRow): HookState[] {
    const events = row.registration?.events ?? [];
    return events.map((event) => {
      const step = eventStep(event);
      if (step === null)
        return {
          event,
          step,
          active: true,
          reason: t('bots.pluginHooks.reasons.observeOnly'),
        };
      const applies = row.registration?.event_processors?.[event];
      const active =
        !applies || applies.some((processor) => processors.has(processor));
      let reason: string | undefined;
      if (!active) {
        reason =
          event === 'PromptPreProcessing' && processors.has('agent')
            ? t('bots.pluginHooks.reasons.promptOnAgent')
            : t('bots.pluginHooks.reasons.notOnRoute', {
                processors: (applies ?? []).map(processorName).join(' / '),
              });
      } else if (event === 'NormalMessageResponded') {
        reason = t('bots.pluginHooks.reasons.streamObserveOnly');
      }
      return { event, step, active, reason };
    });
  }

  function writeSelection(selected: PluginSelection) {
    // Keep enabled plugins in list order: duplicate command names and hooks
    // resolve in this order, so it must match what the user sees.
    const order = new Map(rows.map((row, index) => [row.id, index]));
    const position = (item: { author: string; name: string }) =>
      order.get(`${item.author}/${item.name}`) ?? Number.MAX_SAFE_INTEGER;
    const next = {
      ...selected,
      plugins: [...selected.plugins].sort((a, b) => position(a) - position(b)),
    };
    if (!route) {
      onBotPolicyChange({ ...(botPolicy ?? {}), plugins: next });
      return;
    }
    const nextBindings = [...bindings];
    nextBindings[routeIndex] = {
      ...route,
      policy: { ...(route.policy ?? {}), plugins: next },
    };
    onBindingsChange(nextBindings);
  }

  function setRouteMode(mode: string) {
    if (!route || !mode) return;
    const nextBindings = [...bindings];
    nextBindings[routeIndex] = {
      ...route,
      policy: {
        ...(route.policy ?? {}),
        plugins: mode === 'custom' ? structuredClone(botSelection) : null,
      },
    };
    onBindingsChange(nextBindings);
  }

  const enabledRows = rows.filter((row) =>
    selectionIncludes(selection, row.id),
  );

  const descriptorMap = useMemo(
    () => new Map(descriptors.map((item) => [item.plugin_id, item])),
    [descriptors],
  );
  const commandInstances = useMemo(
    () =>
      new Map(
        agents
          .filter((agent) => agent.kind === 'command_processor' && agent.uuid)
          .map((agent) => [agent.uuid as string, agent]),
      ),
    [agents],
  );
  // Older Runtimes cannot report registrations; fall back to the commands the
  // plugin declares in its manifest.
  function commandsOf(row: PluginRow): string[] {
    return (
      row.registration?.commands ??
      descriptorMap.get(row.id)?.commands.map((command) => command.name) ??
      []
    );
  }
  function instanceBinding(pluginId: string) {
    return (commands.processors ?? []).find(
      (binding) =>
        binding.processor_uuid &&
        commandProcessorPluginId(
          commandInstances.get(binding.processor_uuid),
        ) === pluginId,
    );
  }
  function updateCommands(patch: Partial<BotCommandSettings>) {
    onCommandSettingsChange({ ...commands, prefixes, ...patch });
  }
  function bindInstance(pluginId: string, agent: Agent) {
    onAgentCreated(agent);
    updateCommands({
      processors: [
        ...(commands.processors ?? []).filter(
          (binding) => binding !== instanceBinding(pluginId),
        ),
        { processor_uuid: agent.uuid as string, enabled: true },
      ],
    });
  }
  function unbindInstance(pluginId: string) {
    const binding = instanceBinding(pluginId);
    updateCommands({
      processors: (commands.processors ?? []).filter(
        (item) => item !== binding,
      ),
    });
  }

  // The first enabled plugin in list order owns a command name.
  const commandOwners = new Map<string, PluginRow>();
  const overriddenBy = new Map<string, string>();
  for (const row of enabledRows) {
    for (const command of commandsOf(row)) {
      const owner = commandOwners.get(command);
      if (owner) overriddenBy.set(`${row.id}:${command}`, owner.label);
      else commandOwners.set(command, row);
    }
  }
  const configuringRow = rows.find((row) => row.id === configuring);
  const configuringDescriptor = configuring
    ? descriptorMap.get(configuring)
    : undefined;
  const configuringBinding = configuring
    ? instanceBinding(configuring)
    : undefined;
  const stepPlugins = (step: LifecycleStep) =>
    enabledRows.filter((row) => {
      if (step === 'command')
        return commands.enabled && commandsOf(row).length > 0;
      return hookStates(row).some((hook) => hook.active && hook.step === step);
    });
  const routeTarget = route
    ? agents.find((agent) => agent.uuid === route.target_uuid)
    : undefined;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PolicyScopeSelect
          value={effectiveScope}
          onChange={onScopeChange}
          bindings={bindings}
          agents={agents}
          isCustom={(binding) => hasPluginOverride(binding.policy)}
        />
        {route && (
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={routeCustom ? 'custom' : 'inherit'}
            onValueChange={setRouteMode}
            aria-label={t('bots.pluginHooks.routeMode')}
          >
            <ToggleGroupItem value="inherit" className="px-3">
              {t('bots.policy.inheritDefault')}
            </ToggleGroupItem>
            <ToggleGroupItem value="custom" className="px-3">
              {t('bots.policy.custom')}
            </ToggleGroupItem>
          </ToggleGroup>
        )}
      </div>

      {/* Lifecycle diagram */}
      <section
        aria-label={t('bots.pluginHooks.lifecycleTitle')}
        data-testid="plugin-lifecycle"
        className="rounded-xl border bg-card px-4 py-4"
      >
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold">
            {t('bots.pluginHooks.lifecycleTitle')}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t('bots.pluginHooks.lifecycleHint')}
          </p>
        </div>
        <ol className="flex min-w-0 items-start">
          {LIFECYCLE_STEPS.map((step, index) => {
            const Icon = STEP_ICONS[step];
            const items = stepPlugins(step);
            const caption =
              step === 'process'
                ? routeTarget
                  ? routeTarget.name
                  : [...processors]
                      .filter((p) => p !== 'command')
                      .map(processorName)
                      .join(' / ')
                : step === 'admission' || step === 'send'
                  ? t('bots.pluginHooks.policyCaption')
                  : '';
            return (
              <li
                key={step}
                data-step={step}
                className="flex min-w-0 flex-1 flex-col items-center"
              >
                <div className="flex w-full items-center">
                  <span
                    className={cn(
                      'h-px flex-1',
                      index === 0 ? 'bg-transparent' : 'bg-border',
                    )}
                  />
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full border bg-background text-muted-foreground">
                    <Icon className="size-4" strokeWidth={1.5} />
                  </span>
                  <span
                    className={cn(
                      'h-px flex-1',
                      index === LIFECYCLE_STEPS.length - 1
                        ? 'bg-transparent'
                        : 'bg-border',
                    )}
                  />
                </div>
                <span className="mt-1.5 px-0.5 text-center text-[11px] font-medium leading-tight sm:text-xs">
                  {t(`bots.pluginHooks.steps.${step}`)}
                </span>
                {caption && (
                  <span className="w-full truncate px-0.5 text-center text-[10px] text-muted-foreground">
                    {caption}
                  </span>
                )}
                <div className="mt-1.5 flex min-h-5 w-full flex-wrap justify-center gap-1">
                  {items.map((row) => (
                    <Tooltip key={row.id}>
                      <TooltipTrigger asChild>
                        <span
                          data-lifecycle-plugin={row.id}
                          className="size-5 overflow-hidden rounded ring-1 ring-border"
                        >
                          <AuthenticatedPluginIcon
                            author={row.author}
                            name={row.name}
                            alt={row.label}
                            className="size-5"
                          />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>{row.label}</TooltipContent>
                    </Tooltip>
                  ))}
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      {/* Plugin enablement */}
      <section
        aria-label={t('bots.pluginHooks.enableTitle')}
        className="flex flex-col gap-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold">
              {t('bots.pluginHooks.enableTitle')}
            </h3>
            <p className="text-xs text-muted-foreground">
              {route && !routeCustom
                ? t('bots.pluginHooks.inheritHint')
                : t('bots.pluginHooks.enableHint')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="bot-enable-all-plugins" className="text-sm">
              {t('pipelines.extensions.enableAllPlugins')}
            </Label>
            <Switch
              id="bot-enable-all-plugins"
              checked={selection.enable_all}
              disabled={!editable}
              onCheckedChange={(enableAll) =>
                writeSelection({ ...selection, enable_all: enableAll })
              }
            />
          </div>
        </div>

        <div
          data-testid="bot-command-settings"
          className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border bg-muted/30 px-3 py-2"
        >
          <TerminalSquare
            className="size-4 text-muted-foreground"
            strokeWidth={1.5}
          />
          <Label htmlFor="bot-commands-enabled" className="text-sm">
            {t('bots.pluginHooks.commands.label')}
          </Label>
          <Switch
            id="bot-commands-enabled"
            checked={commands.enabled}
            disabled={Boolean(route)}
            onCheckedChange={(enabled) => updateCommands({ enabled })}
          />
          <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            {t('bots.pluginCommands.prefixes')}
            <CommandPrefixPopover
              prefixes={prefixes}
              disabled={!commands.enabled || Boolean(route)}
              onChange={(next) => updateCommands({ prefixes: next })}
            />
          </span>
          <p className="basis-full text-xs text-muted-foreground">
            {route
              ? t('bots.pluginHooks.commands.botWide')
              : commands.enabled
                ? t('bots.pluginHooks.commands.hint')
                : t('bots.routingLayers.commandsDisabled')}
          </p>
        </div>

        {loadFailed ? (
          <p className="text-sm text-destructive">
            {t('bots.pluginHooks.loadFailed')}
          </p>
        ) : plugins === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <div className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
            {t('bots.pluginHooks.empty')}{' '}
            <Link
              to="/home/add-extension"
              className="text-primary hover:underline"
            >
              {t('bots.pluginHooks.browseMarket')}
              <ArrowRight className="ml-0.5 inline size-3.5" />
            </Link>
          </div>
        ) : (
          <ul className="flex flex-col gap-2" data-testid="bot-plugin-rows">
            {registrations === null && (
              <li className="text-xs text-muted-foreground">
                {t('bots.pluginHooks.registrationsUnknown')}
              </li>
            )}
            {rows.map((row) => {
              const enabled = selectionIncludes(selection, row.id);
              const hooks = hookStates(row);
              const rowCommands = commandsOf(row);
              const descriptor = descriptorMap.get(row.id);
              const binding = instanceBinding(row.id);
              return (
                <li
                  key={row.id}
                  data-plugin={row.id}
                  className={cn(
                    'flex items-start gap-3 rounded-lg border p-3',
                    enabled ? 'bg-card' : 'border-dashed bg-muted/30',
                  )}
                >
                  <span className="mt-0.5 size-8 shrink-0 overflow-hidden rounded">
                    <AuthenticatedPluginIcon
                      author={row.author}
                      name={row.name}
                      alt={row.label}
                      className="size-8"
                    />
                  </span>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {row.label}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {row.id}
                      </span>
                      {binding && (
                        <Badge
                          variant="outline"
                          className="text-[11px]"
                          data-testid="command-config-custom"
                        >
                          {binding.enabled === false
                            ? t('bots.pluginHooks.commandConfig.commandsOff')
                            : t('bots.pluginHooks.commandConfig.custom')}
                        </Badge>
                      )}
                      {!row.globallyEnabled && (
                        <Badge variant="outline" className="text-[11px]">
                          {t('bots.pluginHooks.globallyDisabled')}
                        </Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {rowCommands.map((command) => {
                        // A duplicate-name warning is moot while commands are off.
                        const owner = commands.enabled
                          ? overriddenBy.get(`${row.id}:${command}`)
                          : undefined;
                        const chip = (
                          <Badge
                            key={`cmd-${command}`}
                            variant="secondary"
                            data-command={command}
                            data-overridden={Boolean(owner)}
                            className={cn(
                              'gap-1 font-mono text-[11px]',
                              !enabled && 'text-muted-foreground',
                              // Commands switched off for the bot: every badge is crossed out.
                              !commands.enabled &&
                                'text-muted-foreground line-through decoration-muted-foreground/70',
                              owner &&
                                'bg-amber-50 text-amber-700 line-through dark:bg-amber-950/30 dark:text-amber-400',
                            )}
                          >
                            {owner && <AlertCircle className="size-3" />}
                            {commandPrefix}
                            {command}
                          </Badge>
                        );
                        return owner ? (
                          <Tooltip key={`cmd-${command}`}>
                            <TooltipTrigger asChild>{chip}</TooltipTrigger>
                            <TooltipContent>
                              {t('bots.pluginCommands.overriddenBy', {
                                plugin: owner,
                              })}
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          chip
                        );
                      })}
                      {hooks.map((hook) => (
                        <Tooltip key={`hook-${hook.event}`}>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="outline"
                              data-hook={hook.event}
                              data-active={hook.active}
                              className={cn(
                                'gap-1 text-[11px]',
                                !hook.active &&
                                  'text-muted-foreground line-through decoration-muted-foreground/60',
                              )}
                            >
                              {hook.step === null ? (
                                <Eye className="size-3" aria-hidden="true" />
                              ) : (
                                <EventListenerIcon
                                  className="size-3"
                                  aria-hidden="true"
                                />
                              )}
                              {t(`bots.pluginHooks.events.${hook.event}`, {
                                defaultValue: hook.event,
                              })}
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent className="max-w-xs">
                            <span className="font-mono">{hook.event}</span>
                            {hook.reason && <> · {hook.reason}</>}
                          </TooltipContent>
                        </Tooltip>
                      ))}
                      {registrations === null &&
                        row.hasListeners &&
                        hooks.length === 0 && (
                          <Badge
                            variant="outline"
                            className="text-[11px] text-muted-foreground"
                          >
                            {t('bots.pluginHooks.hooksUnknown')}
                          </Badge>
                        )}
                    </div>
                    {hooks
                      .filter((hook) => !hook.active && hook.reason)
                      .map((hook) => (
                        <p
                          key={`reason-${hook.event}`}
                          className="text-xs text-muted-foreground"
                        >
                          {hook.reason}
                        </p>
                      ))}
                  </div>
                  {commands.enabled &&
                    !route &&
                    hasCommandSettings(descriptor) && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-8 shrink-0 gap-1 px-2 text-xs"
                        onClick={() => setConfiguring(row.id)}
                        data-testid="command-config-button"
                      >
                        <Settings2 className="size-3.5" />
                        {t('bots.pluginHooks.commandConfig.button')}
                      </Button>
                    )}
                  <Switch
                    checked={enabled}
                    disabled={!editable || selection.enable_all}
                    onCheckedChange={(next) =>
                      writeSelection(toggleSelection(selection, row.id, next))
                    }
                    aria-label={t('bots.pluginHooks.enablePlugin', {
                      plugin: row.label,
                    })}
                  />
                </li>
              );
            })}
          </ul>
        )}
        {registrationCapability && commands.enabled && (
          <PlatformCommandRegistration
            value={commands}
            onChange={onCommandSettingsChange}
            capability={registrationCapability}
            botId={botId}
            dirty={dirty}
            names={[...commandOwners.keys()]}
          />
        )}
      </section>

      {configuringRow && configuringDescriptor && (
        <CommandConfigDialog
          open
          onOpenChange={(open) => !open && setConfiguring(null)}
          descriptor={configuringDescriptor}
          pluginLabel={configuringRow.label}
          instance={
            configuringBinding
              ? commandInstances.get(configuringBinding.processor_uuid)
              : undefined
          }
          prefix={commandPrefix}
          onBind={(agent) => bindInstance(configuringRow.id, agent)}
          onUnbind={() => unbindInstance(configuringRow.id)}
        />
      )}

      {children}
    </div>
  );
}
