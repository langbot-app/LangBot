import MarketPage from '@/app/home/plugins/components/plugin-market/PluginMarketComponent';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Download,
  PlusIcon,
  ChevronLeft,
  Server,
  Github,
  BookOpen,
  FileArchive,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import {
  usePluginInstallTasks,
} from '@/app/home/plugins/components/plugin-install-task';
import MCPForm from '@/app/home/mcp/components/mcp-form/MCPForm';
import type { MCPFormHandle } from '@/app/home/mcp/components/mcp-form/MCPForm';
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

type PopoverView = 'menu' | 'mcp' | 'skill' | 'github';

enum GithubInstallStatus {
  WAIT_INPUT = 'wait_input',
  SELECT_RELEASE = 'select_release',
  SELECT_ASSET = 'select_asset',
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  ERROR = 'error',
}

interface GithubRelease {
  id: number;
  tag_name: string;
  name: string;
  published_at: string;
  prerelease: boolean;
  draft: boolean;
  source_type?: 'release' | 'tag' | 'branch';
  archive_url?: string;
}

interface GithubAsset {
  id: number;
  name: string;
  size: number;
  download_url: string;
  content_type: string;
}

enum PluginInstallStatus {
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function AddExtensionPage() {
  const { t } = useTranslation();

  if (!systemInfo?.enable_marketplace) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <p className="text-muted-foreground">{t('plugins.marketplace')}</p>
      </div>
    );
  }

  return <AddExtensionContent />;
}

