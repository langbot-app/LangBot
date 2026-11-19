import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { ArrowUpToLine, Info, LogIn, Send, ShieldCheck } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  Agent,
  EventBinding,
  MessagePolicy,
  MessagePolicyMetadata,
  MessagePolicyOverride,
  MessagePolicySectionName,
} from '@/app/infra/entities/api';
import type { PipelineConfigStage } from '@/app/infra/entities/pipeline';
import { extractI18nObject } from '@/i18n/I18nProvider';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';
import PolicyScopeSelect, { BOT_SCOPE } from './PolicyScopeSelect';
import {
  POLICY_SECTIONS,
  admitsEverything,
  hasPluginOverride,
  hasSectionOverride,
  isMessageRoute,
  mergePolicy,
  resolveRoutePolicy,
  routeKey,
  routeLabel,
  stableJson,
} from './message-policy';

const SECTION_ICONS = {
  trigger: LogIn,
  safety: ShieldCheck,
  output: Send,
} as const;

/** Adapters whose native streaming cannot carry @ / quote on the first frame. */
const STREAM_REPLY_LIMITS = new Set(['discord', 'lark']);

function sectionsOf(policy: MessagePolicy): Omit<MessagePolicy, 'plugins'> {
  const result: Omit<MessagePolicy, 'plugins'> = {};
  for (const section of POLICY_SECTIONS) {
    if (policy[section]) result[section] = structuredClone(policy[section]);
  }
  return result;
}

function withoutSections(
  policy: MessagePolicyOverride | null | undefined,
): MessagePolicyOverride | null {
  if (!policy) return null;
  const rest: MessagePolicyOverride = {};
  if ('plugins' in policy) rest.plugins = policy.plugins;
  return hasPluginOverride(rest) ? rest : null;
}

