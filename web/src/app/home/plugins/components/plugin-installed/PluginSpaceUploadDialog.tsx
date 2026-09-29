import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, Upload, Github, AlertTriangle, ImagePlus } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useAuthenticatedPluginIcon } from '@/hooks/useAuthenticatedPluginResource';
import type {
  PluginManifestOverrides,
  PluginSpaceUploadConfig,
} from '@/app/infra/entities/plugin';
import type { I18nObject } from '@/app/infra/entities/common';

/**
 * Locales exposed in the upload page. ``en_US`` is the manifest default.
 * Each tab shows the language's own endonym so the label is unambiguous
 * regardless of the current UI language.
 */
const LOCALES: { code: string; label: string }[] = [
  { code: 'en_US', label: 'English' },
  { code: 'zh_Hans', label: '简体中文' },
  { code: 'zh_Hant', label: '繁體中文' },
  { code: 'ja_JP', label: '日本語' },
  { code: 'th_TH', label: 'ไทย' },
  { code: 'vi_VN', label: 'Tiếng Việt' },
  { code: 'es_ES', label: 'Español' },
];

/**
 * Icon size ceiling, mirrored by the backend validator.
 *
 * The icon is sent inline (base64) inside a single runtime action, and the SDK
 * caps a single message at 16MB (``MAX_MESSAGE_BYTES``). 10MB raw is ~13.3MB
 * base64, which leaves headroom under that cap; a larger icon would need to be
 * moved to the chunked file-transfer channel.
 */
const MAX_ICON_BYTES = 10 * 1024 * 1024;

/** Extract a readable message from the backend's ``{code, msg}`` error shape. */
function formatError(error: unknown): string {
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object') {
    const record = error as { msg?: string; message?: string };
    if (record.msg) return record.msg;
    if (record.message) return record.message;
    try {
      return JSON.stringify(error);
    } catch {
      return String(error);
    }
  }
  return String(error);
}

type I18nDraft = Record<string, string>;

function toDraft(value: I18nObject | string | undefined): I18nDraft {
  const draft: I18nDraft = {};
  if (value === undefined || value === null) return draft;
  if (typeof value === 'string') {
    draft.en_US = value;
    return draft;
  }
  for (const locale of LOCALES) {
    const text = value[locale.code as keyof I18nObject];
    if (typeof text === 'string') draft[locale.code] = text;
  }
  return draft;
}

function draftToI18n(draft: I18nDraft): I18nObject | undefined {
  const entries: [string, string][] = LOCALES.map((locale) => [
    locale.code,
    (draft[locale.code] ?? '').trim(),
  ]).filter((entry) => entry[1].length > 0) as [string, string][];
  if (entries.length === 0) return undefined;

  const result = { en_US: '' } as I18nObject;
  const mutable = result as unknown as Record<string, string>;
  for (const [code, text] of entries) {
    mutable[code] = text;
  }
  if (!result.en_US) {
    // The manifest requires en_US; fall back to the first provided locale.
    result.en_US = entries[0][1];
  }
  return result;
}

function draftHasContent(draft: I18nDraft): boolean {
  return LOCALES.some((locale) => (draft[locale.code] ?? '').trim().length > 0);
}

