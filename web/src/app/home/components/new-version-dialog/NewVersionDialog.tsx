import { Fragment, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import i18n from 'i18next';
import {
  ArrowRight,
  ChevronDown,
  ExternalLink,
  type LucideIcon,
  Rocket,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  TriangleAlert,
  Wrench,
} from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import { isNewerVersion } from '@/app/utils/versionCompare';

const COLLAPSED_RELEASE_COUNT = 3;

const TYPE_STYLES: Record<
  ChangelogChangeType,
  { icon: LucideIcon; pill: string; dot: string }
> = {
  new: {
    icon: Sparkles,
    pill: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    dot: 'bg-emerald-500',
  },
  improved: {
    icon: TrendingUp,
    pill: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
    dot: 'bg-sky-500',
  },
  changed: {
    icon: TriangleAlert,
    pill: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    dot: 'bg-amber-500',
  },
  security: {
    icon: ShieldCheck,
    pill: 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
    dot: 'bg-rose-500',
  },
  fixed: {
    icon: Wrench,
    pill: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
    dot: 'bg-violet-500',
  },
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
            className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em] text-foreground"
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
  const groups = CHANGELOG_TYPE_ORDER.map((type) => ({
    type,
    items: release.items.filter((item) => item.type === type),
  })).filter((group) => group.items.length > 0);

  return (
    <section className="relative pl-6">
      {/* Timeline rail */}
      <span
        aria-hidden
        className={cn(
          'absolute left-0 top-1.5 size-2.5 rounded-full ring-4 ring-background',
          isLatest ? 'bg-[#2288ee]' : 'bg-muted-foreground/40',
        )}
      />
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <h3 className="font-mono text-base font-semibold tracking-tight">
          v{release.version}
        </h3>
        {isLatest && (
          <Badge className="h-5 rounded-full border-transparent bg-[#2288ee] px-2 text-[0.65rem] text-white">
            {t('version.latestBadge')}
          </Badge>
        )}
        {isCurrent && (
          <Badge
            variant="secondary"
            className="h-5 rounded-full px-2 text-[0.65rem]"
          >
            {t('version.currentBadge')}
          </Badge>
        )}
        <span className="text-xs text-muted-foreground">{release.date}</span>
        <a
          href={changelogPageUrl(locale, release.version)}
          target="_blank"
          rel="noopener noreferrer"
          className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-[#2288ee]"
        >
          {t('version.viewOnWebsite')}
          <ExternalLink className="size-3" />
        </a>
      </div>
      {summary && (
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          <InlineText text={summary} />
        </p>
      )}
      <div className="mt-4 space-y-4">
        {groups.map(({ type, items }) => {
          const style = TYPE_STYLES[type];
          const Icon = style.icon;
          return (
            <div key={type}>
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
                  style.pill,
                )}
              >
                <Icon className="size-3.5" />
                {t(`version.changeTypes.${type}`)}
              </span>
              <ul className="mt-2 space-y-1.5">
                {items.map((item, i) => (
                  <li
                    key={i}
                    className="flex gap-2.5 text-sm leading-relaxed text-foreground/90"
                  >
                    <span
                      aria-hidden
                      className={cn(
                        'mt-[0.55rem] size-1.5 shrink-0 rounded-full',
                        style.dot,
                      )}
                    />
                    <span>
                      <InlineText text={pickChangelogText(item.text, locale)} />
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
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
    () =>
      current
        ? releases.filter((r) => isNewerVersion(r.version, current))
        : releases.slice(0, 1),
    [releases, current],
  );
  const hasUpdate = pending.length > 0;
  const currentRelease = releases.find((r) => r.version === current);
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
      <DialogContent className="flex max-h-[85vh] flex-col gap-0 overflow-hidden p-0 sm:max-w-[640px]">
        <DialogHeader className="shrink-0 border-b bg-gradient-to-b from-[#2288ee]/[0.08] to-transparent px-6 pt-6 pb-5 text-left">
          <div className="flex items-start gap-4">
            <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-[#2288ee]/10 text-[#2288ee]">
              {showUpdateHeader ? (
                <Rocket className="size-5" />
              ) : (
                <Sparkles className="size-5" />
              )}
            </div>
            <div className="min-w-0 space-y-1">
              <DialogTitle className="flex flex-wrap items-baseline gap-x-2 text-lg">
                {showUpdateHeader
                  ? t('version.newVersionAvailable')
                  : t('version.whatsNewInCurrent')}
                {latestVersion && (
                  <span className="font-mono text-[#2288ee]">
                    v{latestVersion}
                  </span>
                )}
              </DialogTitle>
              <DialogDescription className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm">
                {showUpdateHeader && current ? (
                  <>
                    <span className="font-mono">v{current}</span>
                    <ArrowRight className="size-3.5" />
                    <span className="font-mono font-medium text-foreground">
                      v{latestVersion}
                    </span>
                    {pending.length > 1 && (
                      <span>
                        ·{' '}
                        {t('version.releasesIncluded', {
                          count: pending.length,
                        })}
                      </span>
                    )}
                  </>
                ) : (
                  <span>{t('version.upToDate')}</span>
                )}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
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
            <div className="relative space-y-8">
              {/* Vertical line connecting the timeline dots */}
              {visible.length > 1 && (
                <span
                  aria-hidden
                  className="absolute top-3 bottom-3 left-[4.5px] w-px bg-border"
                />
              )}
              {visible.map((release, i) => (
                <ReleaseSection
                  key={release.version}
                  release={release}
                  locale={locale}
                  isLatest={hasUpdate && i === 0}
                  isCurrent={release.version === current}
                />
              ))}
              {hiddenCount > 0 && (
                <div className="pl-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setExpanded(true)}
                    className="gap-1.5"
                  >
                    <ChevronDown className="size-4" />
                    {t('version.showOlderReleases', { count: hiddenCount })}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex shrink-0 flex-col-reverse gap-2 border-t bg-muted/30 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <a
            href={changelogPageUrl(locale)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-[#2288ee]"
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
        </div>
      </DialogContent>
    </Dialog>
  );
}
