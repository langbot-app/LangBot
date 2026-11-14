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
import { useSpaceBind } from './useSpaceBind';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type {
  ContentSubmissionResult,
  ShareFinding,
  ShareMetadata,
  SpaceShareContext,
  SpaceOwnedItem,
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
  itemType,
  promptKind,
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
  /** Type being shared; lists the account's existing items of this type. */
  itemType: SpaceOwnedItem['item_type'];
  /** For prompts: only offer existing prompts of the same kind. */
  promptKind?: string;
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
  const [changelog, setChangelog] = useState('');
  const [ack, setAck] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ContentSubmissionResult | null>(null);
  const { bind: bindAccount, binding } = useSpaceBind();
  // Publish as a new item, or as a new version of one already published.
  const [mode, setMode] = useState<'new' | 'update'>('new');
  const [owned, setOwned] = useState<SpaceOwnedItem[]>([]);
  const [target, setTarget] = useState<SpaceOwnedItem | null>(null);

  useEffect(() => {
    if (!open) return;
    setName(slugifyShareName(defaultName));
    setLabel(defaultLabel);
    setDesc(defaultDescription);
    setChangelog('');
    setAck(false);
    setError('');
    setResult(null);
    setCtxLoading(true);
    setMode('new');
    setTarget(null);
    setOwned([]);
    httpClient
      .getSpaceShareContext()
      .then(async (c) => {
        setCtx(c);
        if (!c?.space_connected || !c.has_creator_profile) return;
        const res = await httpClient
          .listMySpaceItems(itemType)
          .catch(() => ({ items: [] as SpaceOwnedItem[] }));
        const items = (res.items || []).filter(
          (it) => !promptKind || !it.kind || it.kind === promptKind,
        );
        setOwned(items);
        // Sharing something that already has a published twin (same
        // identifier) most likely means updating it.
        const twin = items.find(
          (it) => it.name === slugifyShareName(defaultName),
        );
        if (twin) pickTarget(twin);
      })
      .catch(() => setCtx(null))
      .finally(() => setCtxLoading(false));
    // pickTarget only sets state; it is stable for this effect's purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    open,
    defaultName,
    defaultLabel,
    defaultDescription,
    itemType,
    promptKind,
  ]);

  const locale = (i18n.language || 'en_US').replace('-', '_');
  const pickText = (obj: Record<string, string>) =>
    obj[locale] ||
    obj.en_US ||
    obj.zh_Hans ||
    Object.values(obj).find((v) => v && v.trim()) ||
    '';

  function pickTarget(it: SpaceOwnedItem) {
    setMode('update');
    setTarget(it);
    setName(it.name);
    setLabel(pickText(it.label || {}) || it.name);
    setDesc(pickText(it.description || {}));
  }

  const switchMode = (next: 'new' | 'update') => {
    if (next === mode) return;
    if (next === 'update' && owned.length > 0) {
      pickTarget(target || owned[0]);
      return;
    }
    setMode('new');
    setTarget(null);
    setName(slugifyShareName(defaultName));
    setLabel(defaultLabel);
    setDesc(defaultDescription);
  };
  const blocking = findings.some((f) => f.severity === 'block');
  const warns = findings.some((f) => f.severity === 'warn');
  const ready =
    !!ctx?.space_connected &&
    !!ctx?.has_creator_profile &&
    canSubmit &&
    !blocking &&
    (!warns || ack) &&
    (mode === 'new' || !!target) &&
    /^[a-z0-9][a-z0-9_-]{1,63}$/.test(name) &&
    label.trim() !== '' &&
    desc.trim() !== '';

  const submit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const meta: ShareMetadata = {
        name,
        // Updates keep the item's other languages and replace this one.
        label: { ...(target?.label || {}), [locale]: label.trim() },
        description: { ...(target?.description || {}), [locale]: desc.trim() },
        // Contributors don't tag; Space assigns tags during review.
        tags: [],
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
            <AlertDescription>
              <p>{t('spaceShare.needAccount')}</p>
              <Button
                size="sm"
                className="mt-2"
                disabled={binding}
                onClick={() => void bindAccount()}
              >
                {binding ? (
                  <Loader2 className="mr-1 size-3.5 animate-spin" />
                ) : (
                  <ExternalLink className="mr-1 size-3.5" />
                )}
                {t('spaceShare.bindAccount')}
              </Button>
            </AlertDescription>
          </Alert>
        ) : !ctx.has_creator_profile ? (
          <Alert>
            <AlertTriangle className="size-4" />
            <AlertTitle>{t('spaceShare.needCreatorTitle')}</AlertTitle>
            <AlertDescription>
              <p>{t('spaceShare.needCreator')}</p>
              <Button asChild size="sm" variant="outline" className="mt-2">
                <a
                  href={`${ctx.space_web_url}/profile?tab=creator`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('spaceShare.openCreator')}
                  <ExternalLink className="ml-1 size-3.5" />
                </a>
              </Button>
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
            {owned.length > 0 && (
              <div className="space-y-2">
                <ToggleGroup
                  type="single"
                  variant="outline"
                  size="sm"
                  value={mode}
                  onValueChange={(v) => v && switchMode(v as 'new' | 'update')}
                >
                  <ToggleGroupItem value="new" className="px-3">
                    {t('spaceShare.modeNew')}
                  </ToggleGroupItem>
                  <ToggleGroupItem value="update" className="px-3">
                    {t('spaceShare.modeUpdate', { count: owned.length })}
                  </ToggleGroupItem>
                </ToggleGroup>
                {mode === 'update' && (
                  <Select
                    value={target?.item_id}
                    onValueChange={(id) => {
                      const it = owned.find((x) => x.item_id === id);
                      if (it) pickTarget(it);
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder={t('spaceShare.pickExisting')} />
                    </SelectTrigger>
                    <SelectContent>
                      {owned.map((it) => (
                        <SelectItem key={it.item_id} value={it.item_id}>
                          <span className="truncate">
                            {pickText(it.label || {}) || it.name}
                          </span>
                          <span className="ml-2 font-mono text-xs text-muted-foreground">
                            @{it.item_id} · v{it.version}
                            {it.status === 'unlisted'
                              ? ` · ${t('spaceShare.unlisted')}`
                              : ''}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
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
                {mode === 'update' ? (
                  <div className="flex h-9 items-center rounded-md border bg-muted/40 px-3 font-mono text-sm text-muted-foreground">
                    @{ctx.creator_slug}/{name}
                    <span className="ml-auto pl-2 font-sans text-xs">
                      v{target ? target.version + 1 : ''}
                    </span>
                  </div>
                ) : (
                  <>
                    {/* Looks and behaves like a normal input; the creator
                        prefix is fixed, the name after it is editable. */}
                    <div className="flex h-9 items-center rounded-md border border-input bg-background text-sm shadow-xs transition-[color,box-shadow] focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50">
                      <span className="shrink-0 select-none pl-3 font-mono text-muted-foreground">
                        @{ctx.creator_slug}/
                      </span>
                      <Input
                        className="h-full min-w-0 flex-1 rounded-none border-0 bg-transparent pl-0 font-mono shadow-none focus-visible:ring-0 dark:bg-transparent"
                        value={name}
                        placeholder="my-prompt"
                        onChange={(e) => setName(e.target.value.toLowerCase())}
                      />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {t('spaceShare.identifierHint')}
                    </p>
                  </>
                )}
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
            {(showChangelog || mode === 'update') && (
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
              {t('spaceShare.autoTranslateNotice')}{' '}
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