export default function PluginSpaceUploadDialog({
  author,
  name,
  open,
  onOpenChange,
  onUploaded,
}: {
  author: string;
  name: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded?: () => void;
}) {
  const { t } = useTranslation();
  const authenticatedIcon = useAuthenticatedPluginIcon(author, name, true);

  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [config, setConfig] = useState<PluginSpaceUploadConfig | null>(null);

  const [labelDraft, setLabelDraft] = useState<I18nDraft>({});
  const [descriptionDraft, setDescriptionDraft] = useState<I18nDraft>({});
  const [version, setVersion] = useState('');
  const [repository, setRepository] = useState('');
  const [changelog, setChangelog] = useState('');
  const [activeLocale, setActiveLocale] = useState('en_US');

  const [iconDataUrl, setIconDataUrl] = useState('');
  const [iconFileName, setIconFileName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [syncGithub, setSyncGithub] = useState(false);
  const [repoUrl, setRepoUrl] = useState('');
  const [token, setToken] = useState('');
  const [branch, setBranch] = useState('');
  const [commitMessage, setCommitMessage] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const loadConfig = useMemo(
    () => async () => {
      setLoadingConfig(true);
      setLoadError(false);
      try {
        const info = await httpClient.getPluginSpaceUploadConfig(author, name);
        setConfig(info);
        setLabelDraft(toDraft(info.metadata.label));
        setDescriptionDraft(toDraft(info.metadata.description));
        setVersion(info.metadata.version ?? '');
        setRepository(info.metadata.repository ?? '');
        setRepoUrl(info.metadata.repository ?? '');
      } catch {
        setLoadError(true);
        toast.error(t('plugins.spaceUpload.loadFailed'));
      } finally {
        setLoadingConfig(false);
      }
    },
    [author, name, t],
  );

  useEffect(() => {
    if (open) void loadConfig();
  }, [open, loadConfig]);

  function handleIconSelect(file: File | null) {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      toast.error(t('plugins.spaceUpload.iconInvalidType'));
      return;
    }
    if (file.size > MAX_ICON_BYTES) {
      toast.error(t('plugins.spaceUpload.iconTooLarge'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setIconDataUrl(typeof reader.result === 'string' ? reader.result : '');
      setIconFileName(file.name);
    };
    reader.readAsDataURL(file);
  }

  function buildOverrides(): PluginManifestOverrides {
    const overrides: PluginManifestOverrides = {};
    const label = draftToI18n(labelDraft);
    if (label) overrides.label = label;
    const description = draftToI18n(descriptionDraft);
    if (description) overrides.description = description;
    if (version.trim()) overrides.version = version.trim();
    if (repository.trim()) overrides.repository = repository.trim();
    if (iconDataUrl) overrides.icon_base64 = iconDataUrl;
    return overrides;
  }

  async function handleSyncGithubOnly() {
    setSyncing(true);
    try {
      const result = await httpClient.syncPluginToGithub(author, name, {
        repo_url: repoUrl.trim(),
        token: token.trim(),
        branch: branch.trim(),
        commit_message: commitMessage.trim(),
        manifest_overrides: buildOverrides(),
      });
      const git = result.git;
      if (git?.pushed) {
        toast.success(t('plugins.spaceUpload.gitSynced'));
      } else if (git?.committed) {
        toast.warning(git.message || t('plugins.spaceUpload.gitCommittedNoRemote'));
      } else {
        toast.info(git?.message || t('plugins.spaceUpload.gitNothing'));
      }
    } catch (error) {
      toast.error(`${t('plugins.spaceUpload.gitFailed')} ${formatError(error)}`);
    } finally {
      setSyncing(false);
    }
  }

  async function handleUpload() {
    setSubmitting(true);
    try {
      await httpClient.uploadPluginToSpace(author, name, {
        sync_github: syncGithub,
        changelog: changelog.trim(),
        repo_url: syncGithub ? repoUrl.trim() : '',
        token: syncGithub ? token.trim() : '',
        branch: syncGithub ? branch.trim() : '',
        commit_message: syncGithub ? commitMessage.trim() : '',
        manifest_overrides: buildOverrides(),
      });
      toast.success(t('plugins.spaceUpload.uploadSuccess'));
      onUploaded?.();
      onOpenChange(false);
    } catch (error) {
      toast.error(
        `${t('plugins.spaceUpload.uploadFailed')} ${formatError(error)}`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  // Only block submission when the server explicitly reports no Space account.
  // If the prefill request failed, allow an attempt so the server can return a
  // precise error instead of leaving the form unusable.
  const canSubmit = config ? config.space_connected : true;
  const spaceWarning = !!config && !config.space_connected;
  const busy = submitting || syncing;
  const hasLabel = draftHasContent(labelDraft);

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="size-4" />
            {t('plugins.spaceUpload.title')}
          </DialogTitle>
          <DialogDescription>
            {t('plugins.spaceUpload.description', { author, name })}
          </DialogDescription>
        </DialogHeader>

        {loadingConfig ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4 py-2">
            {loadError && (
              <div className="flex items-center justify-between gap-2 rounded-md border border-amber-400/50 bg-amber-50/50 p-3 text-sm text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                <span>{t('plugins.spaceUpload.loadFailed')}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void loadConfig()}
                >
                  {t('common.retry')}
                </Button>
              </div>
            )}
            {spaceWarning && (
              <div className="flex items-start gap-2 rounded-md border border-amber-400/50 bg-amber-50/50 p-3 text-sm text-amber-700 dark:bg-amber-500/10 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 size-4 flex-shrink-0" />
                <span>{t('plugins.spaceUpload.spaceNotConnected')}</span>
              </div>
            )}

            {/* Icon + version/repository */}
            <div className="flex flex-col gap-4 sm:flex-row">
              <div className="flex flex-col items-center gap-2">
                <img
                  src={iconDataUrl || authenticatedIcon.url || undefined}
                  alt="plugin icon"
                  className="h-20 w-20 rounded-lg border object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.visibility = 'hidden';
                  }}
                />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => handleIconSelect(e.target.files?.[0] ?? null)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={busy}
                >
                  <ImagePlus className="mr-1.5 size-4" />
                  {t('plugins.spaceUpload.changeIcon')}
                </Button>
                {iconFileName && (
                  <span className="max-w-[10rem] truncate text-[0.7rem] text-muted-foreground">
                    {iconFileName}
                  </span>
                )}
              </div>

              <div className="flex-1 space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="space-upload-version">
                    {t('plugins.spaceUpload.version')}
                  </Label>
                  <Input
                    id="space-upload-version"
                    value={version}
                    onChange={(e) => setVersion(e.target.value)}
                    placeholder="0.1.0"
                    disabled={busy}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="space-upload-repository">
                    {t('plugins.spaceUpload.repository')}
                  </Label>
                  <Input
                    id="space-upload-repository"
                    value={repository}
                    onChange={(e) => setRepository(e.target.value)}
                    placeholder="https://github.com/owner/repo"
                    disabled={busy}
                  />
                </div>
              </div>
            </div>

            {/* Multi-language name & description */}
            <div className="space-y-2">
              <Label>{t('plugins.spaceUpload.basicInfo')}</Label>
              <Tabs value={activeLocale} onValueChange={setActiveLocale}>
                <TabsList className="flex-wrap h-auto">
                  {LOCALES.map((locale) => (
                    <TabsTrigger key={locale.code} value={locale.code}>
                      {locale.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>

              <div className="space-y-1.5 pt-1">
                <Label htmlFor="space-upload-label">
                  {t('plugins.spaceUpload.label')}
                </Label>
                <Input
                  id="space-upload-label"
                  value={labelDraft[activeLocale] ?? ''}
                  onChange={(e) =>
                    setLabelDraft((prev) => ({
                      ...prev,
                      [activeLocale]: e.target.value,
                    }))
                  }
                  disabled={busy}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="space-upload-description">
                  {t('plugins.spaceUpload.pluginDescription')}
                </Label>
                <Textarea
                  id="space-upload-description"
                  value={descriptionDraft[activeLocale] ?? ''}
                  onChange={(e) =>
                    setDescriptionDraft((prev) => ({
                      ...prev,
                      [activeLocale]: e.target.value,
                    }))
                  }
                  rows={3}
                  disabled={busy}
                />
              </div>
              {!hasLabel && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  {t('plugins.spaceUpload.labelRequired')}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="space-upload-changelog">
                {t('plugins.spaceUpload.changelog')}
              </Label>
              <Textarea
                id="space-upload-changelog"
                value={changelog}
                onChange={(e) => setChangelog(e.target.value)}
                rows={2}
                disabled={busy}
              />
            </div>

            {/* GitHub sync */}
            <div className="space-y-3 rounded-md border p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Github className="size-4" />
                  <Label
                    htmlFor="space-upload-sync-github"
                    className="cursor-pointer"
                  >
                    {t('plugins.spaceUpload.syncGithub')}
                  </Label>
                </div>
                <Switch
                  id="space-upload-sync-github"
                  checked={syncGithub}
                  onCheckedChange={setSyncGithub}
                  disabled={busy}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {t('plugins.spaceUpload.syncGithubHint')}
              </p>

              {syncGithub && (
                <div className="space-y-3 pt-1">
                  <div className="space-y-1.5">
                    <Label htmlFor="space-upload-repo-url">
                      {t('plugins.spaceUpload.repoUrl')}
                    </Label>
                    <Input
                      id="space-upload-repo-url"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      placeholder="https://github.com/owner/repo"
                      disabled={busy}
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('plugins.spaceUpload.repoUrlHint')}
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="space-upload-token">
                        {t('plugins.spaceUpload.token')}
                      </Label>
                      <Input
                        id="space-upload-token"
                        type="password"
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        placeholder={t('plugins.spaceUpload.tokenPlaceholder')}
                        disabled={busy}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="space-upload-branch">
                        {t('plugins.spaceUpload.branch')}
                      </Label>
                      <Input
                        id="space-upload-branch"
                        value={branch}
                        onChange={(e) => setBranch(e.target.value)}
                        placeholder="main"
                        disabled={busy}
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="space-upload-commit">
                      {t('plugins.spaceUpload.commitMessage')}
                    </Label>
                    <Input
                      id="space-upload-commit"
                      value={commitMessage}
                      onChange={(e) => setCommitMessage(e.target.value)}
                      disabled={busy}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleSyncGithubOnly}
                    disabled={busy}
                  >
                    {syncing && (
                      <Loader2 className="mr-1.5 size-4 animate-spin" />
                    )}
                    <Github className="mr-1.5 size-4" />
                    {t('plugins.spaceUpload.syncOnly')}
                  </Button>
                </div>
              )}
            </div>

            {config?.debug === false && (
              <Badge variant="outline" className="text-[0.7rem]">
                {t('plugins.spaceUpload.notDebugHint')}
              </Badge>
            )}
          </div>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            onClick={handleUpload}
            disabled={busy || loadingConfig || !canSubmit || !hasLabel}
          >
            {submitting && <Loader2 className="mr-1.5 size-4 animate-spin" />}
            <Upload className="mr-1.5 size-4" />
            {t('plugins.spaceUpload.uploadButton')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
