import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, Search } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentPlatformTool, PluginTool } from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

interface AgentApiToolPickerProps {
  platformTools: AgentPlatformTool[];
  platformValue: string[];
  onPlatformChange: (value: string[]) => void;
  hostTools: PluginTool[];
  hostValue: string[];
  onHostChange: (value: string[]) => void;
  platformCatalogAvailable?: boolean;
  hostCatalogAvailable?: boolean;
  scopes?: readonly ToolScope[];
}

type ToolScope = 'event' | 'platform' | 'builtin' | 'mcp' | 'plugin' | 'skill';

type ToolEntry = {
  key: string;
  kind: 'platform' | 'host';
  name: string;
  scope: ToolScope;
  group: string;
  label: string;
  description: string;
  parameters: Record<string, unknown>;
  api?: string;
  eventPatterns?: string[];
  risk?: AgentPlatformTool['risk'];
};

const PLATFORM_CATEGORY_LABELS: Record<string, { zh: string; en: string }> = {
  message: { zh: '消息', en: 'Messages' },
  identity: { zh: '用户与身份', en: 'Users & identity' },
  group: { zh: '群组', en: 'Groups' },
  moderation: { zh: '群管理', en: 'Moderation' },
  request: { zh: '请求处理', en: 'Requests' },
};

const SCOPE_ORDER: ToolScope[] = [
  'event',
  'platform',
  'builtin',
  'mcp',
  'plugin',
  'skill',
];

function normalizeHostScope(tool: PluginTool): ToolScope {
  if (tool.source === 'mcp' || tool.source === 'plugin') return tool.source;
  if (tool.source === 'skill') return 'skill';
  return 'builtin';
}

