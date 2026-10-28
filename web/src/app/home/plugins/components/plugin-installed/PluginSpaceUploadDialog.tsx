import { useEffect, useMemo, useState } from 'react';
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
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Loader2,
  Upload,
  AlertTriangle,
  Check,
  CheckCircle2,
  ArrowLeft,
  ArrowRight,
  ExternalLink,
  Info,
  RefreshCw,
  Sparkles,
  AlertCircle,
  ShieldCheck,
  Puzzle,
  Globe,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useAuthenticatedPluginIcon } from '@/hooks/useAuthenticatedPluginResource';
import type { PluginSpaceUploadConfig } from '@/app/infra/entities/plugin';
import type { I18nObject } from '@/app/infra/entities/common';
import { cn } from '@/lib/utils';

/**
 * Locales supported for manifest preview.
 * English (en_US) is placed first as the canonical manifest default.
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

/** Extract a readable message from the backend's ``{code, msg}`` error shape. */
function formatError(error: unknown): string {
  if (typeof error === 'string') return error;
  if (error && typeof error === 'object') {
    const record = error as {
      msg?: string;
      message?: string;
      response?: { data?: { msg?: string; message?: string } };
      data?: { msg?: string; message?: string };
    };
    if (record.response?.data?.msg) return record.response.data.msg;
    if (record.response?.data?.message) return record.response.data.message;
    if (record.data?.msg) return record.data.msg;
    if (record.data?.message) return record.data.message;
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

function localizeUploadError(
  error: unknown,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  const raw = formatError(error);
  if (!raw) return '';

  if (/set up a creator profile/i.test(raw)) {
    return t('plugins.spaceUpload.errors.noCreatorProfile');
  }

  const mismatchMatch = raw.match(
    /plugin author ['"]?([^'"]+)['"]? does not match .*?@['"]?([^'"]+)['"]?/i,
  );
  if (mismatchMatch) {
    return t('plugins.spaceUpload.errors.authorMismatch', {
      author: mismatchMatch[1],
      slug: mismatchMatch[2],
    });
  }

  if (/already have a plugin submission pending/i.test(raw)) {
    return t('plugins.spaceUpload.errors.pendingReview');
  }

  if (/session has expired|re-authenticate|unauthorized/i.test(raw)) {
    return t('plugins.spaceUpload.errors.sessionExpired');
  }

  if (/connect a LangBot Space account/i.test(raw)) {
    return t('plugins.spaceUpload.errors.notConnected');
  }

  if (/failed certification precheck/i.test(raw)) {
    const detail = raw.replace(/^failed certification precheck:\s*/i, '');
    return t('plugins.spaceUpload.errors.certPrecheckFailed', { detail });
  }

  if (/failed to inspect plugin/i.test(raw)) {
    const detail = raw.replace(/^failed to inspect plugin:\s*/i, '');
    return t('plugins.spaceUpload.errors.inspectFailed', { detail });
  }

  if (/failed to build the plugin package/i.test(raw)) {
    return t('plugins.spaceUpload.errors.packageFailed');
  }

  return raw;
}

interface UploadErrorState {
  type:
    | 'pendingReview'
    | 'sessionExpired'
    | 'notConnected'
    | 'noCreator'
    | 'authorMismatch'
    | 'validation'
    | 'generic';
  detail?: string;
  author?: string;
  slug?: string;
}

function parseUploadError(error: unknown): UploadErrorState {
  const raw = formatError(error);
  if (/already have a plugin submission pending/i.test(raw)) {
    return { type: 'pendingReview' };
  }
  if (/session has expired|re-authenticate|unauthorized/i.test(raw)) {
    return { type: 'sessionExpired' };
  }
  if (/set up a creator profile/i.test(raw)) {
    return { type: 'noCreator' };
  }
  const mismatchMatch = raw.match(
    /plugin author ['"]?([^'"]+)['"]? does not match .*?@['"]?([^'"]+)['"]?/i,
  );
  if (mismatchMatch) {
    return {
      type: 'authorMismatch',
      author: mismatchMatch[1],
      slug: mismatchMatch[2],
    };
  }
  if (/connect a LangBot Space account/i.test(raw)) {
    return { type: 'notConnected' };
  }
  if (/failed certification precheck|failed to inspect/i.test(raw)) {
    return {
      type: 'validation',
      detail: raw.replace(
        /^(failed certification precheck|failed to inspect plugin):\s*/i,
        '',
      ),
    };
  }
  return {
    type: 'generic',
    detail: raw,
  };
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
  const [iconFailed, setIconFailed] = useState(false);

  useEffect(() => {
    setIconFailed(false);
  }, [open, authenticatedIcon.url]);

  // Stepper state: 1 = Plugin Info Confirmation, 2 = Release Notes, 3 = Review & Upload
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);

  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [config, setConfig] = useState<PluginSpaceUploadConfig | null>(null);

  // Manifest fields (strictly read-only confirmation)
  const [labelDraft, setLabelDraft] = useState<I18nDraft>({});
  const [descriptionDraft, setDescriptionDraft] = useState<I18nDraft>({});
  const [version, setVersion] = useState('');
  const [repository, setRepository] = useState('');
  const [authorName, setAuthorName] = useState(author);
  const [license, setLicense] = useState('');

  // Step 2 input: Changelog
  const [changelog, setChangelog] = useState('');

  // Space Account Binding action
  const [bindingSpace, setBindingSpace] = useState(false);

  // Multi-language tab selection defaults to English
  const [activeLocale, setActiveLocale] = useState('en_US');
  const [submitting, setSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState<UploadErrorState | null>(null);
  const [uploadStatus, setUploadStatus] = useState<
    'idle' | 'uploading' | 'success' | 'error'
  >('idle');
  const [uploadProgress, setUploadProgress] = useState(0);

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
        setAuthorName(info.metadata.author ?? author);
        setLicense(info.metadata.license ?? '');
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
    if (open) {
      setCurrentStep(1);
      setActiveLocale('en_US');
      setUploadError(null);
      setUploadStatus('idle');
      setUploadProgress(0);
      void loadConfig();
    }
  }, [open, loadConfig]);

  // Display name prioritizes active locale, then English fallback, then first available
  const displayName = useMemo(() => {
    if (labelDraft[activeLocale]) return labelDraft[activeLocale];
    if (labelDraft.en_US) return labelDraft.en_US;
    if (labelDraft.zh_Hans) return labelDraft.zh_Hans;
    const first = Object.values(labelDraft).find((v) => Boolean(v));
    if (first) return first;
    return name;
  }, [labelDraft, activeLocale, name]);

  const displayDescription = useMemo(() => {
    if (descriptionDraft[activeLocale]) return descriptionDraft[activeLocale];
    if (descriptionDraft.en_US) return descriptionDraft.en_US;
    if (descriptionDraft.zh_Hans) return descriptionDraft.zh_Hans;
    const first = Object.values(descriptionDraft).find((v) => Boolean(v));
    if (first) return first;
    return '';
  }, [descriptionDraft, activeLocale]);

  async function handleBindSpace() {
    setBindingSpace(true);
    try {
      const currentOrigin = window.location.origin;
      const redirectUri = `${currentOrigin}/auth/space/callback?mode=bind`;
      const response = await httpClient.getSpaceBindAuthorizeUrl(redirectUri);
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setBindingSpace(false);
    }
  }

  async function handleStartUpload() {
    setCurrentStep(3);
    setUploadStatus('uploading');
    setSubmitting(true);
    setUploadError(null);
    setUploadProgress(15);

    const timer = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 88) return prev;
        return prev + Math.floor(Math.random() * 12 + 6);
      });
    }, 300);

    try {
      await httpClient.uploadPluginToSpace(author, name, {
        sync_github: false,
        changelog: changelog.trim(),
        manifest_overrides: {},
      });
      clearInterval(timer);
      setUploadProgress(100);
      setUploadStatus('success');
      onUploaded?.();
    } catch (error) {
      clearInterval(timer);
      const parsed = parseUploadError(error);
      setUploadError(parsed);
      setUploadStatus('error');
      if (
        parsed.type === 'notConnected' ||
        parsed.type === 'noCreator' ||
        parsed.type === 'authorMismatch'
      ) {
        void loadConfig();
      }
    } finally {
      clearInterval(timer);
      setSubmitting(false);
    }
  }

  const prerequisitesMet = Boolean(
    config?.space_connected && config?.has_creator_profile,
  );

  const busy = submitting || bindingSpace || uploadStatus === 'uploading';

  const canSubmit = Boolean(
    prerequisitesMet &&
    config?.author_matches &&
    !busy &&
    !loadingConfig &&
    !loadError,
  );

  const steps = [
    { id: 1, title: t('plugins.spaceUpload.stepInfo') },
    { id: 2, title: t('plugins.spaceUpload.stepConfirm') },
    { id: 3, title: t('plugins.spaceUpload.stepResult') },
  ];

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-2xl p-0 gap-0 overflow-hidden flex flex-col h-[700px] max-h-[88vh]">
        {/* Dialog Header */}
        <DialogHeader className="px-6 pt-5 pb-2 shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Upload className="size-4 text-primary" />
            {t('plugins.spaceUpload.title')}
          </DialogTitle>
          <DialogDescription className="text-xs">
            {t('plugins.spaceUpload.description', { author, name })}
          </DialogDescription>
        </DialogHeader>

        {/* Stepper Progress */}
        {prerequisitesMet && !loadingConfig && !loadError && (
          <div className="px-6 pt-1 pb-3 shrink-0">
            <div className="flex items-center justify-center gap-2 sm:gap-4">
              {steps.map((step, idx) => {
                const stepNum = idx + 1;
                const isCompleted = currentStep > stepNum;
                const isActive = currentStep === stepNum;
                return (
                  <div
                    key={step.id}
                    className="flex items-center gap-2 sm:gap-4"
                  >
                    <button
                      type="button"
                      disabled={busy || loadingConfig}
                      onClick={() => {
                        if (stepNum === 1) {
                          setCurrentStep(1);
                        } else if (
                          stepNum === 2 &&
                          (currentStep === 1 || currentStep === 3)
                        ) {
                          setCurrentStep(2);
                        }
                      }}
                      className="flex items-center gap-2 cursor-pointer disabled:cursor-not-allowed transition-colors"
                    >
                      <div
                        className={cn(
                          'size-6 sm:size-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all',
                          isCompleted
                            ? 'bg-blue-600 text-white shadow-xs'
                            : isActive
                              ? 'bg-blue-600 text-white shadow-xs ring-2 ring-blue-600/20'
                              : 'bg-muted text-muted-foreground border border-border/60',
                        )}
                      >
                        {isCompleted ? (
                          <Check className="size-3.5 stroke-[2.5]" />
                        ) : (
                          stepNum
                        )}
                      </div>
                      <span
                        className={cn(
                          'text-xs sm:text-sm transition-colors',
                          isActive
                            ? 'font-medium text-blue-600 dark:text-blue-400'
                            : isCompleted
                              ? 'font-medium text-blue-600/80 dark:text-blue-400/80'
                              : 'text-muted-foreground',
                        )}
                      >
                        {step.title}
                      </span>
                    </button>
                    {idx < steps.length - 1 && (
                      <div
                        className={cn(
                          'w-8 sm:w-12 h-px transition-colors',
                          currentStep > stepNum ? 'bg-blue-600' : 'bg-border',
                        )}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Dialog Body Content */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4 border-t flex flex-col">
          {loadingConfig ? (
            <div className="flex flex-col items-center justify-center flex-1 py-12 gap-2 text-muted-foreground">
              <Loader2 className="size-6 animate-spin text-primary" />
              <span className="text-xs">{t('common.loading')}</span>
            </div>
          ) : loadError ? (
            <Alert className="border-red-500/40 bg-red-50/90 text-red-950 dark:border-red-500/40 dark:bg-red-950/40 dark:text-red-200 shadow-xs">
              <AlertTriangle className="size-4 text-red-600 dark:text-red-400 shrink-0" />
              <AlertTitle className="text-sm font-semibold text-red-950 dark:text-red-100">
                {t('plugins.spaceUpload.loadFailed')}
              </AlertTitle>
              <AlertDescription className="pt-2 flex items-center justify-between">
                <span className="text-xs text-red-900/90 dark:text-red-200/90">
                  无法获取插件上传配置信息，请检查后台服务连接。
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-red-500/30 bg-background/80 hover:bg-red-100/60 dark:hover:bg-red-900/40 text-red-950 dark:text-red-100 text-xs"
                  onClick={() => void loadConfig()}
                >
                  {t('common.retry')}
                </Button>
              </AlertDescription>
            </Alert>
          ) : !prerequisitesMet ? (
            /* Dedicated Prerequisites Gate Page */
            <div className="space-y-4 py-1">
              <Alert className="border-blue-500/30 bg-blue-50/60 text-blue-900 dark:border-blue-500/30 dark:bg-blue-950/30 dark:text-blue-200">
                <Sparkles className="size-4 text-blue-600 dark:text-blue-400" />
                <AlertTitle className="text-sm font-medium text-blue-950 dark:text-blue-100">
                  {t('plugins.spaceUpload.prerequisitesTitle')}
                </AlertTitle>
                <AlertDescription className="text-xs text-blue-800/85 dark:text-blue-300/85 leading-relaxed mt-1">
                  {t('plugins.spaceUpload.prerequisitesDescription')}
                </AlertDescription>
              </Alert>

              {/* Requirement 1: Space Account Binding */}
              {(() => {
                const isSpaceConnected = Boolean(config?.space_connected);
                return (
                  <Card
                    className={cn(
                      'transition-colors py-0 gap-0',
                      !isSpaceConnected &&
                        'border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20',
                    )}
                  >
                    <CardHeader className="flex flex-row items-center justify-between p-4 gap-4 space-y-0">
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className={cn(
                            'size-8 rounded-lg flex items-center justify-center shrink-0 text-xs mt-0.5',
                            isSpaceConnected
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
                          )}
                        >
                          {isSpaceConnected ? (
                            <Check className="size-4 stroke-[2.5]" />
                          ) : (
                            <AlertCircle className="size-4" />
                          )}
                        </div>
                        <div className="space-y-1 min-w-0">
                          <CardTitle className="text-sm font-medium">
                            {t('plugins.spaceUpload.req1Title')}
                          </CardTitle>
                          <CardDescription className="text-xs">
                            {t('plugins.spaceUpload.req1Desc')}
                          </CardDescription>
                        </div>
                      </div>

                      <div className="shrink-0">
                        {isSpaceConnected ? (
                          <Badge
                            variant="secondary"
                            className="text-xs text-emerald-600 dark:text-emerald-400 gap-1 font-normal"
                          >
                            <Check className="size-3 stroke-[2.5]" />
                            {t('plugins.spaceUpload.reqBound')}
                          </Badge>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleBindSpace}
                            disabled={bindingSpace}
                            className="gap-1.5"
                          >
                            {bindingSpace ? (
                              <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                              <ExternalLink className="size-3.5" />
                            )}
                            {t('plugins.spaceUpload.bindSpaceButton')}
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                  </Card>
                );
              })()}

              {/* Requirement 2: Creator Identity */}
              {(() => {
                const isCreatorReady = Boolean(config?.has_creator_profile);
                return (
                  <Card
                    className={cn(
                      'transition-colors py-0 gap-0',
                      !isCreatorReady &&
                        'border-amber-500/40 bg-amber-50/50 dark:bg-amber-950/20',
                    )}
                  >
                    <CardHeader className="flex flex-row items-center justify-between p-4 gap-4 space-y-0">
                      <div className="flex items-start gap-3 min-w-0">
                        <div
                          className={cn(
                            'size-8 rounded-lg flex items-center justify-center shrink-0 text-xs mt-0.5',
                            isCreatorReady
                              ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              : 'bg-amber-500/10 text-amber-600 dark:text-amber-400',
                          )}
                        >
                          {isCreatorReady ? (
                            <Check className="size-4 stroke-[2.5]" />
                          ) : (
                            <AlertCircle className="size-4" />
                          )}
                        </div>
                        <div className="space-y-1 min-w-0">
                          <CardTitle className="text-sm font-medium">
                            {t('plugins.spaceUpload.req2Title')}
                          </CardTitle>
                          <CardDescription className="text-xs">
                            {t('plugins.spaceUpload.req2Desc')}
                          </CardDescription>

                          {/* Status explanation */}
                          {!config?.space_connected ? (
                            <p className="text-xs text-muted-foreground flex items-center gap-1.5 pt-0.5">
                              <Info className="size-3.5 shrink-0" />
                              <span>
                                {t('plugins.spaceUpload.req2WaitSpace')}
                              </span>
                            </p>
                          ) : !config?.has_creator_profile ? (
                            <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1.5 pt-0.5">
                              <AlertCircle className="size-3.5 shrink-0" />
                              <span>
                                {t('plugins.spaceUpload.req2NoCreator')}
                              </span>
                            </p>
                          ) : (
                            <p className="text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 pt-0.5 font-mono">
                              <ShieldCheck className="size-3.5 shrink-0" />
                              <span>@{config?.creator_slug}</span>
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="shrink-0 mt-0.5">
                        {isCreatorReady ? (
                          <Badge
                            variant="secondary"
                            className="text-xs text-emerald-600 dark:text-emerald-400 gap-1 font-normal"
                          >
                            <Check className="size-3 stroke-[2.5]" />
                            {t('plugins.spaceUpload.reqCompleted')}
                          </Badge>
                        ) : !config?.space_connected ? (
                          <Badge
                            variant="secondary"
                            className="text-xs text-muted-foreground font-normal"
                          >
                            {t('plugins.spaceUpload.pendingReq')}
                          </Badge>
                        ) : !config?.has_creator_profile ? (
                          <Button
                            size="sm"
                            variant="outline"
                            asChild
                            className="gap-1.5"
                          >
                            <a
                              href={`${config?.cloud_service_url || 'https://space.langbot.app'}/creator`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <span>
                                {t('plugins.spaceUpload.createCreatorButton')}
                              </span>
                              <ExternalLink className="size-3.5" />
                            </a>
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            asChild
                            className="gap-1.5"
                          >
                            <a
                              href={`${config?.cloud_service_url || 'https://space.langbot.app'}/profile?tab=creator`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <span>
                                {t('plugins.spaceUpload.manageCreatorButton')}
                              </span>
                              <ExternalLink className="size-3.5" />
                            </a>
                          </Button>
                        )}
                      </div>
                    </CardHeader>
                  </Card>
                );
              })()}
            </div>
          ) : (
            <>
              {/* STEP 1: Plugin Card with Language Switcher + Changelog */}
              {currentStep === 1 && (
                <div className="space-y-3.5">
                  {/* Clean Section Header */}
                  <div className="flex items-center justify-between px-0.5">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                      <Sparkles className="size-3.5 text-blue-600 dark:text-blue-400" />
                      <span>{t('plugins.spaceUpload.stepInfo')}</span>
                      <span className="text-[11px] font-normal text-muted-foreground">
                        ({t('plugins.spaceUpload.manifestSource')})
                      </span>
                    </div>
                    <span className="text-[11px] text-muted-foreground hidden sm:inline">
                      点击下方语种切换实时预览
                    </span>
                  </div>

                  {/* Dedicated Full-Width Language Switcher Bar - Single clean line, never wraps */}
                  <div className="w-full flex items-center justify-between bg-muted/40 p-1 rounded-lg border border-border/70 overflow-hidden">
                    <div className="flex items-center gap-1.5 px-2.5 text-xs font-medium text-muted-foreground shrink-0">
                      <Globe className="size-3.5 text-blue-600 dark:text-blue-400" />
                      <span>多语言预览</span>
                    </div>
                    <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
                      {LOCALES.map((locale) => {
                        const hasTranslation = Boolean(
                          labelDraft[locale.code] ||
                          descriptionDraft[locale.code],
                        );
                        const isSelected = activeLocale === locale.code;
                        return (
                          <button
                            key={locale.code}
                            type="button"
                            onClick={() => setActiveLocale(locale.code)}
                            className={cn(
                              'inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs transition-all cursor-pointer select-none whitespace-nowrap shrink-0',
                              isSelected
                                ? 'bg-background text-foreground font-semibold shadow-xs border border-border/80 text-blue-600 dark:text-blue-400'
                                : 'text-muted-foreground hover:text-foreground hover:bg-background/40',
                              !hasTranslation && !isSelected && 'opacity-60',
                            )}
                          >
                            {hasTranslation && (
                              <span
                                className={cn(
                                  'size-1.5 rounded-full shrink-0',
                                  isSelected
                                    ? 'bg-blue-600 dark:bg-blue-400'
                                    : 'bg-blue-500/60',
                                )}
                              />
                            )}
                            <span>{locale.label}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Plugin Card with Fixed-Height Layout: Zero Jitter on Language Switch */}
                  <div className="w-full bg-card rounded-xl border border-border/80 shadow-xs p-4 sm:p-4.5 flex flex-col justify-between min-h-[178px]">
                    <div className="flex items-start gap-3.5">
                      {/* Plugin Icon */}
                      <div className="relative shrink-0">
                        {authenticatedIcon.url && !iconFailed ? (
                          <img
                            src={authenticatedIcon.url}
                            alt="plugin icon"
                            className="size-15 rounded-xl border border-border/60 bg-muted/20 object-cover shadow-xs"
                            onError={() => setIconFailed(true)}
                          />
                        ) : (
                          <div className="size-15 rounded-xl border border-border/60 bg-muted/30 flex items-center justify-center text-muted-foreground shadow-xs">
                            <Puzzle className="size-7 text-blue-500/70" />
                          </div>
                        )}
                      </div>

                      {/* Plugin Card Details */}
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center justify-between text-[0.72rem] font-mono text-muted-foreground">
                          <span className="truncate">
                            {author} / {name}
                          </span>
                          <span className="text-[10px] text-muted-foreground/70 font-sans">
                            {LOCALES.find((l) => l.code === activeLocale)
                              ?.label || activeLocale}
                          </span>
                        </div>

                        {/* Title and Badges: Fixed single line, no vertical shift */}
                        <div className="h-6 flex items-center gap-2">
                          <h3
                            className="text-base font-bold text-foreground leading-none truncate max-w-[280px] sm:max-w-[340px]"
                            title={displayName}
                          >
                            {displayName}
                          </h3>
                          <Badge
                            variant="secondary"
                            className="font-mono text-[10px] font-semibold px-1.5 py-0 bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 shrink-0"
                          >
                            v{version || '0.1.0'}
                          </Badge>
                          <Badge
                            variant="outline"
                            className="text-[10px] border-blue-200 bg-blue-50/60 text-blue-700 dark:border-blue-500/40 dark:bg-blue-500/10 dark:text-blue-300 gap-1 shrink-0 px-1.5 py-0"
                          >
                            <Puzzle className="size-2.5" />
                            {t('market.typePlugin', '插件')}
                          </Badge>
                          {license && (
                            <Badge
                              variant="outline"
                              className="text-[10px] shrink-0 px-1.5 py-0"
                            >
                              {license}
                            </Badge>
                          )}
                        </div>

                        {/* Description: Fixed 3-line height box so switching locales never causes height jump */}
                        <div className="h-[3.6rem] overflow-hidden pt-0.5">
                          <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3 whitespace-pre-wrap">
                            {displayDescription || (
                              <span className="italic text-muted-foreground/50">
                                {t(
                                  'plugins.spaceUpload.noDescription',
                                  '（该语言暂无描述）',
                                )}
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Card Meta Sub-row: Fixed height */}
                    <div className="flex items-center justify-between gap-x-4 pt-2.5 mt-2.5 border-t text-xs text-muted-foreground h-7">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="truncate">
                          {t('plugins.spaceUpload.author')}:{' '}
                          <strong className="font-medium text-foreground">
                            {authorName}
                          </strong>
                        </span>
                        {repository && (
                          <a
                            href={repository}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-primary hover:underline truncate"
                          >
                            <span className="truncate max-w-[200px]">
                              {repository}
                            </span>
                            <ExternalLink className="size-3 shrink-0" />
                          </a>
                        )}
                      </div>
                      <div className="text-[11px] text-muted-foreground/80 font-mono shrink-0 flex items-center gap-1.5">
                        <span className="size-1.5 rounded-full bg-blue-500" />
                        <span>{activeLocale}</span>
                      </div>
                    </div>
                  </div>

                  {/* Changelog Input directly in Step 1 */}
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center justify-between shrink-0">
                      <Label
                        htmlFor="space-upload-changelog"
                        className="text-xs font-semibold flex items-center gap-1.5"
                      >
                        <span>{t('plugins.spaceUpload.changelog')}</span>
                        <span className="text-[11px] text-muted-foreground font-normal">
                          ({t('common.optional', '可选')})
                        </span>
                      </Label>
                      <span className="text-[11px] text-muted-foreground">
                        {t('plugins.spaceUpload.changelogHint')}
                      </span>
                    </div>
                    <Textarea
                      id="space-upload-changelog"
                      value={changelog}
                      onChange={(e) => setChangelog(e.target.value)}
                      placeholder={t(
                        'plugins.spaceUpload.changelogPlaceholder',
                      )}
                      className="min-h-[7.5rem] resize-none text-xs leading-relaxed"
                      disabled={busy}
                    />
                  </div>
                </div>
              )}

              {/* STEP 2: Confirmation & Pre-flight Review */}
              {currentStep === 2 && (
                <div className="space-y-4">
                  {/* Author Mismatch Warning Banner (Yellow) */}
                  {!config?.author_matches && (
                    <Alert className="border-amber-500/40 bg-amber-50/90 text-amber-950 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-200 shadow-xs">
                      <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400 shrink-0" />
                      <AlertTitle className="text-sm font-semibold text-amber-950 dark:text-amber-100">
                        {t('plugins.spaceUpload.banners.authorMismatch.title')}
                      </AlertTitle>
                      <AlertDescription className="space-y-3 pt-1 text-amber-950 dark:text-amber-200">
                        <p className="text-xs text-amber-900/90 dark:text-amber-200/90 leading-relaxed">
                          {t(
                            'plugins.spaceUpload.banners.authorMismatch.description',
                            {
                              author: config?.metadata?.author || author,
                              creator: config?.creator_slug || '',
                            },
                          )}
                        </p>
                        <div className="rounded-md bg-amber-100/75 dark:bg-amber-900/35 border border-amber-500/30 p-2.5 text-xs text-amber-950 dark:text-amber-100 space-y-1">
                          <span className="font-medium text-xs block text-amber-900 dark:text-amber-200">
                            {t('plugins.spaceUpload.banners.guideTitle')}
                          </span>
                          <div className="leading-relaxed whitespace-pre-wrap text-amber-900/95 dark:text-amber-100">
                            {t(
                              'plugins.spaceUpload.banners.authorMismatch.guide',
                              {
                                author: config?.metadata?.author || author,
                                creator: config?.creator_slug || '',
                              },
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2 pt-1 justify-end">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="gap-1.5 text-xs border-amber-500/30 bg-background/80 hover:bg-amber-100/60 dark:hover:bg-amber-900/40"
                            asChild
                          >
                            <a
                              href={`${config?.cloud_service_url || 'https://space.langbot.app'}/profile?tab=creator`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <span>
                                {t(
                                  'plugins.spaceUpload.banners.manageCreatorButton',
                                )}
                              </span>
                              <ExternalLink className="size-3.5" />
                            </a>
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="gap-1 text-xs border-amber-500/30 bg-background/80 hover:bg-amber-100/60 dark:hover:bg-amber-900/40"
                            onClick={() => void loadConfig()}
                            disabled={loadingConfig}
                          >
                            <RefreshCw
                              className={cn(
                                'size-3',
                                loadingConfig && 'animate-spin',
                              )}
                            />
                            {t('plugins.spaceUpload.banners.refreshButton')}
                          </Button>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Ready Notice if Author Matches */}
                  {prerequisitesMet && config?.author_matches && (
                    <Alert className="border-emerald-500/30 bg-emerald-50/40 text-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-300">
                      <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                      <AlertTitle className="text-sm font-medium text-foreground">
                        {t('plugins.spaceUpload.banners.readyToUpload.title')}
                      </AlertTitle>
                      <AlertDescription className="text-xs text-muted-foreground mt-0.5">
                        {t(
                          'plugins.spaceUpload.banners.readyToUpload.description',
                        )}
                      </AlertDescription>
                    </Alert>
                  )}

                  {/* Pre-flight Review Checklist Card */}
                  <Card className="p-4 gap-3.5 py-4">
                    <CardHeader className="p-0 space-y-0">
                      <CardTitle className="text-sm font-semibold flex items-center gap-2">
                        <CheckCircle2 className="size-4 text-primary" />
                        {t('plugins.spaceUpload.reviewSummaryTitle')}
                      </CardTitle>
                    </CardHeader>

                    <CardContent className="p-0 space-y-3.5">
                      <div className="grid grid-cols-2 gap-3 text-xs pt-1 border-t">
                        <div>
                          <span className="text-muted-foreground block">
                            {t('plugins.spaceUpload.label')}
                          </span>
                          <span className="font-medium text-foreground">
                            {displayName}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block">
                            {t('plugins.spaceUpload.version')}
                          </span>
                          <span className="font-mono font-medium text-foreground">
                            v{version || '0.1.0'}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block">
                            {t('plugins.spaceUpload.pluginIdentifier')}
                          </span>
                          <span className="font-mono text-foreground">
                            {author}/{name}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block">
                            {t('plugins.spaceUpload.reviewTargetMarket')}
                          </span>
                          <span className="font-medium text-primary">
                            {t('plugins.spaceUpload.reviewTargetMarketValue')}
                          </span>
                        </div>
                      </div>

                      <div className="space-y-2 pt-2 border-t text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">
                            {t('plugins.spaceUpload.reviewAccountStatus')}
                          </span>
                          {config?.space_connected ? (
                            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                              <Check className="size-3.5" />
                              {t('plugins.spaceUpload.reviewAccountConnected')}
                              {config.creator_slug &&
                                ` (@${config.creator_slug})`}
                            </span>
                          ) : (
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium">
                                <AlertTriangle className="size-3.5" />
                                {t(
                                  'plugins.spaceUpload.reviewAccountNotConnected',
                                )}
                              </span>
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                className="h-6 px-2 text-xs"
                                onClick={handleBindSpace}
                                disabled={bindingSpace}
                              >
                                {t('plugins.spaceUpload.bindSpaceButton')}
                              </Button>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t text-xs">
                        <span className="text-muted-foreground block">
                          {t('plugins.spaceUpload.reviewChangelog')}
                        </span>
                        {changelog.trim() ? (
                          <div className="rounded-md bg-muted/40 p-2.5 font-sans whitespace-pre-wrap text-foreground max-h-36 overflow-y-auto">
                            {changelog.trim()}
                          </div>
                        ) : (
                          <span className="italic text-muted-foreground">
                            {t('plugins.spaceUpload.reviewChangelogEmpty')}
                          </span>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* STEP 3: Upload Progress & Result Display */}
              {currentStep === 3 && (
                <div className="flex-1 flex flex-col items-center justify-center py-8 px-4">
                  {/* In-Flight Uploading State: Clean & Minimal Progress Bar */}
                  {uploadStatus === 'uploading' && (
                    <div className="w-full max-w-sm mx-auto text-center space-y-4">
                      <div className="space-y-1.5">
                        <h3 className="text-sm font-semibold text-foreground">
                          {t(
                            'plugins.spaceUpload.uploadingTitle',
                            '正在发布插件至 Space',
                          )}
                        </h3>
                        <p className="text-xs text-muted-foreground">
                          正在上传包体与清单元数据，请稍候...
                        </p>
                      </div>

                      <div className="w-full space-y-2 pt-1">
                        <Progress
                          value={uploadProgress}
                          className="h-1.5 w-full bg-muted"
                        />
                        <div className="flex justify-between text-[11px] font-mono text-muted-foreground px-0.5">
                          <span>上传进度</span>
                          <span>{uploadProgress}%</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Success State: Clean & Concise */}
                  {uploadStatus === 'success' && (
                    <div className="w-full max-w-sm mx-auto text-center space-y-4">
                      <div className="size-12 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto">
                        <Check className="size-6 stroke-[2.5]" />
                      </div>

                      <div className="space-y-1">
                        <h3 className="text-base font-semibold text-foreground">
                          {t(
                            'plugins.spaceUpload.uploadSuccessTitle',
                            '发布成功，已提交审核',
                          )}
                        </h3>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          插件版本 v{version || '0.1.0'} 已同步至
                          Space，审核通过后将自动上架。
                        </p>
                      </div>

                      <div className="flex items-center justify-center gap-2.5 pt-2">
                        <Button
                          type="button"
                          size="sm"
                          className="text-xs gap-1.5 bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                          onClick={() => {
                            const spaceBase =
                              config?.cloud_service_url ||
                              'https://space.langbot.app';
                            window.open(
                              `${spaceBase}/market`,
                              '_blank',
                              'noopener',
                            );
                          }}
                        >
                          <span>前往扩展市场查看</span>
                          <ExternalLink className="size-3.5" />
                        </Button>

                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="text-xs"
                          onClick={() => {
                            onUploaded?.();
                            onOpenChange(false);
                          }}
                        >
                          {t('common.finish', '完成')}
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Error State: Concise & Minimal, NO nested boxes */}
                  {uploadStatus === 'error' && uploadError && (
                    <div className="w-full max-w-sm mx-auto text-center space-y-4">
                      <div
                        className={cn(
                          'size-12 rounded-full flex items-center justify-center mx-auto',
                          uploadError.type === 'pendingReview'
                            ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                            : 'bg-red-500/10 text-red-600 dark:text-red-400',
                        )}
                      >
                        {uploadError.type === 'pendingReview' ? (
                          <AlertTriangle className="size-6" />
                        ) : (
                          <AlertCircle className="size-6" />
                        )}
                      </div>

                      <div className="space-y-1.5">
                        <h3 className="text-base font-semibold text-foreground">
                          {uploadError.type === 'pendingReview'
                            ? '该插件已有版本正在审核中'
                            : uploadError.type === 'sessionExpired'
                              ? 'Space 登录状态已失效'
                              : uploadError.type === 'noCreator'
                                ? '未设置创作者身份'
                                : uploadError.type === 'authorMismatch'
                                  ? '插件作者与创作者不匹配'
                                  : '发布失败'}
                        </h3>
                        <p className="text-xs text-muted-foreground leading-relaxed px-2">
                          {uploadError.type === 'pendingReview'
                            ? '当前插件已有版本处于审核中，需等待审核完成后方可提交新版本。'
                            : uploadError.type === 'sessionExpired'
                              ? '您的登录凭据已过期，请重新登录 Space 后重试。'
                              : uploadError.type === 'noCreator'
                                ? '请先在 Space 设置创作者标识后再发布插件。'
                                : uploadError.type === 'authorMismatch'
                                  ? `manifest 中的 author (${uploadError.author || author}) 与 Space 创作者标识不一致。`
                                  : uploadError.detail ||
                                    '上传过程中遇到错误，请检查后重试。'}
                        </p>
                      </div>

                      <div className="flex items-center justify-center gap-2 pt-2">
                        {uploadError.type === 'pendingReview' ? (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              className="text-xs gap-1.5 bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                              asChild
                            >
                              <a
                                href={`${config?.cloud_service_url || 'https://space.langbot.app'}/market`}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <span>前往扩展市场查看</span>
                                <ExternalLink className="size-3.5" />
                              </a>
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="text-xs"
                              onClick={() => onOpenChange(false)}
                            >
                              {t('common.close', '关闭')}
                            </Button>
                          </>
                        ) : uploadError.type === 'sessionExpired' ? (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              className="text-xs gap-1.5 bg-blue-600 hover:bg-blue-700 text-white shadow-xs"
                              onClick={handleBindSpace}
                              disabled={bindingSpace}
                            >
                              <span>重新登录 Space</span>
                              <ExternalLink className="size-3.5" />
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="text-xs"
                              onClick={() => onOpenChange(false)}
                            >
                              {t('common.close', '关闭')}
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="text-xs"
                              onClick={() => setCurrentStep(2)}
                            >
                              {t('plugins.spaceUpload.backToEdit', '返回修改')}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              className="text-xs bg-red-600 hover:bg-red-700 text-white shadow-xs"
                              onClick={handleStartUpload}
                              disabled={submitting}
                            >
                              {t('plugins.spaceUpload.retryUpload', '重试上传')}
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Dialog Footer */}
        <DialogFooter className="px-6 py-3 border-t bg-muted/10 shrink-0">
          {!prerequisitesMet && !loadingConfig && !loadError ? (
            <div className="flex items-center justify-end w-full gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => onOpenChange(false)}
                disabled={busy}
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => void loadConfig()}
                disabled={busy || loadingConfig}
                className="gap-1.5"
              >
                <RefreshCw
                  className={cn('size-3.5', loadingConfig && 'animate-spin')}
                />
                {t('plugins.spaceUpload.refreshStatus')}
              </Button>
            </div>
          ) : currentStep === 3 ? (
            <div className="flex items-center justify-between w-full text-xs text-muted-foreground">
              <span className="text-[11px] text-muted-foreground">
                {uploadStatus === 'uploading'
                  ? '正在与 Space 扩展市场同步，请稍候...'
                  : ''}
              </span>
              {uploadStatus !== 'uploading' && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-xs text-muted-foreground hover:text-foreground"
                  onClick={() => {
                    if (uploadStatus === 'success') onUploaded?.();
                    onOpenChange(false);
                  }}
                >
                  {t('common.close', '关闭')}
                </Button>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-between w-full">
              <div>
                {currentStep === 2 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentStep(1)}
                    disabled={busy}
                  >
                    <ArrowLeft className="mr-1.5 size-4" />
                    {t('plugins.spaceUpload.prevStep')}
                  </Button>
                )}
              </div>

              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  disabled={busy}
                >
                  {t('common.cancel')}
                </Button>

                {currentStep === 1 && (
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => setCurrentStep(2)}
                    disabled={busy || loadingConfig || loadError}
                  >
                    {t('plugins.spaceUpload.nextToConfirm')}
                    <ArrowRight className="ml-1.5 size-4" />
                  </Button>
                )}

                {currentStep === 2 && (
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleStartUpload}
                    disabled={!canSubmit}
                    title={
                      !canSubmit
                        ? t('plugins.spaceUpload.banners.disabledTooltip')
                        : undefined
                    }
                    className="gap-1.5 bg-blue-600 hover:bg-blue-700 text-white"
                  >
                    <Upload className="size-4" />
                    {t('plugins.spaceUpload.startUpload')}
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
