import { Fragment, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import i18n from 'i18next';
import { ArrowRight, ChevronDown, ExternalLink } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import '@/styles/github-markdown.css';
import { GitHubRelease } from '@/app/infra/http/CloudServiceClient';
import {
  CHANGELOG_TYPE_ORDER,
  type ChangelogChangeType,
  type ChangelogLocale,
  type ChangelogRelease,
  changelogLocaleFor,
  changelogPageUrl,
  pickChangelogText,
} from '@/app/infra/http/LangBotChangelog';
import {
  coreReleaseOf,
  isCoreUpdate,
  parseCoreVersion,
} from '@/app/utils/coreVersion';

const COLLAPSED_RELEASE_COUNT = 3;

// Same palette as the changelog on langbot.app.
const TYPE_STYLES: Record<ChangelogChangeType, string> = {
  new: 'bg-blue-50 text-blue-600 ring-blue-100 dark:bg-blue-900/30 dark:text-blue-400 dark:ring-blue-900/50',
  improved:
    'bg-emerald-50 text-emerald-600 ring-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400 dark:ring-emerald-900/50',
  changed:
    'bg-amber-50 text-amber-700 ring-amber-100 dark:bg-amber-900/30 dark:text-amber-400 dark:ring-amber-900/50',
  fixed:
    'bg-slate-100 text-slate-600 ring-slate-200 dark:bg-neutral-800 dark:text-slate-300 dark:ring-neutral-700',
  security:
    'bg-rose-50 text-rose-600 ring-rose-100 dark:bg-rose-900/30 dark:text-rose-400 dark:ring-rose-900/50',
};

function stripV(version: string | undefined) {
  return (version ?? '').replace(/^v/, '');
}

/** Render `inline code` spans; the changelog has no other markup. */
function InlineText({ text }: { text: string }) {
  const parts = text.split('`');
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <code
            key={i}
            className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]"
          >
            {part}
          </code>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function ReleaseSection({
  release,
  locale,
  isLatest,
  isCurrent,
}: {
  release: ChangelogRelease;
  locale: ChangelogLocale;
  isLatest: boolean;
  isCurrent: boolean;
}) {
  const { t } = useTranslation();
  const summary = pickChangelogText(release.summary, locale);
  const items = [...release.items].sort(
    (a, b) =>
      CHANGELOG_TYPE_ORDER.indexOf(a.type) -
      CHANGELOG_TYPE_ORDER.indexOf(b.type),
  );

  return (
    <section className="space-y-4">
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-sm font-semibold">
            v{release.version}
          </h3>
          {isLatest && (
            <Badge variant="secondary" className="h-5 px-1.5 text-[0.65rem]">
              {t('version.latestBadge')}
            </Badge>
          )}
          {isCurrent && (
            <Badge variant="outline" className="h-5 px-1.5 text-[0.65rem]">
              {t('version.currentBadge')}
            </Badge>
          )}
          <span className="text-xs text-muted-foreground">{release.date}</span>
          <a
            href={changelogPageUrl(locale, release.version)}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            {t('version.viewOnWebsite')}
            <ExternalLink className="size-3" />
          </a>
        </div>
        {summary && (
          <p className="text-sm leading-relaxed text-muted-foreground">
            <InlineText text={summary} />
          </p>
        )}
      </div>
      <ul className="space-y-2.5">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-3 text-sm leading-6">
            <span
              className={cn(
                'mt-0.5 inline-flex min-w-[4.5rem] shrink-0 justify-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] leading-5 font-semibold ring-1 ring-inset',
                TYPE_STYLES[item.type],
              )}
            >
              {t(`version.changeTypes.${item.type}`)}
            </span>
            <span className="text-foreground/80">
              <InlineText text={pickChangelogText(item.text, locale)} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

interface NewVersionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Running Core version, e.g. "v4.11.6". */
  currentVersion?: string;
  /** Stable releases from langbot.app/changelog.json, newest first. */
  releases: ChangelogRelease[];
  /**
   * GitHub release used only when the langbot.app feed is unreachable, so
   * the update prompt still has something to show.
   */
  fallbackRelease?: GitHubRelease | null;
}

export default function NewVersionDialog({
  open,
  onOpenChange,
  currentVersion,
  releases,
  fallbackRelease,
}: NewVersionDialogProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const locale = changelogLocaleFor(i18n.language);
  const current = stripV(currentVersion);

  const pending = useMemo(
    () => releases.filter((r) => isCoreUpdate(r.version, current)),
    [releases, current],
  );
  const hasUpdate = pending.length > 0;
  const currentBase = coreReleaseOf(current);
  const currentRelease = currentBase
    ? releases.find((r) => r.version === currentBase)
    : undefined;
  const shown = hasUpdate ? pending : currentRelease ? [currentRelease] : [];
  const visible = expanded ? shown : shown.slice(0, COLLAPSED_RELEASE_COUNT);
  const hiddenCount = shown.length - visible.length;

  const useFallback = shown.length === 0 && !!fallbackRelease;
  const latestVersion = hasUpdate
    ? pending[0].version
    : useFallback
      ? stripV(fallbackRelease?.tag_name)
      : current;
  const showUpdateHeader = hasUpdate || useFallback;

  const updateDocsUrl = `https://langbot.app/docs/${locale}/deploy/update`;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setExpanded(false);
        onOpenChange(next);
      }}
    >
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 p-0 sm:max-w-[600px]">
        <DialogHeader className="shrink-0 px-6 pt-6 pb-4">
          <DialogTitle className="flex items-baseline gap-2">
            {showUpdateHeader
              ? t('version.newVersionAvailable')
              : t('version.whatsNewInCurrent')}
            {latestVersion && (
              <span className="font-mono text-base font-medium text-muted-foreground">
                v{latestVersion}
              </span>
            )}
          </DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-1.5">
            {showUpdateHeader && current ? (
              <>
                <span className="font-mono">v{current}</span>
                <ArrowRight className="size-3.5" />
                <span className="font-mono">v{latestVersion}</span>
                {pending.length > 1 && (
                  <span>
                    · {t('version.releasesIncluded', { count: pending.length })}
                  </span>
                )}
              </>
            ) : parseCoreVersion(current) ? (
              <span>{t('version.upToDate')}</span>
            ) : (
              // A hand-edited version cannot be ordered against releases.
              <span className="sr-only">v{current}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        <Separator />

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {useFallback && fallbackRelease ? (
            <div className="markdown-body max-w-none text-sm">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeSanitize]}
              >
                {fallbackRelease.body || t('version.noReleaseNotes')}
              </ReactMarkdown>
            </div>
          ) : shown.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t('version.noReleaseNotes')}
            </p>
          ) : (
            <div className="space-y-6">
              {visible.map((release, i) => (
                <Fragment key={release.version}>
                  {i > 0 && <Separator />}
                  <ReleaseSection
                    release={release}
                    locale={locale}
                    isLatest={hasUpdate && i === 0}
                    isCurrent={release.version === currentBase}
                  />
                </Fragment>
              ))}
              {hiddenCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setExpanded(true)}
                  className="w-full gap-1.5 text-muted-foreground"
                >
                  <ChevronDown className="size-4" />
                  {t('version.showOlderReleases', { count: hiddenCount })}
                </Button>
              )}
            </div>
          )}
        </div>

        <Separator />

        <DialogFooter className="shrink-0 px-6 py-4 sm:items-center sm:justify-between">
          <a
            href={changelogPageUrl(locale)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            {t('version.viewFullChangelog')}
            <ExternalLink className="size-3.5" />
          </a>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.close')}
            </Button>
            {showUpdateHeader && (
              <Button
                onClick={() => window.open(updateDocsUrl, '_blank')}
                className="gap-2"
              >
                {t('version.viewUpdateGuide')}
                <ExternalLink className="size-4" />
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