export default function AgentApiToolPicker({
  platformTools,
  platformValue,
  onPlatformChange,
  hostTools,
  hostValue,
  onHostChange,
  platformCatalogAvailable = true,
  hostCatalogAvailable = true,
  scopes = SCOPE_ORDER,
}: AgentApiToolPickerProps) {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState('');
  const [activeScope, setActiveScope] = useState<ToolScope>(
    scopes[0] ?? 'event',
  );
  const [expandedTool, setExpandedTool] = useState<string | null>(null);
  const isChinese = i18n.language.startsWith('zh');
  const selectedPlatform = useMemo(
    () => new Set(platformValue),
    [platformValue],
  );
  const selectedHost = useMemo(() => new Set(hostValue), [hostValue]);

  const entries = useMemo<ToolEntry[]>(
    () => [
      ...platformTools.map((tool) => ({
        key: `platform:${tool.name}`,
        kind: 'platform' as const,
        name: tool.name,
        scope: tool.scope,
        group: tool.category,
        label: extractI18nObject(tool.label),
        description: extractI18nObject(tool.description),
        parameters: tool.parameters,
        api: tool.api,
        eventPatterns: tool.event_patterns,
        risk: tool.risk,
      })),
      ...hostTools.map((tool) => ({
        key: `host:${tool.source || 'builtin'}:${tool.source_id || ''}:${tool.name}`,
        kind: 'host' as const,
        name: tool.name,
        scope: normalizeHostScope(tool),
        group: tool.source_name || t('agents.langbotBuiltIn'),
        label: tool.name,
        description: tool.human_desc || tool.description || tool.name,
        parameters: tool.parameters as Record<string, unknown>,
      })),
    ],
    [hostTools, platformTools, t],
  );

  const scopeCounts = useMemo(
    () =>
      Object.fromEntries(
        SCOPE_ORDER.map((scope) => [
          scope,
          entries.filter((tool) => tool.scope === scope).length,
        ]),
      ) as Record<ToolScope, number>,
    [entries],
  );
  const visibleScopes = SCOPE_ORDER.filter(
    (scope) =>
      scopes.includes(scope) && (scope !== 'skill' || scopeCounts.skill > 0),
  );
  useEffect(() => {
    if (!visibleScopes.includes(activeScope) && visibleScopes[0]) {
      setActiveScope(visibleScopes[0]);
      setExpandedTool(null);
    }
  }, [activeScope, visibleScopes]);

  const filteredEntries = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    return entries.filter(
      (tool) =>
        tool.scope === activeScope &&
        (!needle ||
          [tool.name, tool.label, tool.description, tool.api, tool.group]
            .join(' ')
            .toLocaleLowerCase()
            .includes(needle)),
    );
  }, [activeScope, entries, query]);
  const groupedEntries = useMemo(() => {
    const groups = new Map<string, ToolEntry[]>();
    for (const tool of filteredEntries) {
      if (!groups.has(tool.group)) groups.set(tool.group, []);
      groups.get(tool.group)!.push(tool);
    }
    return Array.from(groups.entries());
  }, [filteredEntries]);
  const selectedCount = entries.filter(
    (tool) =>
      scopes.includes(tool.scope) &&
      (tool.kind === 'platform'
        ? selectedPlatform.has(tool.name)
        : selectedHost.has(tool.name)),
  ).length;

  const scopeLabel = (scope: ToolScope) => {
    const keys: Record<ToolScope, string> = {
      event: 'agents.eventApiTools',
      platform: 'agents.platformApiTools',
      builtin: 'agents.sandboxTools',
      mcp: 'agents.mcpTools',
      plugin: 'agents.pluginTools',
      skill: 'agents.skillTools',
    };
    return t(keys[scope]);
  };

  const groupLabel = (group: string) => {
    if (activeScope === 'event' || activeScope === 'platform') {
      return isChinese
        ? PLATFORM_CATEGORY_LABELS[group]?.zh || group
        : PLATFORM_CATEGORY_LABELS[group]?.en || group;
    }
    return group;
  };

  const setTool = (tool: ToolEntry, checked: boolean) => {
    if (tool.kind === 'platform') {
      const next = new Set(platformValue);
      if (checked) next.add(tool.name);
      else next.delete(tool.name);
      onPlatformChange(
        platformTools
          .filter((item) => next.has(item.name))
          .map((item) => item.name),
      );
      return;
    }
    const next = new Set(hostValue);
    if (checked) next.add(tool.name);
    else next.delete(tool.name);
    onHostChange(
      hostTools.filter((item) => next.has(item.name)).map((item) => item.name),
    );
  };

  const catalogAvailable =
    activeScope === 'event' || activeScope === 'platform'
      ? platformCatalogAvailable
      : hostCatalogAvailable;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        {visibleScopes.length === 1 ? (
          <span className="pt-2 text-sm font-medium">
            {scopeLabel(visibleScopes[0])}
            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
              {scopeCounts[visibleScopes[0]]}
            </span>
          </span>
        ) : (
          <div className="inline-flex max-w-full flex-wrap gap-1 rounded-lg bg-muted p-1">
            {visibleScopes.map((scope) => (
              <button
                key={scope}
                type="button"
                aria-pressed={activeScope === scope}
                onClick={() => {
                  setActiveScope(scope);
                  setExpandedTool(null);
                }}
                className={cn(
                  'rounded-md px-2.5 py-1.5 text-sm transition-colors active:scale-[0.98]',
                  activeScope === scope
                    ? 'bg-background font-medium shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {scopeLabel(scope)}
                <span className="ml-1.5 text-xs text-muted-foreground">
                  {scopeCounts[scope]}
                </span>
              </button>
            ))}
          </div>
        )}
        <span className="shrink-0 pt-2 text-xs text-muted-foreground">
          {t('agents.apiToolsSelected', {
            count: selectedCount,
          })}
        </span>
      </div>

      <div className="relative max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('agents.apiToolsSearch')}
          className="pl-9"
        />
      </div>

      {!catalogAvailable && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          {activeScope === 'event' || activeScope === 'platform'
            ? t('agents.apiToolsCatalogUnavailable')
            : t('agents.hostToolsCatalogUnavailable')}
        </div>
      )}
      {catalogAvailable && !filteredEntries.length && (
        <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
          {t('agents.apiToolsNoResults')}
        </div>
      )}
      {catalogAvailable && filteredEntries.length > 0 && (
        <div className="overflow-hidden rounded-lg border bg-background">
          {groupedEntries.map(([group, groupTools], groupIndex) => (
            <section key={group} className={cn(groupIndex > 0 && 'border-t')}>
              <div className="bg-muted/30 px-3 py-1.5 text-xs font-medium text-muted-foreground">
                {groupLabel(group)}
              </div>
              <div className="divide-y">
                {groupTools.map((tool) => {
                  const checked =
                    tool.kind === 'platform'
                      ? selectedPlatform.has(tool.name)
                      : selectedHost.has(tool.name);
                  const expanded = expandedTool === tool.key;
                  const parameterNames = Object.keys(
                    (tool.parameters.properties as
                      | Record<string, unknown>
                      | undefined) ?? {},
                  );
                  return (
                    <div key={tool.key} className="bg-background px-3 py-2.5">
                      <label
                        className={cn(
                          'grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2.5',
                          'cursor-pointer',
                        )}
                      >
                        <Checkbox
                          checked={checked}
                          onCheckedChange={(next) =>
                            setTool(tool, next === true)
                          }
                          aria-label={tool.label}
                          className="mt-0.5"
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-medium leading-5">
                            {tool.label}
                          </span>
                          <span className="block truncate text-xs leading-5 text-muted-foreground">
                            {tool.description}
                          </span>
                        </span>
                        <span
                          className={cn(
                            'min-w-12 pt-0.5 text-right text-xs text-muted-foreground',
                            tool.risk === 'dangerous' &&
                              'text-amber-700 dark:text-amber-400',
                          )}
                        >
                          {tool.risk
                            ? t(`agents.apiToolRisk.${tool.risk}`)
                            : scopeLabel(tool.scope)}
                        </span>
                      </label>
                      <button
                        type="button"
                        aria-expanded={expanded}
                        onClick={() =>
                          setExpandedTool(expanded ? null : tool.key)
                        }
                        className="ml-7 mt-0.5 inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs text-muted-foreground hover:text-foreground active:scale-[0.98]"
                      >
                        {expanded
                          ? t('agents.apiToolHideDetails')
                          : t('agents.apiToolDetails')}
                        <ChevronDown
                          className={cn(
                            'size-3 transition-transform',
                            expanded && 'rotate-180',
                          )}
                        />
                      </button>
                      {expanded && (
                        <div className="ml-8 mt-1.5 space-y-1 border-l pl-3 text-xs text-muted-foreground">
                          <div className="font-mono text-foreground/75">
                            {tool.name}
                          </div>
                          {tool.api && <div>API: {tool.api}</div>}
                          {tool.kind === 'host' && (
                            <div>
                              {t('agents.apiToolSource')}:{' '}
                              {groupLabel(tool.group)}
                            </div>
                          )}
                          {tool.eventPatterns && (
                            <div>
                              {t('agents.apiToolEvents')}:{' '}
                              {tool.eventPatterns.join(', ')}
                            </div>
                          )}
                          <div>
                            {t('agents.apiToolParameters')}:{' '}
                            {parameterNames.length
                              ? parameterNames.join(', ')
                              : t('agents.apiToolNoParameters')}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
