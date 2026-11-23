import { useEffect, useState, useRef } from 'react';
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
import {
  CircleHelp,
  Plus,
  X,
  Server,
  Wrench,
  Sparkles,
  Puzzle,
  Loader2,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Plugin } from '@/app/infra/entities/plugin';
import {
  MCPServer,
  Skill,
  WorkspaceOperationItem,
  DomainMeta,
  AgentPlatformTool,
} from '@/app/infra/entities/api';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';
import { useInstalledPluginIcon } from '@/app/infra/hooks/useInstalledPluginIcon';
import WorkspaceOperationsPicker from '@/app/home/components/workspace-operations/WorkspaceOperationsPicker';
import AgentApiToolPicker from '@/app/home/agents/components/AgentApiToolPicker';
import { collectSensitiveTools } from '@/app/home/components/sensitive-tools/SensitiveToolsWarning';

function PluginThumbnail({ author, name }: { author: string; name: string }) {
  const iconURL = useInstalledPluginIcon(author, name);

  if (!iconURL) {
    return (
      <div className="w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
        <Puzzle className="size-5 text-muted-foreground" />
      </div>
    );
  }

  return (
    <img
      src={iconURL}
      alt={name}
      className="w-10 h-10 rounded-lg border bg-muted object-cover flex-shrink-0"
    />
  );
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

export default function PipelineExtension({
  pipelineId,
  onSensitiveToolsChange,
}: {
  pipelineId: string;
  onSensitiveToolsChange?: (tools: string[]) => void;
}) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [enableAllPlugins, setEnableAllPlugins] = useState(true);
  const [enableAllMCPServers, setEnableAllMCPServers] = useState(true);
  const [enableAllSkills, setEnableAllSkills] = useState(true);
  const [selectedPlugins, setSelectedPlugins] = useState<Plugin[]>([]);
  const [allPlugins, setAllPlugins] = useState<Plugin[]>([]);
  const [selectedMCPServers, setSelectedMCPServers] = useState<MCPServer[]>([]);
  const [allMCPServers, setAllMCPServers] = useState<MCPServer[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<Skill[]>([]);
  const [allSkills, setAllSkills] = useState<Skill[]>([]);
  const [pluginDialogOpen, setPluginDialogOpen] = useState(false);
  const [mcpDialogOpen, setMcpDialogOpen] = useState(false);
  const [skillDialogOpen, setSkillDialogOpen] = useState(false);
  const [tempSelectedPluginIds, setTempSelectedPluginIds] = useState<string[]>(
    [],
  );
  const [tempSelectedMCPIds, setTempSelectedMCPIds] = useState<string[]>([]);
  const [tempSelectedSkillIds, setTempSelectedSkillIds] = useState<string[]>(
    [],
  );
  const [workspaceOperations, setWorkspaceOperations] = useState<string[]>([]);
  const [platformTools, setPlatformTools] = useState<AgentPlatformTool[]>([]);
  const [allowedPlatformTools, setAllowedPlatformTools] = useState<string[]>(
    [],
  );
  const savedPlatformToolsRef = useRef<string[]>([]);
  const savedWorkspaceOperationsRef = useRef<string[]>([]);
  const [availableWorkspaceOperations, setAvailableWorkspaceOperations] =
    useState<WorkspaceOperationItem[]>([]);
  const [domains, setDomains] = useState<DomainMeta[]>([]);
  const [isSavingOperations, setIsSavingOperations] = useState(false);
  const [dangerousModalOpen, setDangerousModalOpen] = useState(false);
  const pendingOperationsRef = useRef<string[] | null>(null);

  useEffect(() => {
    if (loading) return;
    onSensitiveToolsChange?.(
      collectSensitiveTools(
        platformTools,
        allowedPlatformTools,
        availableWorkspaceOperations,
        workspaceOperations,
      ),
    );
  }, [
    loading,
    onSensitiveToolsChange,
    platformTools,
    allowedPlatformTools,
    availableWorkspaceOperations,
    workspaceOperations,
  ]);

  const isOperationsDirty = (() => {
    const savedTools = new Set(savedPlatformToolsRef.current);
    if (
      allowedPlatformTools.length !== savedTools.size ||
      allowedPlatformTools.some((tool) => !savedTools.has(tool))
    )
      return true;
    const saved = new Set(savedWorkspaceOperationsRef.current);
    if (workspaceOperations.length !== saved.size) return true;
    return workspaceOperations.some((op) => !saved.has(op));
  })();

  const handleResetWorkspaceOperations = () => {
    setWorkspaceOperations([...savedWorkspaceOperationsRef.current]);
    setAllowedPlatformTools([...savedPlatformToolsRef.current]);
  };

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

      setEnableAllPlugins(data.enable_all_plugins ?? true);
      setEnableAllMCPServers(data.enable_all_mcp_servers ?? true);
      setEnableAllSkills(data.enable_all_skills ?? true);

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

      // Load Skills
      const boundSkillNames = new Set(data.bound_skills || []);
      const selectedSkill = (data.available_skills || []).filter((skill) =>
        boundSkillNames.has(skill.name),
      );

      setSelectedSkills(selectedSkill);
      setAllSkills(data.available_skills || []);

      // Load Workspace Operations
      const loadedOps = data.workspace_operations || [];
      setPlatformTools(data.available_platform_tools || []);
      setAllowedPlatformTools(data.allowed_platform_tools || []);
      savedPlatformToolsRef.current = data.allowed_platform_tools || [];
      setWorkspaceOperations(loadedOps);
      savedWorkspaceOperationsRef.current = loadedOps;
      setAvailableWorkspaceOperations(
        data.available_workspace_operations || [],
      );
      setDomains(data.domains || []);
    } catch (error) {
      console.error('Failed to load extensions:', error);
      toast.error(t('pipelines.extensions.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const saveToBackend = async (
    plugins: Plugin[],
    mcpServers: MCPServer[],
    skills: Skill[],
    newEnableAllPlugins?: boolean,
    newEnableAllMCPServers?: boolean,
    newEnableAllSkills?: boolean,
  ) => {
    try {
      const boundPluginsArray = plugins.map((plugin) => {
        const metadata = plugin.manifest.manifest.metadata;
        return {
          author: metadata.author || '',
          name: metadata.name,
        };
      });

      const boundMCPServerIds = mcpServers.map((server) => server.uuid || '');
      const boundSkillIds = skills.map((skill) => skill.name);

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
        boundMCPServerIds,
        newEnableAllPlugins ?? enableAllPlugins,
        newEnableAllMCPServers ?? enableAllMCPServers,
        boundSkillIds,
        newEnableAllSkills ?? enableAllSkills,
        undefined,
        undefined,
        savedWorkspaceOperationsRef.current,
        savedPlatformToolsRef.current,
      );
      toast.success(t('pipelines.extensions.saveSuccess'));
    } catch (error) {
      console.error('Failed to save extensions:', error);
      toast.error(t('pipelines.extensions.saveError'));
      // Reload on error to restore correct state
      loadExtensions();
    }
  };

  const executeSaveWorkspaceOperations = async (opsToSave: string[]) => {
    setIsSavingOperations(true);
    try {
      const boundPluginsArray = selectedPlugins.map((plugin) => {
        const metadata = plugin.manifest.manifest.metadata;
        return {
          author: metadata.author || '',
          name: metadata.name,
        };
      });
      const boundMCPServerIds = selectedMCPServers.map(
        (server) => server.uuid || '',
      );
      const boundSkillIds = selectedSkills.map((skill) => skill.name);

      await backendClient.updatePipelineExtensions(
        pipelineId,
        boundPluginsArray,
        boundMCPServerIds,
        enableAllPlugins,
        enableAllMCPServers,
        boundSkillIds,
        enableAllSkills,
        undefined,
        undefined,
        opsToSave,
        allowedPlatformTools,
      );
      savedWorkspaceOperationsRef.current = opsToSave;
      savedPlatformToolsRef.current = allowedPlatformTools;
      setWorkspaceOperations(opsToSave);
      toast.success(t('workspaceOperations.saveSuccess'));
    } catch (error) {
      console.error('Failed to save workspace operations:', error);
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : '';
      toast.error(
        t('workspaceOperations.saveFailed') + (message ? `: ${message}` : ''),
      );
    } finally {
      setIsSavingOperations(false);
    }
  };

  const handleSaveWorkspaceOperations = async (opsToSave: string[]) => {
    const hasDangerous =
      opsToSave.some((opId) => {
        const op = availableWorkspaceOperations.find(
          (item) => item.id === opId,
        );
        return op?.risk === 'dangerous';
      }) ||
      platformTools.some(
        (tool) =>
          allowedPlatformTools.includes(tool.name) &&
          (tool.risk === 'dangerous' || tool.api === 'bot.message.send'),
      );
    if (hasDangerous) {
      pendingOperationsRef.current = opsToSave;
      setDangerousModalOpen(true);
      return;
    }
    await executeSaveWorkspaceOperations(opsToSave);
  };

  const handleRemovePlugin = async (pluginId: string) => {
    const newPlugins = selectedPlugins.filter(
      (p) => getPluginId(p) !== pluginId,
    );
    setSelectedPlugins(newPlugins);
    await saveToBackend(newPlugins, selectedMCPServers, selectedSkills);
  };

  const handleRemoveMCPServer = async (serverUuid: string) => {
    const newServers = selectedMCPServers.filter((s) => s.uuid !== serverUuid);
    setSelectedMCPServers(newServers);
    await saveToBackend(selectedPlugins, newServers, selectedSkills);
  };

  const handleRemoveSkill = async (skillName: string) => {
    const newSkills = selectedSkills.filter((s) => s.name !== skillName);
    setSelectedSkills(newSkills);
    await saveToBackend(selectedPlugins, selectedMCPServers, newSkills);
  };

  const handleOpenPluginDialog = () => {
    setTempSelectedPluginIds(selectedPlugins.map((p) => getPluginId(p)));
    setPluginDialogOpen(true);
  };

  const handleOpenMCPDialog = () => {
    setTempSelectedMCPIds(selectedMCPServers.map((s) => s.uuid || ''));
    setMcpDialogOpen(true);
  };

  const handleOpenSkillDialog = () => {
    setTempSelectedSkillIds(selectedSkills.map((s) => s.name));
    setSkillDialogOpen(true);
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

  const handleToggleSkill = (skillName: string) => {
    setTempSelectedSkillIds((prev) =>
      prev.includes(skillName)
        ? prev.filter((id) => id !== skillName)
        : [...prev, skillName],
    );
  };

  const handleToggleAllPlugins = () => {
    if (tempSelectedPluginIds.length === allPlugins.length) {
      setTempSelectedPluginIds([]);
    } else {
      setTempSelectedPluginIds(allPlugins.map((p) => getPluginId(p)));
    }
  };

  const handleToggleAllMCPServers = () => {
    if (tempSelectedMCPIds.length === allMCPServers.length) {
      setTempSelectedMCPIds([]);
    } else {
      setTempSelectedMCPIds(allMCPServers.map((s) => s.uuid || ''));
    }
  };

  const handleToggleAllSkills = () => {
    if (tempSelectedSkillIds.length === allSkills.length) {
      setTempSelectedSkillIds([]);
    } else {
      setTempSelectedSkillIds(allSkills.map((s) => s.name));
    }
  };

  const handleConfirmPluginSelection = async () => {
    const newSelected = allPlugins.filter((p) =>
      tempSelectedPluginIds.includes(getPluginId(p)),
    );
    setSelectedPlugins(newSelected);
    setPluginDialogOpen(false);
    await saveToBackend(newSelected, selectedMCPServers, selectedSkills);
  };

  const handleConfirmMCPSelection = async () => {
    const newSelected = allMCPServers.filter((s) =>
      tempSelectedMCPIds.includes(s.uuid || ''),
    );
    setSelectedMCPServers(newSelected);
    setMcpDialogOpen(false);
    await saveToBackend(selectedPlugins, newSelected, selectedSkills);
  };

  const handleConfirmSkillSelection = async () => {
    const newSelected = allSkills.filter((s) =>
      tempSelectedSkillIds.includes(s.name),
    );
    setSelectedSkills(newSelected);
    setSkillDialogOpen(false);
    await saveToBackend(selectedPlugins, selectedMCPServers, newSelected);
  };

  const handleToggleEnableAllPlugins = async (checked: boolean) => {
    setEnableAllPlugins(checked);
    await saveToBackend(
      selectedPlugins,
      selectedMCPServers,
      selectedSkills,
      checked,
      undefined,
      undefined,
    );
  };

  const handleToggleEnableAllMCPServers = async (checked: boolean) => {
    setEnableAllMCPServers(checked);
    await saveToBackend(
      selectedPlugins,
      selectedMCPServers,
      selectedSkills,
      undefined,
      checked,
      undefined,
    );
  };

  const handleToggleEnableAllSkills = async (checked: boolean) => {
    setEnableAllSkills(checked);
    await saveToBackend(
      selectedPlugins,
      selectedMCPServers,
      selectedSkills,
      undefined,
      undefined,
      checked,
    );
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
        <p className="text-sm text-muted-foreground">
          {t('pipelines.extensions.pluginScopeHint')}
        </p>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t('pipelines.extensions.pluginsTitle')}
          </h3>
          <div className="flex items-center gap-2">
            <Label
              htmlFor="enable-all-plugins"
              className="text-sm font-normal cursor-pointer"
            >
              {t('pipelines.extensions.enableAllPlugins')}
            </Label>
            <Switch
              id="enable-all-plugins"
              checked={enableAllPlugins}
              onCheckedChange={handleToggleEnableAllPlugins}
            />
          </div>
        </div>
        <div className="space-y-2">
          {enableAllPlugins ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.allPluginsEnabled')}
              </p>
            </div>
          ) : selectedPlugins.length === 0 ? (
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
                      <PluginThumbnail
                        author={metadata.author || ''}
                        name={metadata.name}
                      />
                      <div className="flex-1">
                        <div className="font-medium">{metadata.name}</div>
                        <div className="text-sm text-muted-foreground">
                          {metadata.author} • v{metadata.version}
                        </div>
                        <div className="flex gap-1 mt-1">
                          <PluginComponentList
                            components={(() => {
                              const componentKindCount: Record<string, number> =
                                {};
                              for (const component of plugin.components) {
                                const kind = component.manifest.manifest.kind;
                                if (componentKindCount[kind]) {
                                  componentKindCount[kind]++;
                                } else {
                                  componentKindCount[kind] = 1;
                                }
                              }
                              return componentKindCount;
                            })()}
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
          disabled={enableAllPlugins}
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('pipelines.extensions.addPlugin')}
        </Button>
      </div>

      {/* MCP Servers Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <h3 className="text-sm font-semibold text-foreground">
              {t('pipelines.extensions.mcpServersTitle')}
            </h3>
            <InfoTooltip
              label={t('pipelines.extensions.mcpServersScopeTooltip')}
            />
          </div>
          <div className="flex items-center gap-2">
            <Label
              htmlFor="enable-all-mcp-servers"
              className="text-sm font-normal cursor-pointer"
            >
              {t('pipelines.extensions.enableAllMCPServers')}
            </Label>
            <InfoTooltip
              label={t('pipelines.extensions.enableAllMCPServersTooltip')}
            />
            <Switch
              id="enable-all-mcp-servers"
              checked={enableAllMCPServers}
              onCheckedChange={handleToggleEnableAllMCPServers}
            />
          </div>
        </div>
        <div className="space-y-2">
          {enableAllMCPServers ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.allMCPServersEnabled')}
              </p>
            </div>
          ) : selectedMCPServers.length === 0 ? (
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
          disabled={enableAllMCPServers}
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('pipelines.extensions.addMCPServer')}
        </Button>
      </div>

      {/* Skills Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t('pipelines.extensions.skillsTitle')}
          </h3>
          <div className="flex items-center gap-2">
            <Label
              htmlFor="enable-all-skills"
              className="text-sm font-normal cursor-pointer"
            >
              {t('pipelines.extensions.enableAllSkills')}
            </Label>
            <Switch
              id="enable-all-skills"
              checked={enableAllSkills}
              onCheckedChange={handleToggleEnableAllSkills}
            />
          </div>
        </div>
        <div className="space-y-2">
          {enableAllSkills ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border bg-muted/30">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.allSkillsEnabled')}
              </p>
            </div>
          ) : selectedSkills.length === 0 ? (
            <div className="flex h-32 items-center justify-center rounded-lg border-2 border-dashed border-border">
              <p className="text-sm text-muted-foreground">
                {t('pipelines.extensions.noSkillsSelected')}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {selectedSkills.map((skill) => (
                <div
                  key={skill.name}
                  className="flex items-center justify-between rounded-lg border p-3 hover:bg-accent"
                >
                  <div className="flex-1 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
                      <Sparkles className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">
                        {skill.display_name || skill.name}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {skill.description}
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveSkill(skill.name)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        <Button
          onClick={handleOpenSkillDialog}
          variant="outline"
          className="w-full"
          disabled={enableAllSkills}
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('pipelines.extensions.addSkill')}
        </Button>
      </div>

      {/* Agent Tools Section: event tools, bot tools and workspace operations */}
      <div className="space-y-3 border-t pt-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-0.5">
            <h3 className="text-sm font-semibold text-foreground">
              {t('agents.apiTools')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('pipelines.extensions.toolsDescription')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isOperationsDirty && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetWorkspaceOperations}
                disabled={isSavingOperations}
              >
                {t('common.cancel')}
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => handleSaveWorkspaceOperations(workspaceOperations)}
              disabled={isSavingOperations || !isOperationsDirty}
            >
              {isSavingOperations ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {t('pipelines.extensions.saveTools')}
            </Button>
          </div>
        </div>

        <AgentApiToolPicker
          platformTools={platformTools}
          platformValue={allowedPlatformTools}
          onPlatformChange={setAllowedPlatformTools}
          hostTools={[]}
          hostValue={[]}
          onHostChange={() => {}}
          scopes={['event', 'platform']}
          workspaceTools={{
            count: availableWorkspaceOperations.length,
            selectedCount: workspaceOperations.length,
            content: (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {t('workspaceOperations.scopeHint')}
                </p>
                <WorkspaceOperationsPicker
                  operations={availableWorkspaceOperations}
                  domains={domains}
                  value={workspaceOperations}
                  onChange={setWorkspaceOperations}
                  disabled={isSavingOperations}
                />
              </div>
            ),
          }}
        />
      </div>

      {/* Dangerous Operations Confirmation Dialog */}
      <AlertDialog
        open={dangerousModalOpen}
        onOpenChange={setDangerousModalOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t('workspaceOperations.dangerousConfirmTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t('workspaceOperations.dangerousConfirmDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setDangerousModalOpen(false);
                pendingOperationsRef.current = null;
              }}
            >
              {t('workspaceOperations.dangerousConfirmCancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={async () => {
                setDangerousModalOpen(false);
                if (pendingOperationsRef.current) {
                  const ops = pendingOperationsRef.current;
                  pendingOperationsRef.current = null;
                  await executeSaveWorkspaceOperations(ops);
                }
              }}
            >
              {t('workspaceOperations.dangerousConfirmAction')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
                    <PluginThumbnail
                      author={metadata.author || ''}
                      name={metadata.name}
                    />
                    <div className="flex-1">
                      <div className="font-medium">{metadata.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {metadata.author} • v{metadata.version}
                      </div>
                      <div className="flex gap-1 mt-1">
                        <PluginComponentList
                          components={(() => {
                            const componentKindCount: Record<string, number> =
                              {};
                            for (const component of plugin.components) {
                              const kind = component.manifest.manifest.kind;
                              if (componentKindCount[kind]) {
                                componentKindCount[kind]++;
                              } else {
                                componentKindCount[kind] = 1;
                              }
                            }
                            return componentKindCount;
                          })()}
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

      {/* Skill Selection Dialog */}
      <Dialog open={skillDialogOpen} onOpenChange={setSkillDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{t('pipelines.extensions.selectSkills')}</DialogTitle>
          </DialogHeader>
          {allSkills.length > 0 && (
            <div
              className="flex items-center gap-3 px-1 py-2 border-b cursor-pointer"
              onClick={handleToggleAllSkills}
            >
              <Checkbox
                checked={
                  tempSelectedSkillIds.length === allSkills.length &&
                  allSkills.length > 0
                }
                onCheckedChange={handleToggleAllSkills}
              />
              <span className="text-sm font-medium">
                {t('pipelines.extensions.selectAll')}
              </span>
            </div>
          )}
          <div className="flex-1 overflow-y-auto space-y-2 pr-2">
            {allSkills.length === 0 ? (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-muted-foreground">
                  {t('pipelines.extensions.noSkillsAvailable')}
                </p>
              </div>
            ) : (
              allSkills.map((skill) => {
                const isSelected = tempSelectedSkillIds.includes(skill.name);
                return (
                  <div
                    key={skill.name}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent cursor-pointer"
                    onClick={() => handleToggleSkill(skill.name)}
                  >
                    <Checkbox checked={isSelected} />
                    <div className="w-10 h-10 rounded-lg border bg-muted flex items-center justify-center flex-shrink-0">
                      <Sparkles className="h-5 w-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">
                        {skill.display_name || skill.name}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        {skill.description}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSkillDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={handleConfirmSkillSelection}>
              {t('common.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
