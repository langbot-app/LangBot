'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { backendClient } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, X, Server, Wrench } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Plugin } from '@/app/infra/entities/plugin';
import { MCPServer } from '@/app/infra/entities/api';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';

export default function PipelineExtension({
  pipelineId,
}: {
  pipelineId: string;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [selectedPlugins, setSelectedPlugins] = useState<Plugin[]>([]);
  const [allPlugins, setAllPlugins] = useState<Plugin[]>([]);
  const [selectedMCPServers, setSelectedMCPServers] = useState<MCPServer[]>([]);
  const [allMCPServers, setAllMCPServers] = useState<MCPServer[]>([]);
  const [pluginDialogOpen, setPluginDialogOpen] = useState(false);
  const [mcpDialogOpen, setMcpDialogOpen] = useState(false);
  const [tempSelectedPluginIds, setTempSelectedPluginIds] = useState<string[]>(
    [],
  );
  const [tempSelectedMCPIds, setTempSelectedMCPIds] = useState<string[]>([]);

  useEffect(() => {
    loadExtensions();
  }, [pipelineId]);

  const getPluginId = (plugin: Plugin): string => {
    const author = plugin.manifest.manifest.metadata.author;
    const name = plugin.manifest.manifest.metadata.name;
    return `${author}/${name}`;
  };

  const loadExtensions = async () => {
    try {
      setLoading(true);
      const data = await backendClient.getPipelineExtensions(pipelineId);

      const boundPluginIds = new Set(
        data.bound_plugins.map((p) => `${p.author}/${p.name}`),
      );

      const selected = data.available_plugins.filter((plugin) =>
        boundPluginIds.has(getPluginId(plugin)),
      );

      setSelectedPlugins(selected);
      setAllPlugins(data.available_plugins);

      // Load MCP servers
      const boundMCPServerIds = new Set(data.bound_mcp_servers || []);
      const selectedMCP = data.available_mcp_servers.filter((server) =>
        boundMCPServerIds.has(server.uuid || ''),
      );

      setSelectedMCPServers(selectedMCP);
      setAllMCPServers(data.available_mcp_servers);
    } catch (error) {
      console.error('Failed to load extensions:', error);
      toast.error(t('pipelines.extensions.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const saveToBackend = async (plugins: Plugin[], mcpServers: MCPServer[]) => {
    try {
      const boundPluginsArray = plugins.map((plugin) => {
        const metadata = plugin.manifest.manifest.metadata;
        return {
          author: metadata.author || '',
          name: metadata.name,
        };
      });

      const boundMCPServerIds = mcpServers.map((server) => server.uuid || '');

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
        boundMCPServerIds,
      );
      toast.success(t('pipelines.extensions.saveSuccess'));
    } catch (error) {
      console.error('Failed to save extensions:', error);
      toast.error(t('pipelines.extensions.saveError'));
      // Reload on error to restore correct state
      loadExtensions();
    }
  };

  const handleRemovePlugin = async (pluginId: string) => {
    const newPlugins = selectedPlugins.filter(
      (p) => getPluginId(p) !== pluginId,
    );
    setSelectedPlugins(newPlugins);
    await saveToBackend(newPlugins, selectedMCPServers);
  };

  const handleRemoveMCPServer = async (serverUuid: string) => {
    const newServers = selectedMCPServers.filter((s) => s.uuid !== serverUuid);
    setSelectedMCPServers(newServers);
    await saveToBackend(selectedPlugins, newServers);
  };

  const handleOpenPluginDialog = () => {
    setTempSelectedPluginIds(selectedPlugins.map((p) => getPluginId(p)));
    setPluginDialogOpen(true);
  };

  const handleOpenMCPDialog = () => {
    setTempSelectedMCPIds(selectedMCPServers.map((s) => s.uuid || ''));
    setMcpDialogOpen(true);
  };

  const handleTogglePlugin = (pluginId: string) => {
    setTempSelectedPluginIds((prev) =>
      prev.includes(pluginId)
        ? prev.filter((id) => id !== pluginId)
        : [...prev, pluginId],
    );
  };

  const handleToggleMCPServer = (serverUuid: string) => {
    setTempSelectedMCPIds((prev) =>
      prev.includes(serverUuid)
        ? prev.filter((id) => id !== serverUuid)
        : [...prev, serverUuid],
    );
  };

  const handleToggleAllPlugins = () => {
    if (tempSelectedPluginIds.length === allPlugins.length) {
      // Deselect all
      setTempSelectedPluginIds([]);
    } else {
      // Select all
      setTempSelectedPluginIds(allPlugins.map((p) => getPluginId(p)));
    }
  };

  const handleToggleAllMCPServers = () => {
    if (tempSelectedMCPIds.length === allMCPServers.length) {
      // Deselect all
      setTempSelectedMCPIds([]);
    } else {
      // Select all
      setTempSelectedMCPIds(allMCPServers.map((s) => s.uuid || ''));
    }
  };

  const handleConfirmPluginSelection = async () => {
    const newSelected = allPlugins.filter((p) =>
      tempSelectedPluginIds.includes(getPluginId(p)),
    );
    setSelectedPlugins(newSelected);
    setPluginDialogOpen(false);
    await saveToBackend(newSelected, selectedMCPServers);
  };

  const handleConfirmMCPSelection = async () => {
    const newSelected = allMCPServers.filter((s) =>
      tempSelectedMCPIds.includes(s.uuid || ''),
    );
    setSelectedMCPServers(newSelected);
    setMcpDialogOpen(false);
    await saveToBackend(selectedPlugins, newSelected);
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Plugins Section */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">
          {t('pipelines.extensions.pluginsTitle')}
        </h3>
        <div className="space-y-2">
          {selectedPlugins.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.noPluginsSelected')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {selectedPlugins.map((plugin) => {
                const pluginId = getPluginId(plugin);
                const metadata = plugin.manifest.manifest.metadata;
                return (
                  <div
                    key={pluginId}
                    className="flex items-center justify-between rounded-lg border p-3 hover:bg-accent"
                  >
                    <div className="flex-1 flex items-center gap-3">
                      <img
                        src={backendClient.getPluginIconURL(
                          metadata.author || '',
                          metadata.name,
                        )}
                        alt={metadata.name}
                        className="w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                      />
                      <div className="flex-1">
                        <div className="font-medium">{metadata.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {metadata.author} • v{metadata.version}
                        </div>
                        <div className="flex gap-1 mt-1">
                          <PluginComponentList
                            components={plugin.components}
                            showComponentName={true}
                            showTitle={false}
                            useBadge={true}
                            t={t}
                          />
                        </div>
                      </div>
                      {!plugin.enabled && (
                        <Badge variant="secondary">
                          {t('pipelines.extensions.disabled')}
                        </Badge>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemovePlugin(pluginId)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <Button
          onClick={handleOpenPluginDialog}
          variant="outline"
          className="w-full"
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('pipelines.extensions.addPlugin')}
        </Button>
      </div>

      {/* MCP Servers Section */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-foreground">
          {t('pipelines.extensions.mcpServersTitle')}
        </h3>
        <div className="space-y-2">
          {selectedMCPServers.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.noMCPServersSelected')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {selectedMCPServers.map((server) => (
                <div
                  key={server.uuid}
                  className="flex items-center justify-between rounded-lg border p-3 hover:bg-accent"
                >
                  <div className="flex-1 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
                      <Server className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">{server.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {server.mode}
                      </div>
                      {server.runtime_info &&
                        server.runtime_info.status === 'connected' && (
                          <Badge
                            variant="outline"
                            className="flex items-center gap-1 mt-1"
                          >
                            <Wrench className="h-3 w-3 text-black dark:text-white" />
                            <span className="text-xs text-black dark:text-white">
                              {t('pipelines.extensions.toolCount', {
                                count: server.runtime_info.tool_count || 0,
                              })}
                            </span>
                          </Badge>
                        )}
                    </div>
                    {!server.enable && (
                      <Badge variant="secondary">
                        {t('pipelines.extensions.disabled')}
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveMCPServer(server.uuid || '')}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Button
          onClick={handleOpenMCPDialog}
          variant="outline"
          className="w-full"
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('pipelines.extensions.addMCPServer')}
        </Button>
      </div>

      {/* Plugin Selection Dialog */}
      <Dialog open={pluginDialogOpen} onOpenChange={setPluginDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t('pipelines.extensions.selectPlugins')}</DialogTitle>
          </DialogHeader>
          {allPlugins.length > 0 && (
            <div
              className="flex items-center gap-3 px-1 py-2 border-b cursor-pointer"
              onClick={handleToggleAllPlugins}
            >
              <Checkbox
                checked={
                  tempSelectedPluginIds.length === allPlugins.length &&
                  allPlugins.length > 0
                }
                onCheckedChange={handleToggleAllPlugins}
              />
              <span className="text-sm font-medium">
                {t('pipelines.extensions.selectAll')}
              </span>
            </div>
          )}
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {allPlugins.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-muted-foreground">
                  {t('pipelines.extensions.noPluginsInstalled')}
                </p>
              </div>
            ) : (
              allPlugins.map((plugin) => {
                const pluginId = getPluginId(plugin);
                const metadata = plugin.manifest.manifest.metadata;
                const isSelected = tempSelectedPluginIds.includes(pluginId);
                return (
                  <div
                    key={pluginId}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer"
                    onClick={() => handleTogglePlugin(pluginId)}
                  >
                    <Checkbox checked={isSelected} />
                    <img
                      src={backendClient.getPluginIconURL(
                        metadata.author || '',
                        metadata.name,
                      )}
                      alt={metadata.name}
                      className="w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
                    />
                    <div className="flex-1">
                      <div className="font-medium">{metadata.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {metadata.author} • v{metadata.version}
                      </div>
                      <div className="flex gap-1 mt-1">
                        <PluginComponentList
                          components={plugin.components}
                          showComponentName={true}
                          showTitle={false}
                          useBadge={true}
                          t={t}
                        />
                      </div>
                    </div>
                    {!plugin.enabled && (
                      <Badge variant="secondary">
                        {t('pipelines.extensions.disabled')}
                      </Badge>
                    )}
                  </div>
                );
              })
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setPluginDialogOpen(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button onClick={handleConfirmPluginSelection}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MCP Server Selection Dialog */}
      <Dialog open={mcpDialogOpen} onOpenChange={setMcpDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {t('pipelines.extensions.selectMCPServers')}
            </DialogTitle>
          </DialogHeader>
          {allMCPServers.length > 0 && (
            <div
              className="flex items-center gap-3 px-1 py-2 border-b cursor-pointer"
              onClick={handleToggleAllMCPServers}
            >
              <Checkbox
                checked={
                  tempSelectedMCPIds.length === allMCPServers.length &&
                  allMCPServers.length > 0
                }
                onCheckedChange={handleToggleAllMCPServers}
              />
              <span className="text-sm font-medium">
                {t('pipelines.extensions.selectAll')}
              </span>
            </div>
          )}
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {allMCPServers.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-muted-foreground">
                  {t('pipelines.extensions.noMCPServersConfigured')}
                </p>
              </div>
            ) : (
              allMCPServers.map((server) => {
                const isSelected = tempSelectedMCPIds.includes(
                  server.uuid || '',
                );
                return (
                  <div
                    key={server.uuid}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer"
                    onClick={() => handleToggleMCPServer(server.uuid || '')}
                  >
                    <Checkbox checked={isSelected} />
                    <div className="w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
                      <Server className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">{server.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {server.mode}
                      </div>
                      {server.runtime_info &&
                        server.runtime_info.status === 'connected' && (
                          <Badge
                            variant="outline"
                            className="flex items-center gap-1 mt-1"
                          >
                            <Wrench className="h-3 w-3 text-black dark:text-white" />
                            <span className="text-xs text-black dark:text-white">
                              {t('pipelines.extensions.toolCount', {
                                count: server.runtime_info.tool_count || 0,
                              })}
                            </span>
                          </Badge>
                        )}
                    </div>
                    {!server.enable && (
                      <Badge variant="secondary">
                        {t('pipelines.extensions.disabled')}
                      </Badge>
                    )}
                  </div>
                );
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMcpDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleConfirmMCPSelection}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
