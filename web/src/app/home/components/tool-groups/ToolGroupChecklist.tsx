import { useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Search } from 'lucide-react';
import type { PluginTool } from '@/app/infra/entities/api';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import SelectableGroupCard from './SelectableGroupCard';
import { buildToolSourceGroups } from './toolGroups';

export interface ToolGroupChecklistProps {
  tools: PluginTool[];
  value: string[];
  onChange: (value: string[]) => void;
  /** Optional header decoration per tool source (plugin / mcp / skill / builtin). */
  renderSourceExtra?: (source: string) => ReactNode;
  emptyText?: string;
}

/**
 * Searchable tool checklist grouped by provider, using the same collapsible
 * group cards as the Workspace operations picker.
 */
export default function ToolGroupChecklist({
  tools,
  value,
  onChange,
  renderSourceExtra,
  emptyText,
}: ToolGroupChecklistProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const selected = useMemo(() => new Set(value), [value]);

  const sourceLabels = useMemo<Record<string, string>>(
    () => ({
      builtin: t('pipelines.runner.builtinTools'),
      plugin: t('pipelines.runner.pluginTools'),
      mcp: t('pipelines.runner.mcpTools'),
      skill: t('pipelines.runner.skillTools'),
    }),
    [t],
  );

  const filteredTools = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return tools;
    return tools.filter((tool) =>
      [tool.name, tool.human_desc, tool.description, tool.source_name]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase()
        .includes(needle),
    );
  }, [query, tools]);

  const providerGroups = useMemo(
    () =>
      buildToolSourceGroups(filteredTools, sourceLabels).flatMap(
        (sourceGroup) =>
          sourceGroup.groups.map((group) => ({
            ...group,
            source: String(sourceGroup.key),
            sourceLabel: sourceGroup.label,
          })),
      ),
    [filteredTools, sourceLabels],
  );

  const toggleTool = (name: string, checked: boolean) => {
    if (checked) {
      if (!selected.has(name)) onChange([...value, name]);
    } else {
      onChange(value.filter((item) => item !== name));
    }
  };

  const toggleGroup = (groupTools: PluginTool[], checked: boolean) => {
    const names = new Set(groupTools.map((tool) => tool.name));
    if (checked) {
      const next = [...value];
      for (const name of names) if (!selected.has(name)) next.push(name);
      onChange(next);
    } else {
      onChange(value.filter((item) => !names.has(item)));
    }
  };

  const searching = query.trim().length > 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-sm flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t('agents.apiToolsSearch')}
            className="pl-9"
          />
        </div>
        <span className="shrink-0 text-xs text-muted-foreground">
          {t('agents.apiToolsSelected', {
            count: tools.filter((tool) => selected.has(tool.name)).length,
          })}
        </span>
      </div>

      {tools.length === 0 ? (
        <div className="flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-border">
          <p className="text-sm text-muted-foreground">
            {emptyText ?? t('pipelines.runner.noToolsSelected')}
          </p>
        </div>
      ) : providerGroups.length === 0 ? (
        <div className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
          {t('agents.apiToolsNoResults')}
        </div>
      ) : (
        <div className="space-y-3">
          {providerGroups.map((group) => {
            const selectedInGroup = group.tools.filter((tool) =>
              selected.has(tool.name),
            ).length;
            return (
              <SelectableGroupCard
                key={group.key}
                title={group.name}
                subtitle={
                  group.name !== group.sourceLabel
                    ? group.sourceLabel
                    : undefined
                }
                extra={renderSourceExtra?.(group.source)}
                selectedCount={selectedInGroup}
                total={group.tools.length}
                forceOpen={searching}
                selectAllLabel={t('agents.apiToolsSelectAll')}
                onToggleAll={(checked) => toggleGroup(group.tools, checked)}
              >
                {group.tools.map((tool) => {
                  const checked = selected.has(tool.name);
                  const id = `tool-${group.key}-${tool.name}`;
                  return (
                    <div
                      key={tool.name}
                      className="flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-muted/30"
                    >
                      <Checkbox
                        id={id}
                        checked={checked}
                        onCheckedChange={(next) =>
                          toggleTool(tool.name, next === true)
                        }
                        aria-label={`Select ${tool.name}`}
                        className="mt-1"
                      />
                      <label
                        htmlFor={id}
                        className="min-w-0 flex-1 cursor-pointer"
                      >
                        <span className="block truncate text-sm font-medium leading-5">
                          {tool.name}
                        </span>
                        {tool.human_desc && (
                          <span className="mt-0.5 block text-xs leading-normal text-muted-foreground">
                            {tool.human_desc}
                          </span>
                        )}
                      </label>
                    </div>
                  );
                })}
              </SelectableGroupCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
