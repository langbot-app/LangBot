import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import {
  KnowledgeBase,
  MCPResource,
  MCPServer,
  PluginTool,
} from '@/app/infra/entities/api';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  CircleHelp,
  Database,
  FileText,
  Plus,
  Server,
  Wrench,
  X,
} from 'lucide-react';

type ToolSource = NonNullable<PluginTool['source']>;

type BoundMCPResource = {
  server_uuid?: string;
  server_name?: string;
  uri: string;
  mode?: string;
  enabled?: boolean;
  max_bytes?: number;
  max_tokens?: number;
};

type PipelineExtensions = Awaited<
  ReturnType<typeof backendClient.getPipelineExtensions>
>;
type AvailablePlugin = PipelineExtensions['available_plugins'][number];

type ToolProviderGroup = {
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

type MCPToolOwner = {
  serverId?: string;
  serverName: string;
};

type PluginToolOwner = {
  pluginId: string;
};

type BoundPlugin = PipelineExtensions['bound_plugins'][number];

const BUILTIN_TOOL_NAMES = new Set([
  'exec',
  'read',
  'write',
  'edit',
  'glob',
  'grep',
]);
const TOOL_SOURCE_ORDER = ['plugin', 'mcp', 'skill', 'builtin'];

function getMCPResourceKey(server: MCPServer, uri: string) {
  return `${server.uuid || server.name}:${uri}`;
}

function isSameMCPResource(
  resource: BoundMCPResource,
  server: MCPServer,
  uri: string,
) {
  return (
    (resource.server_uuid === server.uuid ||
      (!resource.server_uuid && resource.server_name === server.name)) &&
    resource.uri === uri
  );
}

function getBoundPluginId(plugin: BoundPlugin) {
  return `${plugin.author || ''}/${plugin.name}`;
}

function InfoTooltip({ label }: { label: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
          aria-label={label}
        >
          <CircleHelp className="size-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[280px]">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

function normalizeToolSource(tool: PluginTool): ToolSource | string {
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

function hasReliableSourceMetadata(tool: PluginTool) {
  if (!tool.source) {
    return false;
  }
  if (tool.source === 'plugin' || tool.source === 'mcp') {
    return Boolean(tool.source_id || tool.source_name);
  }
  return true;
}

function buildToolSourceGroups(
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
    .map(
      ([source, providerGroups]): ToolSourceGroup => ({
        key: source,
        label: sourceLabels[source] || source,
        groups: Array.from(providerGroups.values()).sort((left, right) =>
          left.name.localeCompare(right.name),
        ),
        total: Array.from(providerGroups.values()).reduce(
          (count, group) => count + group.tools.length,
          0,
        ),
      }),
    );
}

function buildMCPToolOwners(servers: MCPServer[]) {
  const owners = new Map<string, MCPToolOwner>();
  const ambiguousNames = new Set<string>();

  for (const server of servers) {
    for (const tool of server.runtime_info?.tools || []) {
      if (!tool.name) {
        continue;
      }
      const owner = {
        serverId: server.uuid,
        serverName: server.name,
      };

      if (owners.has(tool.name)) {
        ambiguousNames.add(tool.name);
        continue;
      }
      owners.set(tool.name, owner);
    }
  }

  for (const name of ambiguousNames) {
    owners.delete(name);
  }

  return owners;
}

function buildPluginToolOwners(plugins: AvailablePlugin[]) {
  const owners = new Map<string, PluginToolOwner>();
  const ambiguousNames = new Set<string>();

  for (const plugin of plugins) {
    const metadata = plugin.manifest?.manifest?.metadata;
    const pluginName = metadata?.name;
    if (!pluginName) {
      continue;
    }

    const pluginId = metadata.author
      ? `${metadata.author}/${pluginName}`
      : pluginName;

    for (const component of plugin.components || []) {
      const manifest = component.manifest?.manifest;
      if (manifest?.kind !== 'Tool') {
        continue;
      }

      const toolName = manifest.metadata?.name;
      if (!toolName) {
        continue;
      }

      if (owners.has(toolName)) {
        ambiguousNames.add(toolName);
        continue;
      }
      owners.set(toolName, { pluginId });
    }
  }

  for (const name of ambiguousNames) {
    owners.delete(name);
  }

  return owners;
}

function annotateMCPToolSource(
  tool: PluginTool,
  owner?: MCPToolOwner,
): PluginTool {
  if (!owner || hasReliableSourceMetadata(tool)) {
    return tool;
  }
  return {
    ...tool,
    source: 'mcp',
    source_name: owner.serverName,
    source_id: owner.serverId,
  };
}

function annotatePluginToolSource(
  tool: PluginTool,
  owner?: PluginToolOwner,
): PluginTool {
  if (!owner || hasReliableSourceMetadata(tool)) {
    return tool;
  }
  return {
    ...tool,
    source: 'plugin',
    source_name: owner.pluginId,
    source_id: owner.pluginId,
  };
}

function annotateToolSource(
  tool: PluginTool,
  pluginOwner?: PluginToolOwner,
  mcpOwner?: MCPToolOwner,
): PluginTool {
  if (hasReliableSourceMetadata(tool)) {
    return tool;
  }

  if (tool.source === 'plugin') {
    return annotatePluginToolSource(tool, pluginOwner);
  }
  if (tool.source === 'mcp') {
    return annotateMCPToolSource(tool, mcpOwner);
  }
  if (mcpOwner && !pluginOwner) {
    return annotateMCPToolSource(tool, mcpOwner);
  }
  if (pluginOwner && !mcpOwner) {
    return annotatePluginToolSource(tool, pluginOwner);
  }

  return tool;
}

export default function ToolResourceSelectors({
  pipelineId,
  value,
  onChange,
  mode = 'all',
}: {
  pipelineId?: string;
  value: Record<string, any>;
  onChange: (patch: Record<string, any>) => void;
  mode?: 'tools' | 'resources' | 'all';
}) {
  const { t } = useTranslation();
  const [tools, setTools] = useState<PluginTool[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [extensions, setExtensions] = useState<PipelineExtensions | null>(null);
  const [toolsDialogOpen, setToolsDialogOpen] = useState(false);
  const [kbDialogOpen, setKbDialogOpen] = useState(false);
  const [tempSelectedToolNames, setTempSelectedToolNames] = useState<string[]>(
    [],
  );
  const [tempSelectedKBIds, setTempSelectedKBIds] = useState<string[]>([]);

  useEffect(() => {
    if (mode !== 'resources') {
      backendClient.getTools(pipelineId).then((resp) => setTools(resp.tools));
    }
    if (mode !== 'tools') {
      backendClient
        .getKnowledgeBases()
        .then((resp) => setKnowledgeBases(resp.bases));
    }
    if (pipelineId) {
      backendClient
        .getPipelineExtensions(pipelineId)
        .then((resp) => setExtensions(resp));
    }
  }, [mode, pipelineId]);

  const enableAllTools = value['enable-all-tools'] !== false;
  const selectedToolNames = Array.isArray(value.tools) ? value.tools : [];
  const selectedKBIds = Array.isArray(value['knowledge-bases'])
    ? value['knowledge-bases']
    : [];
  const selectedMCPResources: BoundMCPResource[] = Array.isArray(
    value['mcp-resources'],
  )
    ? value['mcp-resources']
    : extensions?.bound_mcp_resources || [];
  const mcpResourceReadEnabled =
    typeof value['mcp-resource-agent-read-enabled'] === 'boolean'
      ? value['mcp-resource-agent-read-enabled']
      : (extensions?.mcp_resource_agent_read_enabled ?? true);

  const scopedMCPServers = useMemo(() => {
    if (!extensions) return [];
    const boundServerIds = new Set(extensions.bound_mcp_servers || []);
    return extensions.enable_all_mcp_servers
      ? extensions.available_mcp_servers
      : extensions.available_mcp_servers.filter((server) =>
          boundServerIds.has(server.uuid || ''),
        );
  }, [extensions]);

  const scopedMCPServerIds = useMemo(
    () =>
      new Set(
        scopedMCPServers
          .map((server) => server.uuid)
          .filter((uuid): uuid is string => !!uuid),
      ),
    [scopedMCPServers],
  );

  const scopedMCPServerNames = useMemo(
    () => new Set(scopedMCPServers.map((server) => server.name)),
    [scopedMCPServers],
  );

  const mcpToolOwners = useMemo(
    () => buildMCPToolOwners(scopedMCPServers),
    [scopedMCPServers],
  );

  const pluginToolOwners = useMemo(
    () => buildPluginToolOwners(extensions?.available_plugins || []),
    [extensions],
  );

  const scopedPluginIds = useMemo(
    () =>
      new Set(
        extensions?.enable_all_plugins
          ? (extensions.available_plugins || []).map((plugin) => {
              const metadata = plugin.manifest?.manifest?.metadata;
              return metadata?.name
                ? `${metadata.author || ''}/${metadata.name}`
                : '';
            })
          : (extensions?.bound_plugins || []).map(getBoundPluginId),
      ),
    [extensions],
  );

  const availableTools = useMemo(
    () =>
      tools
        .map((tool) =>
          annotateToolSource(
            tool,
            pluginToolOwners.get(tool.name),
            mcpToolOwners.get(tool.name),
          ),
        )
        .filter((tool) => {
          const source = normalizeToolSource(tool);

          if (source === 'plugin') {
            if (!extensions) {
              return false;
            }
            if (extensions.enable_all_plugins) {
              return true;
            }
            return (
              (tool.source_id && scopedPluginIds.has(tool.source_id)) ||
              (tool.source_name && scopedPluginIds.has(tool.source_name))
            );
          }

          if (source === 'mcp') {
            if (!extensions) {
              return false;
            }
            if (extensions.enable_all_mcp_servers) {
              return true;
            }
            return (
              (tool.source_id && scopedMCPServerIds.has(tool.source_id)) ||
              (tool.source_name && scopedMCPServerNames.has(tool.source_name))
            );
          }

          return true;
        }),
    [
      extensions,
      mcpToolOwners,
      pluginToolOwners,
      scopedMCPServerIds,
      scopedMCPServerNames,
      scopedPluginIds,
      tools,
    ],
  );

  const availableToolNames = useMemo(
    () => new Set(availableTools.map((tool) => tool.name)),
    [availableTools],
  );

  const resourceServers = useMemo(() => {
    return scopedMCPServers.filter(
      (server) =>
        server.runtime_info?.status === 'connected' &&
        (server.runtime_info.resources || []).length > 0,
    );
  }, [scopedMCPServers]);

  const availableMCPResourceKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const server of resourceServers) {
      for (const resource of server.runtime_info?.resources || []) {
        keys.add(getMCPResourceKey(server, resource.uri));
      }
    }
    return keys;
  }, [resourceServers]);

  const scopedSelectedMCPResources = selectedMCPResources.filter((resource) => {
    const server = scopedMCPServers.find(
      (item) =>
        item.uuid === resource.server_uuid ||
        (!resource.server_uuid && item.name === resource.server_name),
    );
    return server
      ? availableMCPResourceKeys.has(getMCPResourceKey(server, resource.uri))
      : false;
  });

  const selectedTools = selectedToolNames
    .map((name: string) => availableTools.find((tool) => tool.name === name))
    .filter((tool): tool is PluginTool => !!tool);

  const selectedKnowledgeBases = selectedKBIds
    .map((kbId: string) => knowledgeBases.find((base) => base.uuid === kbId))
    .filter((base): base is KnowledgeBase => !!base);

  const sourceLabels = useMemo<Record<string, string>>(
    () => ({
      builtin: t('pipelines.localAgent.builtinTools'),
      plugin: t('pipelines.localAgent.pluginTools'),
      mcp: t('pipelines.localAgent.mcpTools'),
      skill: t('pipelines.localAgent.skillTools'),
    }),
    [t],
  );

  const availableToolGroups = useMemo(
    () => buildToolSourceGroups(availableTools, sourceLabels),
    [availableTools, sourceLabels],
  );
  const selectedToolGroups = useMemo(
    () => buildToolSourceGroups(selectedTools, sourceLabels),
    [selectedTools, sourceLabels],
  );

  const handleToggleToolMode = (checked: boolean) => {
    onChange({ 'enable-all-tools': checked });
  };

  const handleConfirmTools = () => {
    onChange({
      tools: tempSelectedToolNames.filter((name) =>
        availableToolNames.has(name),
      ),
    });
    setToolsDialogOpen(false);
  };

  const handleConfirmKnowledgeBases = () => {
    onChange({ 'knowledge-bases': tempSelectedKBIds });
    setKbDialogOpen(false);
  };

  const handleToggleMCPResource = (
    server: MCPServer,
    resource: MCPResource,
    checked: boolean,
  ) => {
    const next = checked
      ? [
          ...scopedSelectedMCPResources.filter(
            (item) => !isSameMCPResource(item, server, resource.uri),
          ),
          {
            server_uuid: server.uuid,
            server_name: server.name,
            uri: resource.uri,
            mode: 'pinned',
            enabled: true,
          },
        ]
      : scopedSelectedMCPResources.filter(
          (item) => !isSameMCPResource(item, server, resource.uri),
        );
    onChange({ 'mcp-resources': next });
  };

  const isMCPResourceSelected = (server: MCPServer, uri: string) =>
    scopedSelectedMCPResources.some(
      (resource) =>
        isSameMCPResource(resource, server, uri) && resource.enabled !== false,
    );

  return (
    <div className="space-y-6">
      {mode !== 'resources' && (
        <div className="space-y-3 rounded-lg border p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-sm font-semibold">
                  {t('pipelines.localAgent.toolsTitle')}
                </h3>
                <InfoTooltip
                  label={t('pipelines.localAgent.toolsScopeTooltip')}
                />
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('pipelines.localAgent.toolsDescription')}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Label
                htmlFor="local-agent-enable-all-tools"
                className="cursor-pointer text-sm font-normal"
              >
                {t('pipelines.localAgent.enableAllTools')}
              </Label>
              <Switch
                id="local-agent-enable-all-tools"
                checked={enableAllTools}
                onCheckedChange={handleToggleToolMode}
              />
            </div>
          </div>

          {enableAllTools ? (
            <div className="flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.localAgent.allToolsEnabled')}
              </p>
            </div>
          ) : selectedTools.length === 0 ? (
            <div className="flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-border">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.localAgent.noToolsSelected')}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {selectedToolGroups.map((sourceGroup) => (
                <div key={sourceGroup.key} className="space-y-2">
                  <div className="flex items-center gap-2 px-1 text-xs font-semibold text-muted-foreground">
                    <span>{sourceGroup.label}</span>
                    <Badge variant="outline" className="h-5 px-1.5 text-[11px]">
                      {sourceGroup.total}
                    </Badge>
                  </div>
                  {sourceGroup.groups.map((providerGroup) => (
                    <div key={providerGroup.key} className="rounded-lg border">
                      <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2">
                        <Wrench className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <span className="min-w-0 truncate text-sm font-medium">
                          {providerGroup.name}
                        </span>
                        <Badge variant="outline" className="ml-auto">
                          {providerGroup.tools.length}
                        </Badge>
                      </div>
                      <div className="divide-y">
                        {providerGroup.tools.map((tool) => (
                          <div
                            key={tool.name}
                            className="flex items-center justify-between gap-3 px-3 py-2"
                          >
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium">
                                {tool.name}
                              </div>
                              {tool.human_desc && (
                                <div className="truncate text-sm text-muted-foreground">
                                  {tool.human_desc}
                                </div>
                              )}
                            </div>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() =>
                                onChange({
                                  tools: selectedToolNames.filter(
                                    (name: string) => name !== tool.name,
                                  ),
                                })
                              }
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            className="w-full"
            disabled={enableAllTools}
            onClick={() => {
              setTempSelectedToolNames(
                selectedToolNames.filter((name: string) =>
                  availableToolNames.has(name),
                ),
              );
              setToolsDialogOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            {t('pipelines.localAgent.editTools')}
          </Button>
        </div>
      )}

      {mode !== 'tools' && (
        <div className="space-y-4 rounded-lg border p-4">
          <div>
            <h3 className="text-sm font-semibold">
              {t('pipelines.localAgent.resourcesTitle')}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {t('pipelines.localAgent.resourcesDescription')}
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  {t('pipelines.localAgent.knowledgeBases')}
                </span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setTempSelectedKBIds(selectedKBIds);
                  setKbDialogOpen(true);
                }}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                {t('common.edit')}
              </Button>
            </div>
            {selectedKnowledgeBases.length === 0 ? (
              <div className="flex h-20 items-center justify-center rounded-lg border-2 border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  {t('knowledge.noKnowledgeBaseSelected')}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {selectedKnowledgeBases.map((base) => (
                  <div
                    key={base.uuid}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
                        {base.emoji && <span>{base.emoji}</span>}
                        <span className="truncate">{base.name}</span>
                        {base.knowledge_engine?.name && (
                          <Badge variant="outline">
                            {extractI18nObject(base.knowledge_engine.name)}
                          </Badge>
                        )}
                      </div>
                      {base.description && (
                        <div className="truncate text-sm text-muted-foreground">
                          {base.description}
                        </div>
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() =>
                        onChange({
                          'knowledge-bases': selectedKBIds.filter(
                            (id: string) => id !== base.uuid,
                          ),
                        })
                      }
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">
                  {t('pipelines.localAgent.mcpResources')}
                </span>
                <InfoTooltip
                  label={t('pipelines.localAgent.mcpResourcesScopeTooltip')}
                />
              </div>
              <div className="flex items-center gap-2">
                <Label
                  htmlFor="local-agent-mcp-resource-read"
                  className="cursor-pointer text-sm font-normal"
                >
                  {t('pipelines.localAgent.enableMCPResourceRead')}
                </Label>
                <InfoTooltip
                  label={t('pipelines.localAgent.mcpResourceReadTooltip')}
                />
                <Switch
                  id="local-agent-mcp-resource-read"
                  checked={mcpResourceReadEnabled}
                  onCheckedChange={(checked) =>
                    onChange({ 'mcp-resource-agent-read-enabled': checked })
                  }
                />
              </div>
            </div>

            {resourceServers.length === 0 ? (
              <div className="flex h-20 items-center justify-center rounded-lg border-2 border-dashed border-border">
                <p className="text-sm text-muted-foreground">
                  {t('pipelines.localAgent.noMCPResourcesAvailable')}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {resourceServers.map((server) => (
                  <div
                    key={server.uuid || server.name}
                    className="rounded-lg border"
                  >
                    <div className="flex items-center gap-2 border-b px-3 py-2">
                      <Server className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{server.name}</span>
                      <Badge variant="outline" className="ml-auto">
                        {server.runtime_info?.resources?.length || 0}
                      </Badge>
                    </div>
                    <div className="divide-y">
                      {(server.runtime_info?.resources || []).map(
                        (resource) => (
                          <label
                            key={getMCPResourceKey(server, resource.uri)}
                            className="flex cursor-pointer items-start gap-3 px-3 py-2 hover:bg-accent"
                          >
                            <Checkbox
                              checked={isMCPResourceSelected(
                                server,
                                resource.uri,
                              )}
                              disabled={!mcpResourceReadEnabled}
                              onCheckedChange={(checked) =>
                                handleToggleMCPResource(
                                  server,
                                  resource,
                                  checked === true,
                                )
                              }
                            />
                            <FileText className="mt-0.5 h-4 w-4 flex-none text-muted-foreground" />
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-medium">
                                {resource.title ||
                                  resource.name ||
                                  resource.uri}
                              </div>
                              <div className="truncate font-mono text-xs text-muted-foreground">
                                {resource.uri}
                              </div>
                              {resource.mime_type && (
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {resource.mime_type}
                                </div>
                              )}
                            </div>
                          </label>
                        ),
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {mode !== 'resources' && (
        <Dialog open={toolsDialogOpen} onOpenChange={setToolsDialogOpen}>
          <DialogContent className="flex max-h-[80vh] max-w-2xl flex-col overflow-hidden">
            <DialogHeader>
              <DialogTitle>{t('pipelines.localAgent.selectTools')}</DialogTitle>
            </DialogHeader>
            <div className="flex-1 space-y-5 overflow-y-auto pr-2">
              {availableToolGroups.map((sourceGroup) => {
                return (
                  <div key={sourceGroup.key} className="rounded-lg border">
                    <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2">
                      <span className="text-sm font-semibold">
                        {sourceGroup.label}
                      </span>
                      {sourceGroup.key === 'mcp' && (
                        <InfoTooltip
                          label={t('pipelines.localAgent.mcpToolsScopeTooltip')}
                        />
                      )}
                      <Badge variant="outline" className="ml-auto">
                        {sourceGroup.total}
                      </Badge>
                    </div>
                    <div className="space-y-4 p-3">
                      {sourceGroup.groups.map((providerGroup) => (
                        <div key={providerGroup.key} className="space-y-2">
                          <div className="flex items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
                            <Wrench className="h-3.5 w-3.5" />
                            <span className="min-w-0 truncate">
                              {providerGroup.name}
                            </span>
                            <Badge
                              variant="outline"
                              className="ml-auto h-5 px-1.5 text-[11px]"
                            >
                              {providerGroup.tools.length}
                            </Badge>
                          </div>
                          <div className="space-y-2">
                            {providerGroup.tools.map((tool) => {
                              const selected = tempSelectedToolNames.includes(
                                tool.name,
                              );
                              return (
                                <div
                                  key={`${providerGroup.key}:${tool.name}`}
                                  className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 hover:bg-accent"
                                  onClick={() =>
                                    setTempSelectedToolNames((prev) =>
                                      prev.includes(tool.name)
                                        ? prev.filter(
                                            (name) => name !== tool.name,
                                          )
                                        : [...prev, tool.name],
                                    )
                                  }
                                >
                                  <Checkbox
                                    checked={selected}
                                    aria-label={`Select ${tool.name}`}
                                  />
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate font-medium">
                                      {tool.name}
                                    </div>
                                    {tool.human_desc && (
                                      <div className="truncate text-sm text-muted-foreground">
                                        {tool.human_desc}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
              {availableToolGroups.length === 0 && (
                <div className="flex h-24 items-center justify-center rounded-lg border-2 border-dashed border-border">
                  <p className="text-sm text-muted-foreground">
                    {t('pipelines.localAgent.noToolsSelected')}
                  </p>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setToolsDialogOpen(false)}
              >
                {t('common.cancel')}
              </Button>
              <Button onClick={handleConfirmTools}>
                {t('common.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {mode !== 'tools' && (
        <Dialog open={kbDialogOpen} onOpenChange={setKbDialogOpen}>
          <DialogContent className="flex max-h-[80vh] max-w-2xl flex-col overflow-hidden">
            <DialogHeader>
              <DialogTitle>
                {t('pipelines.localAgent.selectKnowledgeBases')}
              </DialogTitle>
            </DialogHeader>
            <div className="flex-1 space-y-2 overflow-y-auto pr-2">
              {knowledgeBases.map((base) => {
                const kbId = base.uuid || '';
                const selected = tempSelectedKBIds.includes(kbId);
                return (
                  <div
                    key={kbId}
                    className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 hover:bg-accent"
                    onClick={() =>
                      setTempSelectedKBIds((prev) =>
                        prev.includes(kbId)
                          ? prev.filter((id) => id !== kbId)
                          : [...prev, kbId],
                      )
                    }
                  >
                    <Checkbox
                      checked={selected}
                      aria-label={`Select ${base.name}`}
                    />
                    <Database className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <div className="flex min-w-0 items-center gap-2 font-medium">
                        {base.emoji && <span>{base.emoji}</span>}
                        <span className="truncate">{base.name}</span>
                      </div>
                      {base.description && (
                        <div className="truncate text-sm text-muted-foreground">
                          {base.description}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {knowledgeBases.length === 0 && (
                <div className="flex h-24 items-center justify-center">
                  <p className="text-sm text-muted-foreground">
                    {t('knowledge.noKnowledgeBaseSelected')}
                  </p>
                </div>
              )}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setKbDialogOpen(false)}>
                {t('common.cancel')}
              </Button>
              <Button onClick={handleConfirmKnowledgeBases}>
                {t('common.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
