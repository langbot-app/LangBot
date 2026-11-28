import type { PluginTool } from '@/app/infra/entities/api';

export type ToolSource = NonNullable<PluginTool['source']>;

export type ToolProviderGroup = {
  key: string;
  name: string;
  tools: PluginTool[];
};

type ToolSourceGroup = {
  key: ToolSource | string;
  label: string;
  groups: ToolProviderGroup[];
  total: number;
};

const BUILTIN_TOOL_NAMES = new Set([
  'exec',
  'read',
  'write',
  'edit',
  'glob',
  'grep',
]);
const TOOL_SOURCE_ORDER = ['plugin', 'mcp', 'skill', 'builtin'];

export function normalizeToolSource(tool: PluginTool): ToolSource | string {
  if (tool.source) {
    return tool.source;
  }
  if (BUILTIN_TOOL_NAMES.has(tool.name)) {
    return 'builtin';
  }
  if (tool.name.startsWith('langbot_mcp_')) {
    return 'mcp';
  }
  return 'plugin';
}

export function buildToolSourceGroups(
  tools: PluginTool[],
  sourceLabels: Record<string, string>,
) {
  const sourceGroups = new Map<string, Map<string, ToolProviderGroup>>();

  for (const tool of tools) {
    const source = normalizeToolSource(tool);
    const providerName =
      tool.source_name ||
      (source === 'builtin' ? 'LangBot' : sourceLabels[source] || source);
    const providerKey = `${source}:${tool.source_id || providerName}`;

    if (!sourceGroups.has(source)) {
      sourceGroups.set(source, new Map());
    }

    const providerGroups = sourceGroups.get(source)!;
    if (!providerGroups.has(providerKey)) {
      providerGroups.set(providerKey, {
        key: providerKey,
        name: providerName,
        tools: [],
      });
    }
    providerGroups.get(providerKey)!.tools.push(tool);
  }

  return Array.from(sourceGroups.entries())
    .sort(([left], [right]) => {
      const leftIndex = TOOL_SOURCE_ORDER.indexOf(left);
      const rightIndex = TOOL_SOURCE_ORDER.indexOf(right);
      return (
        (leftIndex === -1 ? TOOL_SOURCE_ORDER.length : leftIndex) -
        (rightIndex === -1 ? TOOL_SOURCE_ORDER.length : rightIndex)
      );
    })
    .map(([source, providerGroups]): ToolSourceGroup => ({
      key: source,
      label: sourceLabels[source] || source,
      groups: Array.from(providerGroups.values()).sort((left, right) =>
        left.name.localeCompare(right.name),
      ),
      total: Array.from(providerGroups.values()).reduce(
        (count, group) => count + group.tools.length,
        0,
      ),
    }));
}
