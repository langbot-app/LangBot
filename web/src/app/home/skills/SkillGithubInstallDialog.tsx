'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Github, ChevronLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { httpClient } from '@/app/infra/http/HttpClient';

enum InstallStatus {
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

interface SkillGithubInstallDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

export default function SkillGithubInstallDialog({
  open,
  onOpenChange,
  onSuccess,
}: SkillGithubInstallDialogProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<InstallStatus>(InstallStatus.WAIT_INPUT);
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

  function resetState() {
    setStatus(InstallStatus.WAIT_INPUT);
    setInstallError(null);
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

  function handleOpenChange(nextOpen: boolean) {
    onOpenChange(nextOpen);
    if (!nextOpen) {
      resetState();
    }
  }

  async function fetchReleases() {
    if (!githubURL.trim()) return;
    setFetchingReleases(true);
    setInstallError(null);

    try {
      const result = await httpClient.getGithubReleases(githubURL);
      setGithubReleases(result.releases);
      setGithubOwner(result.owner);
      setGithubRepo(result.repo);

      if (result.releases.length === 0) {
        toast.warning(t('skills.noReleasesFound'));
      } else {
        setStatus(InstallStatus.SELECT_RELEASE);
      }
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setInstallError(errorMessage || t('skills.fetchReleasesError'));
      setStatus(InstallStatus.ERROR);
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
        toast.warning(t('skills.noAssetsFound'));
      } else {
        setStatus(InstallStatus.SELECT_ASSET);
      }
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setInstallError(errorMessage || t('skills.fetchAssetsError'));
      setStatus(InstallStatus.ERROR);
    } finally {
      setFetchingAssets(false);
    }
  }

  function handleAssetSelect(asset: GithubAsset) {
    setSelectedAsset(asset);
    setStatus(InstallStatus.ASK_CONFIRM);
  }

  async function handleConfirmInstall() {
    if (!selectedAsset || !selectedRelease) return;

    setStatus(InstallStatus.INSTALLING);
    try {
      await httpClient.installSkillFromGithub(
        selectedAsset.download_url,
        githubOwner,
        githubRepo,
        selectedRelease.tag_name,
      );
      toast.success(t('skills.installSuccess'));
      handleOpenChange(false);
      onSuccess();
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setInstallError(errorMessage);
      setStatus(InstallStatus.ERROR);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="w-[500px] max-h-[80vh] p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-4">
            <Github className="size-6" />
            <span>{t('skills.importFromGithub')}</span>
          </DialogTitle>
        </DialogHeader>

        {/* Step 1: Enter URL */}
        {status === InstallStatus.WAIT_INPUT && (
          <div className="mt-4">
            <p className="mb-2">{t('skills.enterRepoUrl')}</p>
            <Input
              placeholder={t('skills.repoUrlPlaceholder')}
              value={githubURL}
              onChange={(e) => setGithubURL(e.target.value)}
              className="mb-4"
            />
            {fetchingReleases && (
              <p className="text-sm text-gray-500">
                {t('skills.fetchingReleases')}
              </p>
            )}
          </div>
        )}

        {/* Step 2: Select Release */}
        {status === InstallStatus.SELECT_RELEASE && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-4">
              <p className="font-medium">{t('skills.selectRelease')}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatus(InstallStatus.WAIT_INPUT);
                  setGithubReleases([]);
                }}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                {t('skills.backToRepoUrl')}
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
                        {t('skills.releaseTag', { tag: release.tag_name })} •{' '}
                        {t('skills.publishedAt', {
                          date: new Date(
                            release.published_at,
                          ).toLocaleDateString(),
                        })}
                      </CardDescription>
                    </div>
                    {release.prerelease && (
                      <span className="text-xs bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 px-2 py-0.5 rounded ml-2 shrink-0">
                        {t('skills.prerelease')}
                      </span>
                    )}
                  </CardHeader>
                </Card>
              ))}
            </div>
            {fetchingAssets && (
              <p className="text-sm text-gray-500 mt-4">
                {t('skills.loading')}
              </p>
            )}
          </div>
        )}

        {/* Step 3: Select Asset */}
        {status === InstallStatus.SELECT_ASSET && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-4">
              <p className="font-medium">{t('skills.selectAsset')}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatus(InstallStatus.SELECT_RELEASE);
                  setGithubAssets([]);
                  setSelectedAsset(null);
                }}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                {t('skills.backToReleases')}
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
                      {t('skills.assetSize', {
                        size: formatFileSize(asset.size),
                      })}
                    </CardDescription>
                  </CardHeader>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: Confirm */}
        {status === InstallStatus.ASK_CONFIRM && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-4">
              <p className="font-medium">{t('skills.confirmInstall')}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setStatus(InstallStatus.SELECT_ASSET);
                  setSelectedAsset(null);
                }}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                {t('skills.backToAssets')}
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
                  <span className="text-sm">{selectedRelease.tag_name}</span>
                </div>
                <div>
                  <span className="text-sm font-medium">File: </span>
                  <span className="text-sm">{selectedAsset.name}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Installing */}
        {status === InstallStatus.INSTALLING && (
          <div className="mt-4">
            <p className="mb-2">{t('skills.installing')}</p>
          </div>
        )}

        {/* Error */}
        {status === InstallStatus.ERROR && (
          <div className="mt-4">
            <p className="mb-2">{t('skills.installError')}</p>
            <p className="mb-2 text-red-500">{installError}</p>
          </div>
        )}

        <DialogFooter>
          {status === InstallStatus.WAIT_INPUT && (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button
                onClick={fetchReleases}
                disabled={!githubURL.trim() || fetchingReleases}
              >
                {fetchingReleases ? t('skills.loading') : t('common.confirm')}
              </Button>
            </>
          )}
          {status === InstallStatus.ASK_CONFIRM && (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                {t('common.cancel')}
              </Button>
              <Button onClick={handleConfirmInstall}>
                {t('common.confirm')}
              </Button>
            </>
          )}
          {status === InstallStatus.ERROR && (
            <Button variant="default" onClick={() => handleOpenChange(false)}>
              {t('common.close')}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
