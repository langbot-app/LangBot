'use client';

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { ChevronLeft, Github, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { Skill } from '@/app/infra/entities/api';

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

interface PreviewSkill extends Skill {
  source_path?: string;
  entry_file?: string;
}

interface SkillGithubImportPanelProps {
  onImported: (skillNames: string[]) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function previewPath(skill: PreviewSkill): string {
  return skill.source_path || '';
}

export default function SkillGithubImportPanel({
  onImported,
}: SkillGithubImportPanelProps) {
  const { t } = useTranslation();

  const [githubURL, setGithubURL] = useState('');
  const [githubOwner, setGithubOwner] = useState('');
  const [githubRepo, setGithubRepo] = useState('');
  const [githubSourceSubdir, setGithubSourceSubdir] = useState('');
  const [githubReleases, setGithubReleases] = useState<GithubRelease[]>([]);
  const [selectedRelease, setSelectedRelease] = useState<GithubRelease | null>(
    null,
  );
  const [githubAssets, setGithubAssets] = useState<GithubAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<GithubAsset | null>(null);
  const [previewSkills, setPreviewSkills] = useState<PreviewSkill[]>([]);
  const [selectedPreviewPaths, setSelectedPreviewPaths] = useState<string[]>(
    [],
  );
  const [activePreviewPath, setActivePreviewPath] = useState('');
  const [fetchingReleases, setFetchingReleases] = useState(false);
  const [fetchingAssets, setFetchingAssets] = useState(false);
  const [previewingGithub, setPreviewingGithub] = useState(false);
  const [installingGithub, setInstallingGithub] = useState(false);

  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreviewSkills, setUploadPreviewSkills] = useState<
    PreviewSkill[]
  >([]);
  const [selectedUploadPreviewPaths, setSelectedUploadPreviewPaths] = useState<
    string[]
  >([]);
  const [activeUploadPreviewPath, setActiveUploadPreviewPath] = useState('');
  const [previewingUpload, setPreviewingUpload] = useState(false);
  const [installingUpload, setInstallingUpload] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const activePreviewSkill =
    previewSkills.find((skill) => previewPath(skill) === activePreviewPath) ||
    null;
  const activeUploadPreviewSkill =
    uploadPreviewSkills.find(
      (skill) => previewPath(skill) === activeUploadPreviewPath,
    ) || null;

  function initializeSelection(
    skills: PreviewSkill[],
    setSelectedPaths: (paths: string[]) => void,
    setActivePath: (path: string) => void,
  ) {
    const paths = skills.map(previewPath);
    setSelectedPaths(paths);
    setActivePath(paths[0] || '');
  }

  function toggleSelection(
    targetPath: string,
    selectedPaths: string[],
    setSelectedPaths: (paths: string[]) => void,
    setActivePath: (path: string) => void,
  ) {
    if (selectedPaths.includes(targetPath)) {
      const nextPaths = selectedPaths.filter((path) => path !== targetPath);
      setSelectedPaths(nextPaths);
      if (!nextPaths.includes(targetPath)) {
        setActivePath(nextPaths[0] || targetPath);
      }
      return;
    }

    setSelectedPaths([...selectedPaths, targetPath]);
    setActivePath(targetPath);
  }

  function buildSourceArchiveAsset(release: GithubRelease): GithubAsset | null {
    if (!release.archive_url) return null;

    return {
      id: 0,
      name: t('skills.sourceArchive'),
      size: 0,
      download_url: release.archive_url,
      content_type: 'application/zip',
    };
  }

  async function fetchReleases() {
    if (!githubURL.trim()) return;
    setFetchingReleases(true);
    setErrorMessage(null);
    setPreviewSkills([]);
    setSelectedPreviewPaths([]);
    setActivePreviewPath('');

    try {
      const result = await httpClient.getGithubReleases(githubURL);
      setGithubReleases(result.releases);
      setGithubOwner(result.owner);
      setGithubRepo(result.repo);
      setGithubSourceSubdir(result.source_subdir || '');

      if (result.releases.length === 0) {
        toast.warning(t('skills.noReleasesFound'));
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.fetchReleasesError'));
    } finally {
      setFetchingReleases(false);
    }
  }

  async function handleReleaseSelect(release: GithubRelease) {
    setSelectedRelease(release);
    setSelectedAsset(null);
    setPreviewSkills([]);
    setSelectedPreviewPaths([]);
    setActivePreviewPath('');
    setErrorMessage(null);
    setFetchingAssets(true);

    try {
      if (release.source_type && release.source_type !== 'release') {
        const archiveAsset = buildSourceArchiveAsset(release);
        setGithubAssets(archiveAsset ? [archiveAsset] : []);
        if (!archiveAsset) {
          toast.warning(t('skills.noAssetsFound'));
        }
        return;
      }

      const result = await httpClient.getGithubReleaseAssets(
        githubOwner,
        githubRepo,
        release.id,
        release.tag_name,
        release.source_type,
        release.archive_url,
      );
      let assets = result.assets;
      if (assets.length === 0) {
        const archiveAsset = buildSourceArchiveAsset(release);
        if (archiveAsset) {
          assets = [archiveAsset];
        }
      }
      setGithubAssets(assets);
      if (assets.length === 0) {
        toast.warning(t('skills.noAssetsFound'));
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.fetchAssetsError'));
    } finally {
      setFetchingAssets(false);
    }
  }

  async function handleGithubPreview(asset: GithubAsset) {
    if (!selectedRelease) return;

    setSelectedAsset(asset);
    setPreviewSkills([]);
    setSelectedPreviewPaths([]);
    setActivePreviewPath('');
    setErrorMessage(null);
    setPreviewingGithub(true);

    try {
      const resp = await httpClient.previewSkillInstallFromGithub(
        asset.download_url,
        githubOwner,
        githubRepo,
        selectedRelease.tag_name,
        githubSourceSubdir,
      );
      const skills = resp.skills as PreviewSkill[];
      setPreviewSkills(skills);
      initializeSelection(
        skills,
        setSelectedPreviewPaths,
        setActivePreviewPath,
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.installError'));
    } finally {
      setPreviewingGithub(false);
    }
  }

  async function handleGithubImport() {
    if (!selectedAsset || !selectedRelease || selectedPreviewPaths.length === 0)
      return;

    setInstallingGithub(true);
    setErrorMessage(null);
    try {
      const resp = await httpClient.installSkillFromGithub(
        selectedAsset.download_url,
        githubOwner,
        githubRepo,
        selectedRelease.tag_name,
        selectedPreviewPaths,
        githubSourceSubdir,
      );
      toast.success(t('skills.installSuccess'));
      onImported(resp.skills.map((skill) => skill.name));
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.installError'));
    } finally {
      setInstallingGithub(false);
    }
  }

  async function handleUploadPreview() {
    if (!uploadFile) return;
    if (!uploadFile.name.toLowerCase().endsWith('.zip')) {
      setErrorMessage(t('skills.uploadZipOnly'));
      return;
    }

    setPreviewingUpload(true);
    setUploadPreviewSkills([]);
    setSelectedUploadPreviewPaths([]);
    setActiveUploadPreviewPath('');
    setErrorMessage(null);
    try {
      const resp = await httpClient.previewSkillInstallFromUpload(uploadFile);
      const skills = resp.skills as PreviewSkill[];
      setUploadPreviewSkills(skills);
      initializeSelection(
        skills,
        setSelectedUploadPreviewPaths,
        setActiveUploadPreviewPath,
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.installError'));
    } finally {
      setPreviewingUpload(false);
    }
  }

  async function handleUploadImport() {
    if (!uploadFile || selectedUploadPreviewPaths.length === 0) return;

    setInstallingUpload(true);
    setErrorMessage(null);
    try {
      const resp = await httpClient.installSkillFromUpload(
        uploadFile,
        selectedUploadPreviewPaths,
      );
      toast.success(t('skills.installSuccess'));
      onImported(resp.skills.map((skill) => skill.name));
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message || t('skills.installError'));
    } finally {
      setInstallingUpload(false);
    }
  }

  function renderCandidateSelector(
    skills: PreviewSkill[],
    selectedPaths: string[],
    activePath: string,
    setSelectedPaths: (paths: string[]) => void,
    setActivePath: (path: string) => void,
  ) {
    if (skills.length <= 1) {
      return null;
    }

    return (
      <div className="space-y-2">
        {skills.map((skill) => {
          const path = previewPath(skill);
          const selected = selectedPaths.includes(path);
          const active = path === activePath;
          return (
            <div
              key={path || skill.name}
              className={`w-full rounded-lg border p-3 transition-colors ${
                active ? 'border-primary bg-accent/50' : 'hover:bg-accent/50'
              }`}
            >
              <div className="flex items-start gap-3">
                <Checkbox
                  checked={selected}
                  onCheckedChange={() =>
                    toggleSelection(
                      path,
                      selectedPaths,
                      setSelectedPaths,
                      setActivePath,
                    )
                  }
                />
                <button
                  type="button"
                  className="flex-1 text-left"
                  onClick={() => setActivePath(path)}
                >
                  <div className="font-medium">
                    {skill.display_name || skill.name}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {(skill.source_path || '.') + ' · ' + skill.name}
                  </div>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  function renderPreviewDetail(skill: PreviewSkill | null) {
    if (!skill) return null;

    return (
      <>
        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium">{t('skills.displayName')}:</span>{' '}
            {skill.display_name || '-'}
          </div>
          <div>
            <span className="font-medium">{t('skills.skillSlug')}:</span>{' '}
            {skill.name}
          </div>
          <div>
            <span className="font-medium">{t('skills.skillDescription')}:</span>{' '}
            {skill.description}
          </div>
          <div>
            <span className="font-medium">{t('skills.packageRoot')}:</span>{' '}
            {skill.package_root}
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">
            {t('skills.skillInstructions')}
          </div>
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
            {skill.instructions || ''}
          </pre>
        </div>
      </>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Github className="size-5" />
            <span>{t('skills.importFromGithub')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {githubReleases.length === 0 && (
            <div className="flex gap-2">
              <Input
                placeholder={t('skills.repoUrlPlaceholder')}
                value={githubURL}
                onChange={(e) => setGithubURL(e.target.value)}
              />
              <Button
                type="button"
                onClick={fetchReleases}
                disabled={!githubURL.trim() || fetchingReleases}
              >
                {fetchingReleases ? t('skills.loading') : t('common.confirm')}
              </Button>
            </div>
          )}

          {githubReleases.length > 0 && !selectedRelease && (
            <div className="space-y-2">
              {githubReleases.map((release) => (
                <button
                  key={release.id}
                  type="button"
                  className="w-full rounded-lg border p-3 text-left hover:bg-accent/50 transition-colors"
                  onClick={() => handleReleaseSelect(release)}
                >
                  <div className="font-medium">
                    {release.name || release.tag_name}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {t('skills.releaseTag', { tag: release.tag_name })}
                  </div>
                </button>
              ))}
            </div>
          )}

          {selectedRelease && previewSkills.length === 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">
                    {selectedRelease.name || selectedRelease.tag_name}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {t('skills.releaseTag', { tag: selectedRelease.tag_name })}
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedRelease(null);
                    setGithubAssets([]);
                    setSelectedAsset(null);
                    setPreviewSkills([]);
                    setSelectedPreviewPaths([]);
                    setActivePreviewPath('');
                    setErrorMessage(null);
                  }}
                >
                  <ChevronLeft className="size-4 mr-1" />
                  {t('skills.backToReleases')}
                </Button>
              </div>

              {fetchingAssets && (
                <div className="text-sm text-muted-foreground">
                  {t('skills.loading')}
                </div>
              )}

              {!fetchingAssets && githubAssets.length > 0 && (
                <div className="space-y-2">
                  {githubAssets.map((asset) => (
                    <button
                      key={asset.id}
                      type="button"
                      className="w-full rounded-lg border p-3 text-left hover:bg-accent/50 transition-colors"
                      onClick={() => handleGithubPreview(asset)}
                      disabled={previewingGithub}
                    >
                      <div className="font-medium">{asset.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {t('skills.assetSize', {
                          size: formatFileSize(asset.size),
                        })}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {previewSkills.length > 0 && selectedRelease && selectedAsset && (
            <div className="space-y-4 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <div className="font-medium">{t('skills.preview')}</div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setPreviewSkills([]);
                    setSelectedPreviewPaths([]);
                    setActivePreviewPath('');
                    setSelectedAsset(null);
                  }}
                >
                  <ChevronLeft className="size-4 mr-1" />
                  {t('skills.backToAssets')}
                </Button>
              </div>

              {renderCandidateSelector(
                previewSkills,
                selectedPreviewPaths,
                activePreviewPath,
                setSelectedPreviewPaths,
                setActivePreviewPath,
              )}
              {renderPreviewDetail(activePreviewSkill)}

              <div className="flex justify-end">
                <Button
                  type="button"
                  onClick={handleGithubImport}
                  disabled={
                    installingGithub || selectedPreviewPaths.length === 0
                  }
                >
                  {installingGithub
                    ? t('skills.installing')
                    : t('skills.confirmInstall')}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="size-5" />
            <span>{t('skills.uploadZip')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              setUploadFile(file);
              setUploadPreviewSkills([]);
              setSelectedUploadPreviewPaths([]);
              setActiveUploadPreviewPath('');
              setErrorMessage(null);
            }}
          />
          {uploadFile && (
            <div className="text-sm text-muted-foreground">
              {uploadFile.name}
            </div>
          )}

          <div className="flex justify-end">
            <Button
              type="button"
              onClick={handleUploadPreview}
              disabled={!uploadFile || previewingUpload}
            >
              {previewingUpload ? t('skills.loading') : t('skills.preview')}
            </Button>
          </div>

          {uploadPreviewSkills.length > 0 && uploadFile && (
            <div className="space-y-4 rounded-lg border p-4">
              <div className="font-medium">{t('skills.preview')}</div>

              {renderCandidateSelector(
                uploadPreviewSkills,
                selectedUploadPreviewPaths,
                activeUploadPreviewPath,
                setSelectedUploadPreviewPaths,
                setActiveUploadPreviewPath,
              )}
              {renderPreviewDetail(activeUploadPreviewSkill)}

              <div className="flex justify-end">
                <Button
                  type="button"
                  onClick={handleUploadImport}
                  disabled={
                    installingUpload || selectedUploadPreviewPaths.length === 0
                  }
                >
                  {installingUpload
                    ? t('skills.installing')
                    : t('skills.confirmInstall')}
                </Button>
              </div>
            </div>
          )}

          {errorMessage && (
            <div className="text-sm text-destructive">{errorMessage}</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
