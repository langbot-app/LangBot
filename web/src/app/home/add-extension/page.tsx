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
  ChevronRight,
  Server,
  Github,
  BookOpen,
  FileArchive,
  Loader2,
  CircleHelp,
  Package,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import type { Skill } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { usePluginInstallTasks } from '@/app/home/plugins/components/plugin-install-task';
import MCPForm from '@/app/home/mcp/components/mcp-form/MCPForm';
import type {
  MCPFormDraft,
  MCPFormHandle,
} from '@/app/home/mcp/components/mcp-form/MCPForm';
import SkillZipPreviewPanel from '@/app/home/skills/components/SkillZipPreviewPanel';
import PluginLocalPreviewPanel from '@/app/home/plugins/components/PluginLocalPreviewPanel';

type PopoverView = 'menu' | 'mcp' | 'github';

enum GithubInstallStatus {
  WAIT_INPUT = 'wait_input',
  SELECT_RELEASE = 'select_release',
  SELECT_ASSET = 'select_asset',
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  SKILL_PREVIEW = 'skill_preview',
  SKILL_INSTALLING = 'skill_installing',
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

interface GithubSkillMdInfo {
  owner: string;
  repo: string;
  ref: string;
  path: string;
}

function isGithubSkillMdUrl(rawUrl: string): boolean {
  try {
    const url = new URL(rawUrl.trim());
    return url.pathname.toLowerCase().endsWith('/skill.md');
  } catch {
    return rawUrl.trim().toLowerCase().split('?', 1)[0].endsWith('skill.md');
  }
}

function parseGithubSkillMdUrl(rawUrl: string): GithubSkillMdInfo {
  const url = new URL(rawUrl.trim());
  const parts = url.pathname.split('/').filter(Boolean);

  if (url.hostname === 'github.com') {
    if (parts.length < 5 || parts[2] !== 'blob') {
      throw new Error('Invalid GitHub SKILL.md URL');
    }
    return {
      owner: parts[0],
      repo: parts[1],
      ref: parts[3],
      path: parts.slice(4).join('/'),
    };
  }

  if (url.hostname === 'raw.githubusercontent.com') {
    if (parts.length < 4) {
      throw new Error('Invalid GitHub SKILL.md URL');
    }
    return {
      owner: parts[0],
      repo: parts[1],
      ref: parts[2],
      path: parts.slice(3).join('/'),
    };
  }

  throw new Error('Invalid GitHub SKILL.md URL');
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
  const [searchParams, setSearchParams] = useSearchParams();
  const { refreshPlugins, refreshMCPServers, refreshSkills } = useSidebarData();

  // Localized label for an extension type, used in the install dialog.
  const extensionTypeLabel = (type: string) =>
    type === 'mcp'
      ? t('market.typeMCP')
      : type === 'skill'
        ? t('market.typeSkill')
        : t('market.typePlugin');
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
  const [installIconFailed, setInstallIconFailed] = useState(false);

  // Marketplace icon URL for the extension being installed, by type.
  const installIconURL = (() => {
    const cloud = getCloudServiceClientSync();
    const a = installInfo.plugin_author || '';
    const n = installInfo.plugin_name || '';
    return cloud.resolveMarketplaceIconURL(
      installExtensionType,
      a,
      n,
      installInfo.plugin_icon,
    );
  })();

  // When the resolved icon URL changes (e.g. the real external icon arrives
  // after an async fetch), clear any prior load failure so the <img> retries
  // instead of staying on the placeholder.
  useEffect(() => {
    setInstallIconFailed(false);
  }, [installIconURL]);

  const [popoverOpen, setPopoverOpen] = useState(false);
  const [popoverView, setPopoverView] = useState<PopoverView>('menu');
  const [isDragOver, setIsDragOver] = useState(false);
  const [skillUploadPreviewOpen, setSkillUploadPreviewOpen] = useState(false);
  const [skillUploadPreviewFile, setSkillUploadPreviewFile] =
    useState<File | null>(null);
  const [pluginUploadPreviewOpen, setPluginUploadPreviewOpen] = useState(false);
  const [pluginUploadPreviewFile, setPluginUploadPreviewFile] =
    useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mcpFormRef = useRef<MCPFormHandle>(null);
  const [mcpTesting, setMcpTesting] = useState(false);
  const [mcpDraft, setMcpDraft] = useState<MCPFormDraft | undefined>();

  // GitHub install state
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
  const [fetchingSkillPreview, setFetchingSkillPreview] = useState(false);
  const [githubSkillInfo, setGithubSkillInfo] =
    useState<GithubSkillMdInfo | null>(null);
  const [githubSkillPreview, setGithubSkillPreview] = useState<Skill | null>(
    null,
  );
  const [githubInstallStatus, setGithubInstallStatus] =
    useState<GithubInstallStatus>(GithubInstallStatus.WAIT_INPUT);
  const [githubInstallError, setGithubInstallError] = useState<string | null>(
    null,
  );

  useEffect(() => {
    // Clear any stale completed tasks on mount
    clearCompletedTasks();
  }, [clearCompletedTasks]);

  useEffect(() => {
    if (searchParams.get('manual') !== '1') return;

    setPopoverView('menu');
    setPopoverOpen(true);
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('manual');
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  // One-click install deep link from LangBot Space:
  // /home/add-extension?install=1&extension_type=mcp&author=X&name=Y&version=Z
  // Opens the install confirm dialog directly, then strips the params.
  useEffect(() => {
    if (searchParams.get('install') !== '1') return;
    const author = searchParams.get('author');
    const name = searchParams.get('name');
    if (!author || !name) return;
    const rawType =
      searchParams.get('extension_type') ||
      searchParams.get('type') ||
      'plugin';
    const extType = (
      ['plugin', 'mcp', 'skill'].includes(rawType) ? rawType : 'plugin'
    ) as 'plugin' | 'mcp' | 'skill';
    const version = searchParams.get('version') || '';

    setInstallInfo({
      plugin_author: author,
      plugin_name: name,
      plugin_version: version,
      plugin_label: name,
    });
    setInstallExtensionType(extType);
    setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
    setInstallError(null);
    setInstallIconFailed(false);
    setModalOpen(true);

    // The icon is not carried in the URL params, so fetch it from the
    // marketplace record. Without this the confirm dialog falls back to the
    // /resources/icon endpoint, which 404s for extensions whose icon is an
    // external URL (simpleicons / iconify), showing a placeholder.
    const cloud = getCloudServiceClientSync();
    cloud
      .fetchMarketplaceIcon(extType, author, name)
      .then((icon) => {
        if (!icon) return;
        setInstallInfo((prev) =>
          prev.plugin_author === author && prev.plugin_name === name
            ? { ...prev, plugin_icon: icon }
            : prev,
        );
      })
      .catch(() => {});

    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        [
          'install',
          'extension_type',
          'type',
          'author',
          'name',
          'version',
        ].forEach((k) => next.delete(k));
        return next;
      },
      { replace: true },
    );
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const onComplete = (_taskId: number, success: boolean) => {
      if (success) {
        toast.success(t('addExtension.installSuccess'));
        // Refresh every sidebar extension list so the newly-installed
        // plugin / MCP / skill shows up immediately, regardless of type.
        refreshPlugins();
        refreshMCPServers();
        refreshSkills();
      }
    };
    registerOnTaskComplete(onComplete);
    return () => {
      unregisterOnTaskComplete(onComplete);
    };
  }, [
    registerOnTaskComplete,
    unregisterOnTaskComplete,
    refreshPlugins,
    refreshMCPServers,
    refreshSkills,
    t,
  ]);

  const handleInstallPlugin = useCallback(async (plugin: PluginV4) => {
    setInstallInfo({
      plugin_author: plugin.author,
      plugin_name: plugin.name,
      plugin_version: plugin.latest_version,
      plugin_label: extractI18nObject(plugin.label) || plugin.name,
      plugin_description: extractI18nObject(plugin.description) || '',
      plugin_icon: plugin.icon || '',
    });
    setInstallExtensionType(plugin.type || 'plugin');
    setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
    setInstallError(null);
    setInstallIconFailed(false);
    setModalOpen(true);
  }, []);

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

      setPopoverOpen(false);
      // Clear any selected task to avoid showing stale dialogs
      setSelectedTaskId(null);

      if (extType === 'plugin') {
        setPluginUploadPreviewFile(file);
        setPluginUploadPreviewOpen(true);
      } else {
        setSkillUploadPreviewFile(file);
        setSkillUploadPreviewOpen(true);
      }
    },
    [t, setSelectedTaskId],
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