function AddExtensionContent() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { refreshPlugins, refreshMCPServers, refreshSkills } = useSidebarData();
  const {
    addTask,
    setSelectedTaskId,
    registerOnTaskComplete,
    unregisterOnTaskComplete,
    clearCompletedTasks,
  } = usePluginInstallTasks();
  const [modalOpen, setModalOpen] = useState(false);
  const [installInfo, setInstallInfo] = useState<Record<string, string>>({});
  const [installExtensionType, setInstallExtensionType] = useState<
    'plugin' | 'mcp' | 'skill'
  >('plugin');
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.ASK_CONFIRM);
  const [installError, setInstallError] = useState<string | null>(null);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [popoverView, setPopoverView] = useState<PopoverView>('menu');
  const [isDragOver, setIsDragOver] = useState(false);
  const [skillUploadState, setSkillUploadState] = useState<
    'idle' | 'uploading' | 'done' | 'error'
  >('idle');
  const [skillUploadFileName, setSkillUploadFileName] = useState('');
  const [skillUploadError, setSkillUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mcpFormRef = useRef<MCPFormHandle>(null);
  const [mcpTesting, setMcpTesting] = useState(false);

  // GitHub install state
  const [githubURL, setGithubURL] = useState('');
  const [githubReleases, setGithubReleases] = useState<GithubRelease[]>([]);
  const [selectedRelease, setSelectedRelease] = useState<GithubRelease | null>(null);
  const [githubAssets, setGithubAssets] = useState<GithubAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<GithubAsset | null>(null);
  const [githubOwner, setGithubOwner] = useState('');
  const [githubRepo, setGithubRepo] = useState('');
  const [fetchingReleases, setFetchingReleases] = useState(false);
  const [fetchingAssets, setFetchingAssets] = useState(false);
  const [githubInstallStatus, setGithubInstallStatus] =
    useState<GithubInstallStatus>(GithubInstallStatus.WAIT_INPUT);
  const [githubInstallError, setGithubInstallError] = useState<string | null>(null);

  useEffect(() => {
    // Clear any stale completed tasks on mount
    clearCompletedTasks();
  }, []);

  useEffect(() => {
    const onComplete = (_taskId: number, success: boolean) => {
      if (success) {
        toast.success(t('plugins.installSuccess'));
        refreshPlugins();
      }
    };
    registerOnTaskComplete(onComplete);
    return () => {
      unregisterOnTaskComplete(onComplete);
    };
  }, [registerOnTaskComplete, unregisterOnTaskComplete, refreshPlugins, t]);

  const handleInstallPlugin = useCallback(
    async (plugin: PluginV4) => {
      setInstallInfo({
        plugin_author: plugin.author,
        plugin_name: plugin.name,
        plugin_version: plugin.latest_version,
      });
      setInstallExtensionType(plugin.type || 'plugin');
      setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
      setInstallError(null);
      setModalOpen(true);
    },
    [],
  );

  function handleModalConfirm() {
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
    const pluginDisplayName = `${installInfo.plugin_author}/${installInfo.plugin_name}`;
    httpClient
      .installPluginFromMarketplace(
        installInfo.plugin_author,
        installInfo.plugin_name,
        installInfo.plugin_version,
      )
      .then((resp: { task_id: number }) => {
        const taskId = resp.task_id;
        const taskKey = `marketplace-${taskId}`;
        addTask({
          taskId,
          pluginName: pluginDisplayName,
          source: 'marketplace',
          extensionType: installExtensionType,
        });
        setSelectedTaskId(taskKey);
        setModalOpen(false);
      })
      .catch((err: { msg?: string }) => {
        setInstallError(err.msg || null);
        setPluginInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  const validateFileType = (file: File): boolean => {
    const allowedExtensions = ['.lbpkg', '.zip'];
    const fileName = file.name.toLowerCase();
    return allowedExtensions.some((ext) => fileName.endsWith(ext));
  };

  const getExtensionTypeFromFile = (file: File): 'plugin' | 'skill' => {
    const fileName = file.name.toLowerCase();
    if (fileName.endsWith('.lbpkg')) return 'plugin';
    if (fileName.endsWith('.zip')) return 'skill';
    return 'plugin';
  };

  const uploadFile = useCallback(
    async (file: File) => {
      if (!validateFileType(file)) {
        toast.error(t('addExtension.unsupportedFileType'));
        return;
      }

      const extType = getExtensionTypeFromFile(file);
      const fileName = file.name;
      const fileSize = file.size;

      setPopoverOpen(false);
      // Clear any selected task to avoid showing stale dialogs
      setSelectedTaskId(null);

      if (extType === 'plugin') {
        httpClient
          .installPluginFromLocal(file)
          .then((resp) => {
            const taskId = resp.task_id;
            const taskKey = `local-${taskId}`;
            addTask({
              taskId,
              pluginName: fileName,
              source: 'local',
              extensionType: 'plugin',
              fileSize,
            });
            setSelectedTaskId(taskKey);
          })
          .catch((err: { msg?: string }) => {
            toast.error(t('plugins.installFailed') + (err.msg || ''));
          });
      } else {
        setSkillUploadFileName(fileName);
        setSkillUploadState('uploading');
        setSkillUploadError(null);
        httpClient
          .installSkillFromUpload(file)
          .then(() => {
            setSkillUploadState('done');
            refreshPlugins();
            refreshSkills();
          })
          .catch((err: { msg?: string }) => {
            setSkillUploadState('error');
            setSkillUploadError(err.msg || null);
          });
      }
    },
    [t, addTask, setSelectedTaskId, refreshPlugins],
  );

  const handleFileSelect = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, []);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        uploadFile(file);
      }
      event.target.value = '';
    },
    [uploadFile],
  );

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDragOver(false);
      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        uploadFile(files[0]);
      }
    },
    [uploadFile],
  );

  function handleMCPCreated(serverName: string) {
    refreshMCPServers();
    setPopoverView('menu');
    setPopoverOpen(false);
  }

  function handleSkillCreated(skillName: string) {
    refreshPlugins();
    refreshSkills();
    setPopoverView('menu');
    setPopoverOpen(false);
  }

  async function checkExtensionsLimit(): Promise<boolean> {
    const maxExtensions = systemInfo.limitation?.max_extensions ?? -1;
    if (maxExtensions < 0) return true;
    try {
      const [pluginsResp, mcpResp] = await Promise.all([
        httpClient.getPlugins(),
        httpClient.getMCPServers(),
      ]);
      const total =
        (pluginsResp.plugins?.length ?? 0) + (mcpResp.servers?.length ?? 0);
      if (total >= maxExtensions) {
        toast.error(
          t('limitation.maxExtensionsReached', { max: maxExtensions }),
        );
        return false;
      }
    } catch {
      // If we can't check, let backend handle it
    }
    return true;
  }

  function resetGithubState() {
    setGithubURL('');
    setGithubReleases([]);
    setSelectedRelease(null);
    setGithubAssets([]);
    setSelectedAsset(null);
    setGithubOwner('');
    setGithubRepo('');
    setFetchingReleases(false);
    setFetchingAssets(false);
    setGithubInstallStatus(GithubInstallStatus.WAIT_INPUT);
    setGithubInstallError(null);
  }

  async function fetchGithubReleases() {
    if (!githubURL.trim()) {
      toast.error(t('plugins.enterRepoUrl'));
      return;
    }

    setFetchingReleases(true);
    setGithubInstallError(null);

    try {
      const result = await httpClient.getGithubReleases(githubURL);
      setGithubReleases(result.releases);
      setGithubOwner(result.owner);
      setGithubRepo(result.repo);

      if (result.releases.length === 0) {
        toast.warning(t('plugins.noReleasesFound'));
      } else {
        setGithubInstallStatus(GithubInstallStatus.SELECT_RELEASE);
      }
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setGithubInstallError(errorMessage || t('plugins.fetchReleasesError'));
      setGithubInstallStatus(GithubInstallStatus.ERROR);
    } finally {
      setFetchingReleases(false);
    }
  }

  async function handleReleaseSelect(release: GithubRelease) {
    setSelectedRelease(release);
    setFetchingAssets(true);
    setGithubInstallError(null);

    try {
      const result = await httpClient.getGithubReleaseAssets(
        githubOwner,
        githubRepo,
        release.id,
        release.tag_name,
        release.source_type,
        release.archive_url,
      );
      setGithubAssets(result.assets);

      if (result.assets.length === 0) {
        toast.warning(t('plugins.noAssetsFound'));
      } else {
        setGithubInstallStatus(GithubInstallStatus.SELECT_ASSET);
      }
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setGithubInstallError(errorMessage || t('plugins.fetchAssetsError'));
      setGithubInstallStatus(GithubInstallStatus.ERROR);
    } finally {
      setFetchingAssets(false);
    }
  }

  function handleAssetSelect(asset: GithubAsset) {
    setSelectedAsset(asset);
    setGithubInstallStatus(GithubInstallStatus.ASK_CONFIRM);
  }

  async function handleGithubConfirm() {
    if (!selectedAsset || !selectedRelease) return;
    if (!(await checkExtensionsLimit())) return;

    setGithubInstallStatus(GithubInstallStatus.INSTALLING);
    const pluginDisplayName = `${githubOwner}/${githubRepo}`;
    httpClient
      .installPluginFromGithub(
        selectedAsset.download_url,
        githubOwner,
        githubRepo,
        selectedRelease.tag_name,
      )
      .then((resp) => {
        const taskId = resp.task_id;
        const taskKey = `github-${taskId}`;
        addTask({
          taskId,
          pluginName: pluginDisplayName,
          source: 'github',
          extensionType: 'plugin',
          fileSize: selectedAsset.size,
        });
        setSelectedTaskId(taskKey);
        resetGithubState();
        setPopoverOpen(false);
      })
      .catch((err) => {
        setGithubInstallError(err.msg);
        setGithubInstallStatus(GithubInstallStatus.ERROR);
      });
  }

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  function getPopoverWidth(): string {
    switch (popoverView) {
      case 'mcp':
        return 'w-[500px]';
      case 'skill':
        return 'w-[460px]';
      case 'github':
        return 'w-[460px]';
      default:
        return 'w-[360px]';
    }
  }

  const extensionActions = (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".lbpkg,.zip"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />

      <Popover
        open={popoverOpen}
        onOpenChange={(open) => {
          setPopoverOpen(open);
          if (!open) {
            setPopoverView('menu');
          }
        }}
      >
        <PopoverTrigger asChild>
          <Button
            variant="default"
            className="px-3 sm:px-4 py-2 cursor-pointer flex-shrink-0"
          >
            <PlusIcon className="w-4 h-4" />
            <span className="whitespace-nowrap">
              {t('addExtension.manualAdd')}
            </span>
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className={`${getPopoverWidth()} p-4 max-h-[80vh] overflow-y-auto`}
          align="end"
        >
          {/* ===== Menu View ===== */}
          {popoverView === 'menu' && (
            <div className="space-y-4">
              {/* File upload area */}
              <div
                className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
                  isDragOver
                    ? 'border-primary bg-primary/5'
                    : 'border-muted-foreground/25 hover:border-primary/50'
                }`}
                onClick={handleFileSelect}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                <FileArchive
                  className={`mx-auto h-10 w-10 mb-3 ${
                    isDragOver ? 'text-primary' : 'text-muted-foreground/50'
                  }`}
                />
                <p className="text-sm font-medium">
                  {t('addExtension.uploadExtension')}
                </p>
                <p className="text-xs text-muted-foreground mt-1.5">
                  {t('addExtension.uploadHint')}
                </p>
              </div>

              {/* Divider */}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-popover px-2 text-muted-foreground">
                    {t('addExtension.orContinueWith')}
                  </span>
                </div>
              </div>

              {/* MCP Config button */}
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                onClick={() => setPopoverView('mcp')}
              >
                <Server className="w-4 h-4" />
                {t('mcp.addMCPServer')}
              </Button>

              {/* Two side-by-side buttons */}
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  className="flex-col h-auto py-3 gap-1"
                  onClick={() => setPopoverView('github')}
                >
                  <Github className="w-4 h-4" />
                  <span className="text-xs">
                    {t('addExtension.installFromGithub')}
                  </span>
                </Button>
                <Button
                  variant="outline"
                  className="flex-col h-auto py-3 gap-1"
                  onClick={() => setPopoverView('skill')}
                >
                  <BookOpen className="w-4 h-4" />
                  <span className="text-xs">
                    {t('addExtension.createSkill')}
                  </span>
                </Button>
              </div>

              {/* Hints for the two buttons */}
              <div className="grid grid-cols-2 gap-2">
                <p className="text-[11px] text-muted-foreground text-center px-1">
                  {t('addExtension.installFromGithubHint')}
                </p>
                <p className="text-[11px] text-muted-foreground text-center px-1">
                  {t('addExtension.createSkillHint')}
                </p>
              </div>
            </div>
          )}

          {/* ===== MCP Form View ===== */}
          {popoverView === 'mcp' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setPopoverView('menu')}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <h4 className="text-sm font-medium leading-none">
                  {t('mcp.createServer')}
                </h4>
              </div>

              <div className="max-h-[60vh] overflow-y-auto pr-1">
                <MCPForm
                  ref={mcpFormRef}
                  initServerName={undefined}
                  onFormSubmit={() => {}}
                  onNewServerCreated={handleMCPCreated}
                  onTestingChange={setMcpTesting}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => mcpFormRef.current?.testMcp()}
                  disabled={mcpTesting}
                >
                  {t('common.test')}
                </Button>
                <Button
                  type="submit"
                  form="mcp-form"
                  size="sm"
                  onClick={async (e) => {
                    if (!(await checkExtensionsLimit())) {
                      e.preventDefault();
                    }
                  }}
                >
                  {t('common.submit')}
                </Button>
              </div>
            </div>
          )}

          {/* ===== Skill Form View ===== */}
          {popoverView === 'skill' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => setPopoverView('menu')}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <h4 className="text-sm font-medium leading-none">
                  {t('skills.createSkill')}
                </h4>
              </div>

              <div className="max-h-[60vh] overflow-y-auto pr-1">
                <SkillForm
                  initSkillName={undefined}
                  onNewSkillCreated={handleSkillCreated}
                  onSkillUpdated={() => {}}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t">
                <Button type="submit" form="skill-form" size="sm">
                  {t('common.save')}
                </Button>
              </div>
            </div>
          )}

          {/* ===== GitHub Install View ===== */}
          {popoverView === 'github' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => {
                    resetGithubState();
                    setPopoverView('menu');
                  }}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <h4 className="text-sm font-medium leading-none">
                  {t('plugins.installFromGithub')}
                </h4>
              </div>

              <div className="max-h-[60vh] overflow-y-auto pr-1 space-y-3">
                {githubInstallStatus === GithubInstallStatus.WAIT_INPUT && (
                  <div className="space-y-2">
                    <p className="text-xs text-muted-foreground">
                      {t('plugins.enterRepoUrl')}
                    </p>
                    <Input
                      placeholder={t('plugins.repoUrlPlaceholder')}
                      value={githubURL}
                      onChange={(e) => setGithubURL(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') fetchGithubReleases();
                      }}
                    />
                    <Button
                      className="w-full"
                      onClick={fetchGithubReleases}
                      disabled={!githubURL.trim() || fetchingReleases}
                    >
                      {fetchingReleases && (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      )}
                      {fetchingReleases
                        ? t('plugins.loading')
                        : t('common.confirm')}
                    </Button>
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.SELECT_RELEASE && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium">
                        {t('plugins.selectRelease')}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs px-2"
                        onClick={() => {
                          setGithubInstallStatus(GithubInstallStatus.WAIT_INPUT);
                          setGithubReleases([]);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToRepoUrl')}
                      </Button>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto space-y-1.5">
                      {githubReleases.map((release) => (
                        <div
                          key={release.id}
                          className="flex items-center justify-between rounded-md border p-2 hover:bg-accent cursor-pointer text-sm"
                          onClick={() => handleReleaseSelect(release)}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate text-xs">
                              {release.name || release.tag_name}
                            </div>
                            <div className="text-[11px] text-muted-foreground">
                              {release.tag_name} &bull;{' '}
                              {new Date(release.published_at).toLocaleDateString()}
                            </div>
                          </div>
                          {release.prerelease && (
                            <span className="text-[10px] bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-1.5 py-0.5 rounded ml-2 shrink-0">
                              Pre
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                    {fetchingAssets && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        {t('plugins.loading')}
                      </p>
                    )}
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.SELECT_ASSET && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium">
                        {t('plugins.selectAsset')}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs px-2"
                        onClick={() => {
                          setGithubInstallStatus(GithubInstallStatus.SELECT_RELEASE);
                          setGithubAssets([]);
                          setSelectedAsset(null);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToReleases')}
                      </Button>
                    </div>
                    {selectedRelease && (
                      <div className="p-1.5 bg-muted rounded text-[11px]">
                        <span className="font-medium">
                          {selectedRelease.name || selectedRelease.tag_name}
                        </span>
                      </div>
                    )}
                    <div className="max-h-[300px] overflow-y-auto space-y-1.5">
                      {githubAssets.map((asset) => (
                        <div
                          key={asset.id}
                          className="flex items-center justify-between rounded-md border p-2 hover:bg-accent cursor-pointer"
                          onClick={() => handleAssetSelect(asset)}
                        >
                          <span className="text-xs truncate">{asset.name}</span>
                          <span className="text-[11px] text-muted-foreground ml-2 shrink-0">
                            {formatFileSize(asset.size)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.ASK_CONFIRM && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium">
                        {t('plugins.confirmInstall')}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs px-2"
                        onClick={() => {
                          setGithubInstallStatus(GithubInstallStatus.SELECT_ASSET);
                          setSelectedAsset(null);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToAssets')}
                      </Button>
                    </div>
                    {selectedRelease && selectedAsset && (
                      <div className="p-2 bg-muted rounded space-y-1 text-xs">
                        <div>
                          <span className="font-medium">Repository: </span>
                          <span>{githubOwner}/{githubRepo}</span>
                        </div>
                        <div>
                          <span className="font-medium">Release: </span>
                          <span>{selectedRelease.tag_name}</span>
                        </div>
                        <div>
                          <span className="font-medium">File: </span>
                          <span>{selectedAsset.name}</span>
                        </div>
                      </div>
                    )}
                    <Button
                      className="w-full"
                      onClick={handleGithubConfirm}
                    >
                      {t('common.confirm')}
                    </Button>
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.INSTALLING && (
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('plugins.installing')}</span>
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.ERROR && (
                  <div className="space-y-2">
                    <p className="text-xs text-destructive">
                      {t('plugins.installFailed')}
                    </p>
                    {githubInstallError && (
                      <p className="text-xs text-muted-foreground break-all">
                        {githubInstallError}
                      </p>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full"
                      onClick={resetGithubState}
                    >
                      {t('common.retry')}
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </PopoverContent>
      </Popover>
    </>
  );

  return (
    <>
      <div className="h-full flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <MarketPage
            installPlugin={handleInstallPlugin}
            headerActions={extensionActions}
          />
        </div>
      </div>

      <Dialog
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) {
            setInstallError(null);
          }
        }}
      >
        <DialogContent className="w-[calc(100vw-2rem)] sm:w-[500px] sm:max-w-[500px] max-h-[80vh] p-4 sm:p-6 overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <Download className="size-6" />
              <span>{t('plugins.installPlugin')}</span>
            </DialogTitle>
          </DialogHeader>

          {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
            <div className="mt-4">
              <p className="mb-2">
                {installInfo.plugin_version
                  ? t('plugins.askConfirm', {
                      name: installInfo.plugin_name,
                      version: installInfo.plugin_version,
                    })
                  : t('plugins.askConfirmNoVersion', {
                      name: installInfo.plugin_name,
                    })}
              </p>
            </div>
          )}

          {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installing')}</p>
            </div>
          )}

          {pluginInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installFailed')}</p>
              <p className="mb-2 text-red-500">{installError}</p>
            </div>
          )}

          <DialogFooter>
            {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  {t('common.cancel')}
                </Button>
                <Button onClick={handleModalConfirm}>
                  {t('common.confirm')}
                </Button>
              </>
            )}
            {pluginInstallStatus === PluginInstallStatus.ERROR && (
              <Button variant="default" onClick={() => setModalOpen(false)}>
                {t('common.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Skill Upload Progress Dialog */}
      <Dialog
        open={skillUploadState !== 'idle'}
        onOpenChange={(open) => {
          if (!open && skillUploadState !== 'uploading') {
            setSkillUploadState('idle');
            setSkillUploadError(null);
          }
        }}
      >
        <DialogContent
          className="sm:max-w-lg w-[90vw] max-h-[80vh] p-4 sm:p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto overflow-x-hidden"
          hideCloseButton={skillUploadState === 'uploading'}
        >
          <DialogHeader>
            <DialogTitle className="flex items-start gap-3">
              <Download className="size-5 shrink-0 mt-0.5" />
              <span className="break-words">
                {t('plugins.installProgress.title', {
                  name: skillUploadFileName,
                })}
              </span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Overall progress bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    'text-sm font-medium shrink-0',
                    skillUploadState === 'done'
                      ? 'text-green-700 dark:text-green-300'
                      : skillUploadState === 'error'
                        ? 'text-red-700 dark:text-red-300'
                        : 'text-blue-700 dark:text-blue-300',
                  )}
                >
                  {skillUploadState === 'done'
                    ? t('plugins.installProgress.completed')
                    : skillUploadState === 'error'
                      ? t('plugins.installProgress.failed')
                      : t('plugins.installProgress.overallProgress')}
                </span>
                <span
                  className={cn(
                    'text-sm font-medium',
                    skillUploadState === 'done'
                      ? 'text-green-600 dark:text-green-400'
                      : skillUploadState === 'error'
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-blue-600 dark:text-blue-400',
                  )}
                >
                  {skillUploadState === 'done'
                    ? '100%'
                    : skillUploadState === 'error'
                      ? '0%'
                      : '50%'}
                </span>
              </div>
              <Progress
                value={
                  skillUploadState === 'done'
                    ? 100
                    : skillUploadState === 'error'
                      ? 0
                      : 50
                }
                className={cn(
                  'h-2.5',
                  '[&>div]:bg-blue-500 dark:[&>div]:bg-blue-400',
                  'bg-blue-100 dark:bg-blue-900/30',
                  skillUploadState === 'done' &&
                    '[&>div]:bg-green-500 dark:[&>div]:bg-green-400 bg-green-100 dark:bg-green-900/30',
                  skillUploadState === 'error' &&
                    '[&>div]:bg-red-500 dark:[&>div]:bg-red-400 bg-red-100 dark:bg-red-900/30',
                )}
              />
            </div>

            {/* Stage display */}
            <div className="space-y-1.5">
              {skillUploadState === 'uploading' && (
                <div className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-2 sm:py-2.5 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800">
                  <div className="flex items-center justify-center w-7 h-7 rounded-full shrink-0 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-blue-700 dark:text-blue-300">
                      {t('plugins.installProgress.downloading')}
                    </span>
                  </div>
                </div>
              )}

              {skillUploadState === 'done' && (
                <div className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-2 sm:py-2.5 rounded-lg bg-green-50/50 dark:bg-green-950/15 border border-green-100 dark:border-green-900/50">
                  <div className="flex items-center justify-center w-7 h-7 rounded-full shrink-0 bg-green-100 dark:bg-green-900/40 text-green-600 dark:text-green-400">
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-green-600 dark:text-green-400">
                      {t('plugins.installProgress.downloading')}
                    </span>
                  </div>
                </div>
              )}

              {skillUploadState === 'error' && (
                <div className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-2 sm:py-2.5 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
                  <div className="flex items-center justify-center w-7 h-7 rounded-full shrink-0 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">
                    <XCircle className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-red-600 dark:text-red-400">
                      {t('plugins.installProgress.downloading')}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Done banner */}
            {skillUploadState === 'done' && (
              <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-900">
                <CheckCircle2 className="w-5 h-5 shrink-0 text-green-600 dark:text-green-400" />
                <span className="text-sm text-green-700 dark:text-green-300 font-medium break-words">
                  {t('plugins.installProgress.installComplete')}
                </span>
              </div>
            )}

            {/* Error detail */}
            {skillUploadState === 'error' && skillUploadError && (
              <div className="px-3 py-2 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900">
                <p className="text-xs text-red-600 dark:text-red-400 break-all line-clamp-4">
                  {skillUploadError}
                </p>
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 mt-2">
            <Button
              variant="default"
              size="sm"
              onClick={() => {
                if (
                  skillUploadState === 'done' ||
                  skillUploadState === 'error'
                ) {
                  setSkillUploadState('idle');
                  setSkillUploadError(null);
                }
              }}
              disabled={skillUploadState === 'uploading'}
            >
              {skillUploadState === 'done' || skillUploadState === 'error'
                ? t('common.close')
                : t('plugins.installProgress.background')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
