import { ReactNode, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  ShieldAlert,
  Upload,
} from 'lucide-react';
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
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Checkbox } from '@/components/ui/checkbox';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  ContentSubmissionResult,
  ShareFinding,
  ShareMetadata,
  SpaceShareContext,
} from '@/app/infra/entities/space-share';

export function slugifyShareName(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
  return slug.length >= 2 ? slug : '';
}

export function FindingsList({ findings }: { findings: ShareFinding[] }) {
  const { t } = useTranslation();
  if (findings.length === 0) return null;
  const blocking = findings.some((f) => f.severity === 'block');
  return (
    <Alert variant={blocking ? 'destructive' : 'default'}>
      {blocking ? (
        <ShieldAlert className="size-4" />
      ) : (
        <AlertTriangle className="size-4" />
      )}
      <AlertTitle>
        {blocking
          ? t('spaceShare.findingsBlockTitle')
          : t('spaceShare.findingsWarnTitle')}
      </AlertTitle>
      <AlertDescription>
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
          {findings.slice(0, 8).map((f, i) => (
            <li key={i}>
              <code>{f.where}</code> · {t(`spaceShare.finding.${f.kind}`)} ·{' '}
              <code>{f.excerpt}</code>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}

/**
 * Shared shell for "Share to LangBot Space" (LANG-439): checks the bound
 * LangBot Account and creator profile, collects the listing metadata, shows
 * the type-specific preview and submits for review.
 */
export default function ShareToSpaceDialog({
  open,
  onOpenChange,
  title,
  description,
  defaultName,
  defaultLabel,
  defaultDescription,
  findings = [],
  canSubmit = true,
  showChangelog = false,
  children,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  defaultName: string;
  defaultLabel: string;
  defaultDescription: string;
  findings?: ShareFinding[];
  canSubmit?: boolean;
  showChangelog?: boolean;
  children?: ReactNode;
  onSubmit: (
    meta: ShareMetadata,
    acknowledgeWarnings: boolean,
  ) => Promise<ContentSubmissionResult>;
}) {
  const { t, i18n } = useTranslation();
  const [ctx, setCtx] = useState<SpaceShareContext | null>(null);
  const [ctxLoading, setCtxLoading] = useState(false);
  const [name, setName] = useState('');
  const [label, setLabel] = useState('');
  const [desc, setDesc] = useState('');
  const [tags, setTags] = useState('');
  const [changelog, setChangelog] = useState('');
  const [ack, setAck] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ContentSubmissionResult | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(slugifyShareName(defaultName));
    setLabel(defaultLabel);
    setDesc(defaultDescription);
    setTags('');
    setChangelog('');
    setAck(false);
    setError('');
    setResult(null);
    setCtxLoading(true);
    httpClient
      .getSpaceShareContext()
      .then(setCtx)
      .catch(() => setCtx(null))
      .finally(() => setCtxLoading(false));
  }, [open, defaultName, defaultLabel, defaultDescription]);

  const locale = (i18n.language || 'en_US').replace('-', '_');
  const blocking = findings.some((f) => f.severity === 'block');
  const warns = findings.some((f) => f.severity === 'warn');
  const ready =
    !!ctx?.space_connected &&
    !!ctx?.has_creator_profile &&
    canSubmit &&
    !blocking &&
    (!warns || ack) &&
    /^[a-z0-9][a-z0-9_-]{1,63}$/.test(name) &&
    label.trim() !== '' &&
    desc.trim() !== '';

  const submit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const meta: ShareMetadata = {
        name,
        label: { [locale]: label.trim() },
        description: { [locale]: desc.trim() },
        tags: tags
          .split(/[,，]/)
          .map((s) => s.trim())
          .filter(Boolean),
        changelog: changelog.trim(),
      };
      setResult(await onSubmit(meta, ack));
    } catch (e) {
      setError((e as { msg?: string })?.msg || t('spaceShare.submitFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  const reviewURL = `${ctx?.space_web_url || 'https://space.langbot.app'}/profile?tab=myContent`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[min(720px,94vw)] max-w-none overflow-y-auto sm:max-w-none">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="size-4" />
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="flex flex-col items-center gap-3 py-6 text-center">
            <CheckCircle2 className="size-10 text-emerald-500" />
            <div className="font-medium">{t('spaceShare.submittedTitle')}</div>
            <div className="text-sm text-muted-foreground">
              {result.agent_review
                ? t('spaceShare.submittedAgentReview', {
                    id: result.submission.item_id,
                  })
                : t('spaceShare.submittedManualReview', {
                    id: result.submission.item_id,
                  })}
            </div>
            <Button asChild variant="outline">
              <a href={reviewURL} target="_blank" rel="noreferrer">
                {t('spaceShare.viewProgress')}
                <ExternalLink className="ml-1 size-3.5" />
              </a>
            </Button>
          </div>
        ) : ctxLoading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : !ctx?.space_connected ? (
          <Alert>
            <AlertTriangle className="size-4" />
            <AlertTitle>{t('spaceShare.needAccountTitle')}</AlertTitle>
            <AlertDescription>{t('spaceShare.needAccount')}</AlertDescription>
          </Alert>
        ) : !ctx.has_creator_profile ? (
          <Alert>
            <AlertTriangle className="size-4" />
            <AlertTitle>{t('spaceShare.needCreatorTitle')}</AlertTitle>
            <AlertDescription>
              {t('spaceShare.needCreator')}{' '}
              <a
                className="underline"
                href={`${ctx.space_web_url}/profile?tab=creator`}
                target="_blank"
                rel="noreferrer"
              >
                {t('spaceShare.openCreator')}
              </a>
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-4">
            {children}
            <FindingsList findings={findings} />
            {warns && !blocking && (
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={ack}
                  onCheckedChange={(v) => setAck(v === true)}
                />
                {t('spaceShare.acknowledgeWarnings')}
              </label>
            )}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>{t('spaceShare.displayName')}</Label>
                <Input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label>{t('spaceShare.identifier')}</Label>
                <div className="flex items-center rounded-md border bg-muted/30 pl-2 text-sm text-muted-foreground">
                  <span className="shrink-0">@{ctx.creator_slug}/</span>
                  <Input
                    className="border-0 bg-transparent pl-0.5 shadow-none focus-visible:ring-0"
                    value={name}
                    onChange={(e) => setName(e.target.value.toLowerCase())}
                  />
                </div>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>{t('spaceShare.descriptionLabel')}</Label>
              <Textarea
                rows={2}
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t('spaceShare.tags')}</Label>
              <Input
                value={tags}
                placeholder={t('spaceShare.tagsPlaceholder')}
                onChange={(e) => setTags(e.target.value)}
              />
            </div>
            {showChangelog && (
              <div className="space-y-1.5">
                <Label>{t('spaceShare.changelog')}</Label>
                <Textarea
                  rows={2}
                  value={changelog}
                  onChange={(e) => setChangelog(e.target.value)}
                />
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              {t('spaceShare.reviewNotice')}
            </p>
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {!result && (
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              disabled={!ready || submitting}
              onClick={() => void submit()}
            >
              {submitting && <Loader2 className="mr-1 size-4 animate-spin" />}
              {t('spaceShare.submit')}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