export default function BotMessagePolicyPanel({
  botPolicy,
  onBotPolicyChange,
  bindings,
  onBindingsChange,
  agents,
  scope,
  onScopeChange,
  adapter,
}: {
  botPolicy: MessagePolicy | undefined;
  onBotPolicyChange: (policy: MessagePolicy) => void;
  bindings: EventBinding[];
  onBindingsChange: (bindings: EventBinding[]) => void;
  agents: Agent[];
  scope: string;
  onScopeChange: (scope: string) => void;
  adapter: string;
}) {
  const { t } = useTranslation();
  const [metadata, setMetadata] = useState<MessagePolicyMetadata | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  // Remount the dynamic forms when values change from outside them.
  const [formVersion, setFormVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    httpClient
      .getMessagePolicyMetadata()
      .then((data) => {
        if (!cancelled) setMetadata(data);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const routeIndex = bindings.findIndex(
    (binding, index) =>
      isMessageRoute(binding) && routeKey(binding, index) === scope,
  );
  const route = routeIndex >= 0 ? bindings[routeIndex] : undefined;
  const effectiveScope = route ? scope : BOT_SCOPE;
  const routeCustom = route ? hasSectionOverride(route.policy) : false;
  const baseBot = mergePolicy(metadata?.neutral ?? {}, botPolicy ?? {});
  const shown: MessagePolicy = route
    ? resolveRoutePolicy(baseBot, route.policy)
    : baseBot;
  const editable = !route || routeCustom;
  const messageRoutes = bindings
    .map((binding, index) => ({ binding, index }))
    .filter(({ binding }) => isMessageRoute(binding));

  function setRoutePolicy(policy: MessagePolicyOverride | null) {
    const next = [...bindings];
    next[routeIndex] = { ...route!, policy };
    onBindingsChange(next);
  }

  function writeStage(
    section: MessagePolicySectionName,
    stage: string,
    values: Record<string, unknown>,
  ) {
    if (!editable) return;
    if (stableJson(shown[section]?.[stage]) === stableJson(values)) return;
    if (!route) {
      onBotPolicyChange({
        ...(botPolicy ?? {}),
        [section]: { ...(baseBot[section] ?? {}), [stage]: values },
      });
      return;
    }
    const override = route.policy ?? {};
    setRoutePolicy({
      ...override,
      [section]: { ...(shown[section] ?? {}), [stage]: values },
    });
  }

  function setRouteMode(mode: string) {
    if (!route || !mode) return;
    if (mode === 'custom') {
      setRoutePolicy({ ...(route.policy ?? {}), ...sectionsOf(baseBot) });
    } else {
      setRoutePolicy(withoutSections(route.policy));
    }
    setFormVersion((v) => v + 1);
  }

  function promoteToDefault() {
    if (!route) return;
    const nextBot: MessagePolicy = {
      ...(botPolicy ?? {}),
      ...sectionsOf(resolveRoutePolicy(baseBot, route.policy)),
    };
    const resolvedDefault = stableJson(
      sectionsOf(mergePolicy(baseBot, nextBot)),
    );
    let cleared = 0;
    const next = bindings.map((binding) => {
      if (!isMessageRoute(binding) || !hasSectionOverride(binding.policy))
        return binding;
      const resolved = sectionsOf(
        resolveRoutePolicy(mergePolicy(baseBot, nextBot), binding.policy),
      );
      if (stableJson(resolved) !== resolvedDefault) return binding;
      cleared += 1;
      return { ...binding, policy: withoutSections(binding.policy) };
    });
    onBotPolicyChange(nextBot);
    onBindingsChange(next);
    setFormVersion((v) => v + 1);
    toast.success(t('bots.policy.promoted', { count: cleared }));
  }

  if (loadFailed)
    return (
      <p className="text-sm text-destructive">{t('bots.policy.loadFailed')}</p>
    );
  if (!metadata)
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    );

  const neutralDefault = admitsEverything(botPolicy, metadata.neutral);

  function renderStage(
    section: MessagePolicySectionName,
    stage: PipelineConfigStage,
  ) {
    return (
      <div
        key={`${effectiveScope}-${section}-${stage.name}-${formVersion}`}
        className="rounded-lg border p-4"
      >
        <div className="mb-3">
          <h4 className="text-sm font-medium">
            {extractI18nObject(stage.label)}
          </h4>
          {stage.description && (
            <p className="text-xs text-muted-foreground">
              {extractI18nObject(stage.description)}
            </p>
          )}
        </div>
        <DynamicFormComponent
          itemConfigList={stage.config}
          initialValues={
            (shown[section]?.[stage.name] as Record<string, unknown>) ?? {}
          }
          onSubmit={(values) =>
            writeStage(section, stage.name, values as Record<string, unknown>)
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5" data-testid="bot-message-policy">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PolicyScopeSelect
          value={effectiveScope}
          onChange={onScopeChange}
          bindings={bindings}
          agents={agents}
          isCustom={(binding) => hasSectionOverride(binding.policy)}
        />
        {route && (
          <div className="flex flex-wrap items-center gap-2">
            <ToggleGroup
              type="single"
              variant="outline"
              size="sm"
              value={routeCustom ? 'custom' : 'inherit'}
              onValueChange={setRouteMode}
              aria-label={t('bots.policy.routeMode')}
            >
              <ToggleGroupItem value="inherit" className="px-3">
                {t('bots.policy.inheritDefault')}
              </ToggleGroupItem>
              <ToggleGroupItem value="custom" className="px-3">
                {t('bots.policy.custom')}
              </ToggleGroupItem>
            </ToggleGroup>
            {routeCustom && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={promoteToDefault}
              >
                <ArrowUpToLine className="size-4" />
                {t('bots.policy.promote')}
              </Button>
            )}
          </div>
        )}
      </div>

      {!route && (
        <>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t('bots.policy.botDefaultHint')}
            {neutralDefault && ` ${t('bots.policy.neutralDefaultHint')}`}
          </p>
          {messageRoutes.length > 0 && (
            <ul
              className="divide-y rounded-lg border"
              aria-label={t('bots.policy.routes')}
            >
              {messageRoutes.map(({ binding, index }) => (
                <li
                  key={routeKey(binding, index)}
                  className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm"
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 truncate text-left hover:underline"
                    onClick={() => onScopeChange(routeKey(binding, index))}
                  >
                    {routeLabel(binding, index, agents)}
                  </button>
                  <Badge
                    variant={
                      hasSectionOverride(binding.policy) ? 'default' : 'outline'
                    }
                    className="text-[11px]"
                  >
                    {t('bots.policy.policyState', {
                      state: hasSectionOverride(binding.policy)
                        ? t('bots.policy.custom')
                        : t('bots.policy.inheritDefault'),
                    })}
                  </Badge>
                  <Badge
                    variant={
                      hasPluginOverride(binding.policy) ? 'default' : 'outline'
                    }
                    className="text-[11px]"
                  >
                    {t('bots.policy.pluginState', {
                      state: hasPluginOverride(binding.policy)
                        ? t('bots.policy.custom')
                        : t('bots.policy.inheritDefault'),
                    })}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      {route && !routeCustom && (
        <Alert>
          <Info className="size-4" />
          <AlertDescription>{t('bots.policy.inheritHint')}</AlertDescription>
        </Alert>
      )}

      <fieldset
        disabled={!editable}
        className={cn('flex flex-col gap-6', !editable && 'opacity-70')}
      >
        {metadata.configs.map((config) => {
          const section = config.name as MessagePolicySectionName;
          const Icon = SECTION_ICONS[section] ?? Info;
          return (
            <section
              key={section}
              aria-label={extractI18nObject(config.label)}
              data-policy-section={section}
              className="flex flex-col gap-3"
            >
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <Icon className="size-4 text-muted-foreground" />
                {extractI18nObject(config.label)}
              </h3>
              {section === 'output' && (
                <p className="text-xs text-muted-foreground">
                  {t('bots.policy.streamingNote')}
                  {STREAM_REPLY_LIMITS.has(adapter) &&
                    ` ${t('bots.policy.streamingPlatformLimit')}`}
                </p>
              )}
              {config.stages.map((stage) => renderStage(section, stage))}
            </section>
          );
        })}
      </fieldset>
    </div>
  );
}