  function handleMCPCreated(_serverName: string) {
    setMcpDraft(undefined);
    refreshMCPServers();
    setPopoverView('menu');
    setPopoverOpen(false);
  }

  async function checkExtensionsLimit(): Promise<boolean> {
    const maxExtensions = systemInfo.limitation?.max_extensions ?? -1;
    if (maxExtensions < 0) return true;
    try {
      const [pluginsResp, mcpResp, skillsResp] = await Promise.all([
        httpClient.getPlugins(),
        httpClient.getMCPServers(),
        httpClient.getSkills(),
      ]);
      const total =
        (pluginsResp.plugins?.length ?? 0) +
        (mcpResp.servers?.length ?? 0) +
        (skillsResp.skills?.length ?? 0);
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
    setFetchingSkillPreview(false);
    setGithubSkillInfo(null);
    setGithubSkillPreview(null);
    setGithubInstallStatus(GithubInstallStatus.WAIT_INPUT);
    setGithubInstallError(null);
  }

  async function handleGithubAddressSubmit() {
    if (isGithubSkillMdUrl(githubURL)) {
      await previewGithubSkillMd();
      return;
    }
    await fetchGithubReleases();
  }

  async function fetchGithubReleases() {
    if (!githubURL.trim()) {
      toast.error(t('plugins.enterRepoUrl'));
      return;
    }

    setFetchingReleases(true);
    setGithubInstallError(null);
    setGithubSkillInfo(null);
    setGithubSkillPreview(null);

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

  async function previewGithubSkillMd() {
    if (!githubURL.trim()) {
      toast.error(t('addExtension.githubUrlRequired'));
      return;
    }

    setFetchingSkillPreview(true);
    setGithubInstallError(null);
    setGithubReleases([]);
    setGithubAssets([]);
    setSelectedRelease(null);
    setSelectedAsset(null);

    try {
      const skillInfo = parseGithubSkillMdUrl(githubURL);
      const result = await httpClient.previewSkillInstallFromGithub(
        githubURL.trim(),
        skillInfo.owner,
        skillInfo.repo,
        skillInfo.ref,
      );
      const preview = result.skills?.[0];
      if (!preview) {
        throw new Error(t('addExtension.noSkillPreviewFound'));
      }
      setGithubOwner(skillInfo.owner);
      setGithubRepo(skillInfo.repo);
      setGithubSkillInfo(skillInfo);
      setGithubSkillPreview(preview);
      setGithubInstallStatus(GithubInstallStatus.SKILL_PREVIEW);
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      setGithubInstallError(errorMessage || t('skills.previewLoadError'));
      setGithubInstallStatus(GithubInstallStatus.ERROR);
    } finally {
      setFetchingSkillPreview(false);
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

  async function handleGithubSkillConfirm() {
    if (!githubSkillInfo) return;
    if (!(await checkExtensionsLimit())) return;

    setGithubInstallStatus(GithubInstallStatus.SKILL_INSTALLING);
    try {
      await httpClient.installSkillFromGithub(
        githubURL.trim(),
        githubSkillInfo.owner,
        githubSkillInfo.repo,
        githubSkillInfo.ref,
      );
      toast.success(t('skills.installSuccess'));
      refreshPlugins();
      refreshSkills();
      resetGithubState();
      setPopoverOpen(false);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : typeof err === 'object' && err && 'msg' in err
            ? String((err as { msg?: string }).msg || '')
            : String(err);
      setGithubInstallError(errorMessage);
      setGithubInstallStatus(GithubInstallStatus.ERROR);
    }
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
        return 'w-[calc(100vw-2rem)] sm:w-[560px]';
      case 'github':
        return 'w-[calc(100vw-2rem)] sm:w-[560px]';
      default:
        return 'w-[calc(100vw-2rem)] sm:w-[380px]';
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
          forceMount
          className={`${getPopoverWidth()} max-h-[min(720px,80vh)] overflow-hidden p-0`}
          align="end"
        >
          {/* ===== Menu View ===== */}
          {popoverView === 'menu' && (
            <div className="space-y-4 p-4">
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

              <p className="text-center text-xs text-muted-foreground">
                {t('addExtension.orContinueWith')}
              </p>

              <div className="space-y-2">
                <button
                  type="button"
                  className="group flex w-full items-center gap-3 rounded-md bg-muted/30 p-3 text-left transition-colors outline-none hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  onClick={() => setPopoverView('mcp')}
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground transition-colors group-hover:text-foreground">
                    <Server className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="block text-sm font-medium leading-none">
                      {t('mcp.addMCPServer')}
                    </span>
                    <span className="block text-xs leading-relaxed text-muted-foreground">
                      {t('addExtension.addMCPServerHint')}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </button>

                <button
                  type="button"
                  className="group flex w-full items-center gap-3 rounded-md bg-muted/30 p-3 text-left transition-colors outline-none hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  onClick={() => setPopoverView('github')}
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground transition-colors group-hover:text-foreground">
                    <Github className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="block text-sm font-medium leading-none">
                      {t('addExtension.installFromGithub')}
                    </span>
                    <span className="block text-xs leading-relaxed text-muted-foreground">
                      {t('addExtension.installFromGithubHint')}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </button>

                <button
                  type="button"
                  className="group flex w-full items-center gap-3 rounded-md bg-muted/30 p-3 text-left transition-colors outline-none hover:bg-accent hover:text-accent-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                  onClick={async () => {
                    if (!(await checkExtensionsLimit())) return;
                    setPopoverOpen(false);
                    navigate('/home/skills?action=create');
                  }}
                >
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground transition-colors group-hover:text-foreground">
                    <BookOpen className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1 space-y-0.5">
                    <span className="block text-sm font-medium leading-none">
                      {t('addExtension.createSkill')}
                    </span>
                    <span className="block text-xs leading-relaxed text-muted-foreground">
                      {t('addExtension.createSkillHint')}
                    </span>
                  </span>
                  <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                </button>
              </div>
            </div>
          )}

          {/* ===== MCP Form View ===== */}
          {popoverView === 'mcp' && (
            <div className="flex max-h-[min(720px,80vh)] flex-col">
              <div className="flex items-center gap-2 px-4 pb-1 pt-3">
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

              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                <MCPForm
                  ref={mcpFormRef}
                  initServerName={undefined}
                  initialDraft={mcpDraft}
                  onFormSubmit={() => {}}
                  onNewServerCreated={handleMCPCreated}
                  onDraftChange={setMcpDraft}
                  onTestingChange={setMcpTesting}
                />
              </div>

              <div className="flex items-center justify-end gap-2 bg-popover px-4 pb-4 pt-1">
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

          {/* ===== GitHub Install View ===== */}
          {popoverView === 'github' && (
            <div className="flex max-h-[min(720px,80vh)] flex-col">
              <div className="flex items-center gap-2 px-4 pb-1 pt-3">
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
                  {t('addExtension.installFromGithub')}
                </h4>
              </div>

              <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
                {githubInstallStatus === GithubInstallStatus.WAIT_INPUT && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span>{t('addExtension.githubUrlHelp')}</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className="inline-flex size-4 items-center justify-center rounded-full transition-colors hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                            aria-label={t('addExtension.githubUrlTooltip')}
                          >
                            <CircleHelp className="size-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="max-w-[280px]">
                          {t('addExtension.githubUrlTooltip')}
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Input
                      placeholder={t('addExtension.githubUrlPlaceholder')}
                      value={githubURL}
                      onChange={(e) => setGithubURL(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleGithubAddressSubmit();
                      }}
                    />
                    <Button
                      className="w-full"
                      onClick={handleGithubAddressSubmit}
                      disabled={
                        !githubURL.trim() ||
                        fetchingReleases ||
                        fetchingSkillPreview
                      }
                    >
                      {(fetchingReleases || fetchingSkillPreview) && (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      )}
                      {fetchingReleases || fetchingSkillPreview
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
                          setGithubInstallStatus(
                            GithubInstallStatus.WAIT_INPUT,
                          );
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
                          className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 text-sm hover:bg-accent"
                          onClick={() => handleReleaseSelect(release)}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate text-xs">
                              {release.name || release.tag_name}
                            </div>
                            <div className="text-[11px] text-muted-foreground">
                              {release.tag_name} &bull;{' '}
                              {new Date(
                                release.published_at,
                              ).toLocaleDateString()}
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
                          setGithubInstallStatus(
                            GithubInstallStatus.SELECT_RELEASE,
                          );
                          setGithubAssets([]);
                          setSelectedAsset(null);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToReleases')}
                      </Button>
                    </div>
                    {selectedRelease && (
                      <div className="rounded-md bg-muted/40 px-2 py-1.5 text-[11px]">
                        <span className="font-medium">
                          {selectedRelease.name || selectedRelease.tag_name}
                        </span>
                      </div>
                    )}
                    <div className="max-h-[300px] overflow-y-auto space-y-1.5">
                      {githubAssets.map((asset) => (
                        <div
                          key={asset.id}
                          className="flex cursor-pointer items-center justify-between rounded-md px-2 py-2 hover:bg-accent"
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
                          setGithubInstallStatus(
                            GithubInstallStatus.SELECT_ASSET,
                          );
                          setSelectedAsset(null);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToAssets')}
                      </Button>
                    </div>
                    {selectedRelease && selectedAsset && (
                      <div className="space-y-1 rounded-md bg-muted/40 px-2 py-2 text-xs">
                        <div>
                          <span className="font-medium">Repository: </span>
                          <span>
                            {githubOwner}/{githubRepo}
                          </span>
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
                    <Button className="w-full" onClick={handleGithubConfirm}>
                      {t('common.confirm')}
                    </Button>
                  </div>
                )}

                {githubInstallStatus === GithubInstallStatus.SKILL_PREVIEW && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-medium">
                        {t('addExtension.previewSkill')}
                      </p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs px-2"
                        onClick={() => {
                          setGithubInstallStatus(
                            GithubInstallStatus.WAIT_INPUT,
                          );
                          setGithubSkillInfo(null);
                          setGithubSkillPreview(null);
                        }}
                      >
                        <ChevronLeft className="w-3 h-3 mr-1" />
                        {t('plugins.backToRepoUrl')}
                      </Button>
                    </div>

                    {githubSkillPreview && (
                      <div className="space-y-2 rounded-md bg-muted/40 p-3 text-xs">
                        <div className="flex items-start gap-2">
                          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground">
                            <BookOpen className="size-3.5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-medium">
                              {githubSkillPreview.display_name ||
                                githubSkillPreview.name}
                            </div>
                            <div className="truncate text-[11px] text-muted-foreground">
                              {githubSkillPreview.name}
                            </div>
                          </div>
                        </div>
                        {githubSkillPreview.description && (
                          <p className="leading-relaxed text-muted-foreground">
                            {githubSkillPreview.description}
                          </p>
                        )}
                        <div className="space-y-1 text-[11px] text-muted-foreground">
                          <div>
                            <span className="font-medium text-foreground">
                              Repository:{' '}
                            </span>
                            {githubSkillInfo?.owner}/{githubSkillInfo?.repo}
                          </div>
                          <div>
                            <span className="font-medium text-foreground">
                              File:{' '}
                            </span>
                            <span className="break-all">
                              {githubSkillInfo?.path}
                            </span>
                          </div>
                          {githubSkillPreview.package_root && (
                            <div>
                              <span className="font-medium text-foreground">
                                Directory:{' '}
                              </span>
                              <span className="break-all">
                                {githubSkillPreview.package_root}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    <Button
                      className="w-full"
                      onClick={handleGithubSkillConfirm}
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

                {githubInstallStatus ===
                  GithubInstallStatus.SKILL_INSTALLING && (
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('skills.installing')}</span>
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
              <span>
                {t('addExtension.installTitle', {
                  type: extensionTypeLabel(installExtensionType),
                })}
              </span>
            </DialogTitle>
          </DialogHeader>

          {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
            <div className="mt-4 space-y-3">
              <p>
                {t('addExtension.installConfirm', {
                  type: extensionTypeLabel(installExtensionType),
                  name: installInfo.plugin_label || installInfo.plugin_name,
                })}
              </p>
              <div className="flex gap-3 rounded-md bg-muted/40 p-3">
                {installIconFailed ? (
                  <div className="flex size-12 shrink-0 items-center justify-center rounded-lg border bg-background text-muted-foreground">
                    <Package className="size-6" />
                  </div>
                ) : (
                  <img
                    src={installIconURL}
                    alt={installInfo.plugin_name}
                    className="size-12 shrink-0 rounded-lg border bg-background object-cover"
                    onError={() => setInstallIconFailed(true)}
                  />
                )}
                <div className="min-w-0 flex-1 space-y-0.5">
                  <div className="truncate font-medium">
                    {installInfo.plugin_label || installInfo.plugin_name}
                  </div>
                  <div className="truncate text-xs text-muted-foreground">
                    {installInfo.plugin_author}/{installInfo.plugin_name}
                    {installInfo.plugin_version
                      ? ` · v${installInfo.plugin_version}`
                      : ''}
                  </div>
                  {installInfo.plugin_description && (
                    <div className="line-clamp-3 pt-0.5 text-xs text-muted-foreground">
                      {installInfo.plugin_description}
                    </div>
                  )}
                </div>
              </div>
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

      {/* Plugin Upload Preview Dialog */}
      <Dialog
        open={pluginUploadPreviewOpen}
        onOpenChange={(open) => {
          setPluginUploadPreviewOpen(open);
          if (!open) {
            setPluginUploadPreviewFile(null);
          }
        }}
      >
        <DialogContent className="w-[calc(100vw-2rem)] sm:max-w-xl max-h-[85vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileArchive className="size-5" />
              <span>{t('plugins.localPreview.title')}</span>
            </DialogTitle>
          </DialogHeader>
          {pluginUploadPreviewFile && (
            <PluginLocalPreviewPanel
              file={pluginUploadPreviewFile}
              onCancel={() => {
                setPluginUploadPreviewOpen(false);
                setPluginUploadPreviewFile(null);
              }}
              onInstallStarted={() => {
                setPluginUploadPreviewOpen(false);
                setPluginUploadPreviewFile(null);
              }}
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Skill Upload Preview Dialog */}
      <Dialog
        open={skillUploadPreviewOpen}
        onOpenChange={(open) => {
          setSkillUploadPreviewOpen(open);
          if (!open) {
            setSkillUploadPreviewFile(null);
          }
        }}
      >
        <DialogContent className="w-[calc(100vw-2rem)] sm:max-w-3xl max-h-[85vh] overflow-y-auto p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileArchive className="size-5" />
              <span>{t('skills.uploadZip')}</span>
            </DialogTitle>
          </DialogHeader>
          {skillUploadPreviewFile && (
            <SkillZipPreviewPanel
              file={skillUploadPreviewFile}
              onCancel={() => {
                setSkillUploadPreviewOpen(false);
                setSkillUploadPreviewFile(null);
              }}
              onImported={(skillNames) => {
                setSkillUploadPreviewOpen(false);
                setSkillUploadPreviewFile(null);
                void refreshSkills();
                const firstSkillName = skillNames[0];
                if (firstSkillName) {
                  navigate(
                    `/home/skills?id=${encodeURIComponent(firstSkillName)}`,
                  );
                }
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
