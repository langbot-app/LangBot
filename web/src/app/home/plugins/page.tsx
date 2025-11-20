'use client';
import PluginInstalledComponent, {
  PluginInstalledComponentRef,
} from '@/app/home/plugins/components/plugin-installed/PluginInstalledComponent';
import MarketPage from '@/app/home/plugins/components/plugin-market/PluginMarketComponent';
import MCPServerComponent from '@/app/home/plugins/mcp-server/MCPServerComponent';
import MCPFormDialog from '@/app/home/plugins/mcp-server/mcp-form/MCPFormDialog';
import MCPDeleteConfirmDialog from '@/app/home/plugins/mcp-server/mcp-form/MCPDeleteConfirmDialog';
import styles from './plugins.module.css';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import {
  PlusIcon,
  ChevronDownIcon,
  UploadIcon,
  StoreIcon,
  Download,
  Power,
  Github,
  ChevronLeft,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { ApiRespPluginSystemStatus } from '@/app/infra/entities/api';

enum PluginInstallStatus {
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
}

interface GithubAsset {
  id: number;
  name: string;
  size: number;
  download_url: string;
  content_type: string;
}

export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('installed');
  const [modalOpen, setModalOpen] = useState(false);
  const [installSource, setInstallSource] = useState<string>('local');
  const [installInfo, setInstallInfo] = useState<Record<string, any>>({}); // eslint-disable-line @typescript-eslint/no-explicit-any
  const [mcpSSEModalOpen, setMcpSSEModalOpen] = useState(false);
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const [installError, setInstallError] = useState<string | null>(null);
  const [githubURL, setGithubURL] = useState('');
  const [githubReleases, setGithubReleases] = useState<GithubRelease[]>([]);
  const [selectedRelease, setSelectedRelease] = useState<GithubRelease | null>(
    null,
  );
  const [githubAssets, setGithubAssets] = useState<GithubAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<GithubAsset | null>(null);
  const [githubOwner, setGithubOwner] = useState('');
  const [githubRepo, setGithubRepo] = useState('');
  const [fetchingReleases, setFetchingReleases] = useState(false);
  const [fetchingAssets, setFetchingAssets] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [editingServerName, setEditingServerName] = useState<string | null>(
    null,
  );
  const [isEditMode, setIsEditMode] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const fetchPluginSystemStatus = async () => {
      try {
        setStatusLoading(true);
        const status = await httpClient.getPluginSystemStatus();
        setPluginSystemStatus(status);
      } catch (error) {
        console.error('Failed to fetch plugin system status:', error);
        toast.error(t('plugins.failedToGetStatus'));
      } finally {
        setStatusLoading(false);
      }
    };

    fetchPluginSystemStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  function watchTask(taskId: number) {
    let alreadySuccess = false;

    const interval = setInterval(() => {
      httpClient.getAsyncTask(taskId).then((resp) => {
        if (resp.runtime.done) {
          clearInterval(interval);
          if (resp.runtime.exception) {
            setInstallError(resp.runtime.exception);
            setPluginInstallStatus(PluginInstallStatus.ERROR);
          } else {
            if (!alreadySuccess) {
              toast.success(t('plugins.installSuccess'));
              alreadySuccess = true;
            }
            resetGithubState();
            setModalOpen(false);
            pluginInstalledRef.current?.refreshPluginList();
          }
        }
      });
    }, 1000);
  }

  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);

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
  }

  async function fetchGithubReleases() {
    if (!githubURL.trim()) {
      toast.error(t('plugins.enterRepoUrl'));
      return;
    }

    setFetchingReleases(true);
    setInstallError(null);

    try {
      const result = await httpClient.getGithubReleases(githubURL);
      setGithubReleases(result.releases);
      setGithubOwner(result.owner);
      setGithubRepo(result.repo);

      if (result.releases.length === 0) {
        toast.warning(t('plugins.noReleasesFound'));
      } else {
        setPluginInstallStatus(PluginInstallStatus.SELECT_RELEASE);
      }
    } catch (error: unknown) {
      console.error('Failed to fetch GitHub releases:', error);
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setInstallError(errorMessage || t('plugins.fetchReleasesError'));
      setPluginInstallStatus(PluginInstallStatus.ERROR);
    } finally {
      setFetchingReleases(false);
    }
  }

  async function handleReleaseSelect(release: GithubRelease) {
    setSelectedRelease(release);
    setFetchingAssets(true);
    setInstallError(null);

    try {
      const result = await httpClient.getGithubReleaseAssets(
        githubOwner,
        githubRepo,
        release.id,
      );
      setGithubAssets(result.assets);

      if (result.assets.length === 0) {
        toast.warning(t('plugins.noAssetsFound'));
      } else {
        setPluginInstallStatus(PluginInstallStatus.SELECT_ASSET);
      }
    } catch (error: unknown) {
      console.error('Failed to fetch GitHub release assets:', error);
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setInstallError(errorMessage || t('plugins.fetchAssetsError'));
      setPluginInstallStatus(PluginInstallStatus.ERROR);
    } finally {
      setFetchingAssets(false);
    }
  }

  function handleAssetSelect(asset: GithubAsset) {
    setSelectedAsset(asset);
    setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
  }

  function handleModalConfirm() {
    if (installSource === 'github' && selectedAsset && selectedRelease) {
      installPlugin('github', {
        asset_url: selectedAsset.download_url,
        owner: githubOwner,
        repo: githubRepo,
        release_tag: selectedRelease.tag_name,
      });
    } else {
      installPlugin(installSource, installInfo as Record<string, any>); // eslint-disable-line @typescript-eslint/no-explicit-any
    }
  }

  function installPlugin(
    installSource: string,
    installInfo: Record<string, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
  ) {
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
    if (installSource === 'github') {
      httpClient
        .installPluginFromGithub(
          installInfo.asset_url,
          installInfo.owner,
          installInfo.repo,
          installInfo.release_tag,
        )
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        })
        .catch((err) => {
          console.log('error when install plugin:', err);
          setInstallError(err.message);
          setPluginInstallStatus(PluginInstallStatus.ERROR);
        });
    } else if (installSource === 'local') {
      httpClient
        .installPluginFromLocal(installInfo.file)
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        })
        .catch((err) => {
          console.log('error when install plugin:', err);
          setInstallError(err.message);
          setPluginInstallStatus(PluginInstallStatus.ERROR);
        });
    } else if (installSource === 'marketplace') {
      httpClient
        .installPluginFromMarketplace(
          installInfo.plugin_author,
          installInfo.plugin_name,
          installInfo.plugin_version,
        )
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        });
    }
  }

  const validateFileType = (file: File): boolean => {
    const allowedExtensions = ['.lbpkg', '.zip'];
    const fileName = file.name.toLowerCase();
    return allowedExtensions.some((ext) => fileName.endsWith(ext));
  };

  const uploadPluginFile = useCallback(
    async (file: File) => {
      if (!pluginSystemStatus?.is_enable || !pluginSystemStatus?.is_connected) {
        toast.error(t('plugins.pluginSystemNotReady'));
        return;
      }

      if (!validateFileType(file)) {
        toast.error(t('plugins.unsupportedFileType'));
        return;
      }

      setModalOpen(true);
      setPluginInstallStatus(PluginInstallStatus.INSTALLING);
      setInstallError(null);
      installPlugin('local', { file });
    },
    [t, pluginSystemStatus, installPlugin],
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
        uploadPluginFile(file);
      }

      event.target.value = '';
    },
    [uploadPluginFile],
  );

  const isPluginSystemReady =
    pluginSystemStatus?.is_enable && pluginSystemStatus?.is_connected;

  const handleDragOver = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (isPluginSystemReady) {
        setIsDragOver(true);
      }
    },
    [isPluginSystemReady],
  );

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDragOver(false);

      if (!isPluginSystemReady) {
        toast.error(t('plugins.pluginSystemNotReady'));
        return;
      }

      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        uploadPluginFile(files[0]);
      }
    },
    [uploadPluginFile, isPluginSystemReady, t],
  );

  const renderPluginDisabledState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]">
      <Power className="w-16 h-16 text-gray-400 mb-4" />
      <h2 className="text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {t('plugins.systemDisabled')}
      </h2>
      <p className="text-gray-500 dark:text-gray-400 max-w-md">
        {t('plugins.systemDisabledDesc')}
      </p>
    </div>
  );

  const renderPluginConnectionErrorState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width="72"
        height="72"
        fill="#BDBDBD"
      >
        <path d="M17.657 14.8284L16.2428 13.4142L17.657 12C19.2191 10.4379 19.2191 7.90526 17.657 6.34316C16.0949 4.78106 13.5622 4.78106 12.0001 6.34316L10.5859 7.75737L9.17171 6.34316L10.5859 4.92895C12.9291 2.5858 16.7281 2.5858 19.0712 4.92895C21.4143 7.27209 21.4143 11.0711 19.0712 13.4142L17.657 14.8284ZM14.8286 17.6569L13.4143 19.0711C11.0712 21.4142 7.27221 21.4142 4.92907 19.0711C2.58592 16.7279 2.58592 12.9289 4.92907 10.5858L6.34328 9.17159L7.75749 10.5858L6.34328 12C4.78118 13.5621 4.78118 16.0948 6.34328 17.6569C7.90538 19.219 10.438 19.219 12.0001 17.6569L13.4143 16.2427L14.8286 17.6569ZM14.8286 7.75737L16.2428 9.17159L9.17171 16.2427L7.75749 14.8284L14.8286 7.75737ZM5.77539 2.29291L7.70724 1.77527L8.74252 5.63897L6.81067 6.15661L5.77539 2.29291ZM15.2578 18.3611L17.1896 17.8434L18.2249 21.7071L16.293 22.2248L15.2578 18.3611ZM2.29303 5.77527L6.15673 6.81054L5.63909 8.7424L1.77539 7.70712L2.29303 5.77527ZM18.3612 15.2576L22.2249 16.2929L21.7072 18.2248L17.8435 17.1895L18.3612 15.2576Z"></path>
      </svg>

      <h2 className="text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {t('plugins.connectionError')}
      </h2>
      <p className="text-gray-500 dark:text-gray-400 max-w-md mb-4">
        {t('plugins.connectionErrorDesc')}
      </p>
    </div>
  );

  const renderLoadingState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] pt-[10vh]">
      <p className="text-gray-500 dark:text-gray-400">
        {t('plugins.loadingStatus')}
      </p>
    </div>
  );

  if (statusLoading) {
    return renderLoadingState();
  }

  if (!pluginSystemStatus?.is_enable) {
    return renderPluginDisabledState();
  }

  if (!pluginSystemStatus?.is_connected) {
    return renderPluginConnectionErrorState();
  }

  return (
    <div
      className={`${styles.pageContainer} h-full flex flex-col ${isDragOver ? 'bg-blue-50' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".lbpkg,.zip"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="w-full h-full flex flex-col"
      >
        <div className="flex flex-row justify-between items-center px-[0.8rem] flex-shrink-0">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0] dark:bg-[#2a2a2e]">
            <TabsTrigger value="installed" className="px-6 py-4 cursor-pointer">
              {t('plugins.installed')}
            </TabsTrigger>
            {systemInfo.enable_marketplace && (
              <TabsTrigger value="market" className="px-6 py-4 cursor-pointer">
                {t('plugins.marketplace')}
              </TabsTrigger>
            )}
            <TabsTrigger
              value="mcp-servers"
              className="px-6 py-4 cursor-pointer"
            >
              {t('mcp.title')}
            </TabsTrigger>
          </TabsList>

          <div className="flex flex-row justify-end items-center">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="default" className="px-6 py-4 cursor-pointer">
                  <PlusIcon className="w-4 h-4" />
                  {activeTab === 'mcp-servers'
                    ? t('mcp.add')
                    : t('plugins.install')}
                  <ChevronDownIcon className="ml-2 w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {activeTab === 'mcp-servers' ? (
                  <>
                    <DropdownMenuItem
                      onClick={() => {
                        setActiveTab('mcp-servers');
                        setIsEditMode(false);
                        setEditingServerName(null);
                        setMcpSSEModalOpen(true);
                      }}
                    >
                      <PlusIcon className="w-4 h-4" />
                      {t('mcp.createServer')}
                    </DropdownMenuItem>
                  </>
                ) : (
                  <>
                    {systemInfo.enable_marketplace && (
                      <DropdownMenuItem
                        onClick={() => {
                          setActiveTab('market');
                        }}
                      >
                        <StoreIcon className="w-4 h-4" />
                        {t('plugins.marketplace')}
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={handleFileSelect}>
                      <UploadIcon className="w-4 h-4" />
                      {t('plugins.uploadLocal')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        setInstallSource('github');
                        setPluginInstallStatus(PluginInstallStatus.WAIT_INPUT);
                        setInstallError(null);
                        resetGithubState();
                        setModalOpen(true);
                      }}
                    >
                      <Github className="w-4 h-4" />
                      {t('plugins.installFromGithub')}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <TabsContent value="installed" className="flex-1 overflow-y-auto mt-0">
          <PluginInstalledComponent ref={pluginInstalledRef} />
        </TabsContent>
        <TabsContent value="market" className="flex-1 overflow-y-auto mt-0">
          <MarketPage
            installPlugin={(plugin: PluginV4) => {
              setInstallSource('marketplace');
              setInstallInfo({
                plugin_author: plugin.author,
                plugin_name: plugin.name,
                plugin_version: plugin.latest_version,
              });
              setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
              setModalOpen(true);
            }}
          />
        </TabsContent>
        <TabsContent
          value="mcp-servers"
          className="flex-1 overflow-y-auto mt-0"
        >
          <MCPServerComponent
            key={refreshKey}
            onEditServer={(serverName) => {
              setEditingServerName(serverName);
              setIsEditMode(true);
              setMcpSSEModalOpen(true);
            }}
          />
        </TabsContent>
      </Tabs>

      <Dialog
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) {
            resetGithubState();
            setInstallError(null);
          }
        }}
      >
        <DialogContent className="w-[500px] max-h-[80vh] p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              {installSource === 'github' ? (
                <Github className="size-6" />
              ) : (
                <Download className="size-6" />
              )}
              <span>{t('plugins.installPlugin')}</span>
            </DialogTitle>
          </DialogHeader>

          {/* GitHub Install Flow */}
          {installSource === 'github' &&
            pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
              <div className="mt-4">
                <p className="mb-2">{t('plugins.enterRepoUrl')}</p>
                <Input
                  placeholder={t('plugins.repoUrlPlaceholder')}
                  value={githubURL}
                  onChange={(e) => setGithubURL(e.target.value)}
                  className="mb-4"
                />
                {fetchingReleases && (
                  <p className="text-sm text-gray-500">
                    {t('plugins.fetchingReleases')}
                  </p>
                )}
              </div>
            )}

          {installSource === 'github' &&
            pluginInstallStatus === PluginInstallStatus.SELECT_RELEASE && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-4">
                  <p className="font-medium">{t('plugins.selectRelease')}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setPluginInstallStatus(PluginInstallStatus.WAIT_INPUT);
                      setGithubReleases([]);
                    }}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    {t('plugins.backToRepoUrl')}
                  </Button>
                </div>
                <div className="max-h-[400px] overflow-y-auto space-y-2 pb-2">
                  {githubReleases.map((release) => (
                    <Card
                      key={release.id}
                      className="cursor-pointer hover:shadow-sm transition-shadow duration-200 shadow-none py-4"
                      onClick={() => handleReleaseSelect(release)}
                    >
                      <CardHeader className="flex flex-row items-start justify-between px-3 space-y-0">
                        <div className="flex-1">
                          <CardTitle className="text-sm">
                            {release.name || release.tag_name}
                          </CardTitle>
                          <CardDescription className="text-xs mt-1">
                            {t('plugins.releaseTag', { tag: release.tag_name })}{' '}
                            •{' '}
                            {t('plugins.publishedAt', {
                              date: new Date(
                                release.published_at,
                              ).toLocaleDateString(),
                            })}
                          </CardDescription>
                        </div>
                        {release.prerelease && (
                          <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded ml-2 shrink-0">
                            {t('plugins.prerelease')}
                          </span>
                        )}
                      </CardHeader>
                    </Card>
                  ))}
                </div>
                {fetchingAssets && (
                  <p className="text-sm text-gray-500 mt-4">
                    {t('plugins.loading')}
                  </p>
                )}
              </div>
            )}

          {installSource === 'github' &&
            pluginInstallStatus === PluginInstallStatus.SELECT_ASSET && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-4">
                  <p className="font-medium">{t('plugins.selectAsset')}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setPluginInstallStatus(
                        PluginInstallStatus.SELECT_RELEASE,
                      );
                      setGithubAssets([]);
                      setSelectedAsset(null);
                    }}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    {t('plugins.backToReleases')}
                  </Button>
                </div>
                {selectedRelease && (
                  <div className="mb-4 p-2 bg-gray-50 dark:bg-gray-900 rounded">
                    <div className="text-sm font-medium">
                      {selectedRelease.name || selectedRelease.tag_name}
                    </div>
                    <div className="text-xs text-gray-500">
                      {selectedRelease.tag_name}
                    </div>
                  </div>
                )}
                <div className="max-h-[400px] overflow-y-auto space-y-2 pb-2">
                  {githubAssets.map((asset) => (
                    <Card
                      key={asset.id}
                      className="cursor-pointer hover:shadow-sm transition-shadow duration-200 shadow-none py-3"
                      onClick={() => handleAssetSelect(asset)}
                    >
                      <CardHeader className="px-3">
                        <CardTitle className="text-sm">{asset.name}</CardTitle>
                        <CardDescription className="text-xs">
                          {t('plugins.assetSize', {
                            size: formatFileSize(asset.size),
                          })}
                        </CardDescription>
                      </CardHeader>
                    </Card>
                  ))}
                </div>
              </div>
            )}

          {/* Marketplace Install Confirm */}
          {installSource === 'marketplace' &&
            pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
              <div className="mt-4">
                <p className="mb-2">
                  {t('plugins.askConfirm', {
                    name: installInfo.plugin_name,
                    version: installInfo.plugin_version,
                  })}
                </p>
              </div>
            )}

          {/* GitHub Install Confirm */}
          {installSource === 'github' &&
            pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-4">
                  <p className="font-medium">{t('plugins.confirmInstall')}</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setPluginInstallStatus(PluginInstallStatus.SELECT_ASSET);
                      setSelectedAsset(null);
                    }}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    {t('plugins.backToAssets')}
                  </Button>
                </div>
                {selectedRelease && selectedAsset && (
                  <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded space-y-2">
                    <div>
                      <span className="text-sm font-medium">Repository: </span>
                      <span className="text-sm">
                        {githubOwner}/{githubRepo}
                      </span>
                    </div>
                    <div>
                      <span className="text-sm font-medium">Release: </span>
                      <span className="text-sm">
                        {selectedRelease.tag_name}
                      </span>
                    </div>
                    <div>
                      <span className="text-sm font-medium">File: </span>
                      <span className="text-sm">{selectedAsset.name}</span>
                    </div>
                  </div>
                )}
              </div>
            )}

          {/* Installing State */}
          {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installing')}</p>
            </div>
          )}

          {/* Error State */}
          {pluginInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installFailed')}</p>
              <p className="mb-2 text-red-500">{installError}</p>
            </div>
          )}

          <DialogFooter>
            {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT &&
              installSource === 'github' && (
                <>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setModalOpen(false);
                      resetGithubState();
                    }}
                  >
                    {t('common.cancel')}
                  </Button>
                  <Button
                    onClick={fetchGithubReleases}
                    disabled={!githubURL.trim() || fetchingReleases}
                  >
                    {fetchingReleases
                      ? t('plugins.loading')
                      : t('common.confirm')}
                  </Button>
                </>
              )}
            {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  {t('common.cancel')}
                </Button>
                <Button onClick={() => handleModalConfirm()}>
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

      {isDragOver && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-50 flex items-center justify-center z-50 pointer-events-none">
          <div className="bg-white rounded-lg p-8 shadow-lg border-2 border-dashed border-gray-500">
            <div className="text-center">
              <UploadIcon className="mx-auto h-12 w-12 text-gray-500 mb-4" />
              <p className="text-lg font-medium text-gray-700">
                {t('plugins.dragToUpload')}
              </p>
            </div>
          </div>
        </div>
      )}

      <MCPFormDialog
        open={mcpSSEModalOpen}
        onOpenChange={setMcpSSEModalOpen}
        serverName={editingServerName}
        isEditMode={isEditMode}
        onSuccess={() => {
          setEditingServerName(null);
          setIsEditMode(false);
          setRefreshKey((prev) => prev + 1);
        }}
        onDelete={() => {
          setShowDeleteConfirmModal(true);
        }}
      />

      <MCPDeleteConfirmDialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
        serverName={editingServerName}
        onSuccess={() => {
          setMcpSSEModalOpen(false);
          setEditingServerName(null);
          setIsEditMode(false);
          setRefreshKey((prev) => prev + 1);
        }}
      />
    </div>
  );
}
