import { useEffect, useState, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Github, Upload as UploadIcon, ChevronLeft } from 'lucide-react';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { usePluginInstallTasks } from '@/app/home/plugins/components/plugin-install-task';

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

export default function AddPluginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const actionParam = searchParams.get('action');

  const { refreshPlugins } = useSidebarData();
  const {
    addTask,
    setSelectedTaskId,
    registerOnTaskComplete,
    unregisterOnTaskComplete,
  } = usePluginInstallTasks();

  const [githubURL, setGithubURL] = useState('');
  const [githubReleases, setGithubReleases] = useState<GithubRelease[]>([]);
  const [selectedRelease, setSelectedRelease] = useState<GithubRelease | null>(null);
  const [githubAssets, setGithubAssets] = useState<GithubAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<GithubAsset | null>(null);
  const [githubOwner, setGithubOwner] = useState('');
  const [githubRepo, setGithubRepo] = useState('');
  const [fetchingReleases, setFetchingReleases] = useState(false);
  const [fetchingAssets, setFetchingAssets] = useState(false);
  const [installError, setInstallError] = useState<string | null>(null);
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isGithubMode = actionParam === 'github';
  const isUploadMode = actionParam === 'upload';

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
        release.tag_name,
        release.source_type,
        release.archive_url,
      );
      setGithubAssets(result.assets);

      if (result.assets.length === 0) {
        toast.warning(t('plugins.noAssetsFound'));
      } else {
        setPluginInstallStatus(PluginInstallStatus.SELECT_ASSET);
      }
    } catch (error: unknown) {
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

  function handleGithubConfirm() {
    if (!selectedAsset || !selectedRelease) return;
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
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
        toast.success(t('plugins.installSuccess'));
        navigate('/home/add-extension');
      })
      .catch((err) => {
        setInstallError(err.msg);
        setPluginInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  // Local file upload
  const validateFileType = (file: File): boolean => {
    const allowedExtensions = ['.lbpkg'];
    const fileName = file.name.toLowerCase();
    return allowedExtensions.some((ext) => fileName.endsWith(ext));
  };

  const uploadPluginFile = async (file: File) => {
    if (!validateFileType(file)) {
      toast.error(t('plugins.unsupportedFileType'));
      return;
    }

    if (!(await checkExtensionsLimit())) return;

    const fileName = file.name || 'local plugin';
    const fileSize = file.size;
    setInstallError(null);

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
          fileSize: fileSize,
        });
        setSelectedTaskId(taskKey);
        toast.success(t('plugins.installSuccess'));
        navigate('/home/add-extension');
      })
      .catch((err) => {
        toast.error(t('plugins.installFailed') + (err.msg || ''));
      });
  };

  const handleFileSelect = async () => {
    if (!(await checkExtensionsLimit())) return;
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      uploadPluginFile(file);
    }
    event.target.value = '';
  };

  function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }

  function handleCancel() {
    navigate('/home/add-extension');
  }

  // GitHub Install View
  if (isGithubMode) {
    return (
      <div className="h-full flex flex-col">
        <input
          ref={fileInputRef}
          type="file"
          accept=".lbpkg"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />

        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('plugins.installFromGithub')}</h1>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Github className="size-5" />
                  {t('plugins.installFromGithub')}
                </CardTitle>
                <CardDescription>
                  {t('plugins.installFromGithubDesc')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
                  <div>
                    <p className="mb-2 text-sm">{t('plugins.enterRepoUrl')}</p>
                    <div className="flex gap-2">
                      <Input
                        placeholder={t('plugins.repoUrlPlaceholder')}
                        value={githubURL}
                        onChange={(e) => setGithubURL(e.target.value)}
                      />
                      <Button
                        onClick={fetchGithubReleases}
                        disabled={!githubURL.trim() || fetchingReleases}
                      >
                        {fetchingReleases
                          ? t('plugins.loading')
                          : t('common.confirm')}
                      </Button>
                    </div>
                  </div>
                )}

                {pluginInstallStatus === PluginInstallStatus.SELECT_RELEASE && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <p className="font-medium text-sm">
                        {t('plugins.selectRelease')}
                      </p>
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
                                {t('plugins.releaseTag', {
                                  tag: release.tag_name,
                                })}{' '}
                                &bull;{' '}
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
                      <p className="text-sm text-muted-foreground mt-4">
                        {t('plugins.loading')}
                      </p>
                    )}
                  </div>
                )}

                {pluginInstallStatus === PluginInstallStatus.SELECT_ASSET && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <p className="font-medium text-sm">
                        {t('plugins.selectAsset')}
                      </p>
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
                      <div className="mb-3 p-2 bg-muted rounded">
                        <div className="text-sm font-medium">
                          {selectedRelease.name || selectedRelease.tag_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
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
                            <CardTitle className="text-sm">
                              {asset.name}
                            </CardTitle>
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

                {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <p className="font-medium text-sm">
                        {t('plugins.confirmInstall')}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setPluginInstallStatus(
                            PluginInstallStatus.SELECT_ASSET,
                          );
                          setSelectedAsset(null);
                        }}
                      >
                        <ChevronLeft className="w-4 h-4 mr-1" />
                        {t('plugins.backToAssets')}
                      </Button>
                    </div>
                    {selectedRelease && selectedAsset && (
                      <div className="p-3 bg-muted rounded space-y-2">
                        <div>
                          <span className="text-sm font-medium">
                            Repository:{' '}
                          </span>
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
                    <div className="flex justify-end mt-4">
                      <Button onClick={handleGithubConfirm}>
                        {t('common.confirm')}
                      </Button>
                    </div>
                  </div>
                )}

                {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
                  <div>
                    <p className="text-sm">{t('plugins.installing')}</p>
                  </div>
                )}

                {pluginInstallStatus === PluginInstallStatus.ERROR && (
                  <div>
                    <p className="text-sm mb-1">{t('plugins.installFailed')}</p>
                    <p className="text-sm text-destructive">{installError}</p>
                    <div className="flex justify-end mt-4">
                      <Button variant="default" onClick={handleCancel}>
                        {t('common.close')}
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  // Upload Mode - show file select dialog
  if (isUploadMode) {
    return (
      <div className="h-full flex flex-col">
        <input
          ref={fileInputRef}
          type="file"
          accept=".lbpkg"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />

        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('plugins.uploadLocal')}</h1>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <UploadIcon className="size-5" />
                  {t('plugins.uploadLocal')}
                </CardTitle>
                <CardDescription>
                  {t('plugins.uploadPluginOnly')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div
                  className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500 transition-colors"
                  onClick={handleFileSelect}
                >
                  <UploadIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                  <p className="text-gray-600 dark:text-gray-300">
                    {t('plugins.dragToUpload')}
                  </p>
                  <p className="text-sm text-gray-500 mt-2">
                    {t('plugins.selectFileToUpload')}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  // Default: redirect to add-extension
  navigate('/home/add-extension');
  return null;
}