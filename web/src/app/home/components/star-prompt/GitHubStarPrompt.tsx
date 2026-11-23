import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Github, Star, X } from 'lucide-react';

import {
  backendClient,
  getCloudServiceClientSync,
  isSupportAdminSession,
} from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import {
  STAR_PROMPT_THRESHOLD,
  formatStarCount,
  readStarPromptState,
  shouldOfferStarPrompt,
  writeStarPromptState,
} from './star-prompt-state';

const REPO_URL = 'https://github.com/langbot-app/LangBot';
const FIRST_CHECK_DELAY_MS = 8_000;
const RECHECK_INTERVAL_MS = 15 * 60_000;
const SNOOZE_MS = 7 * 24 * 60 * 60_000;

/**
 * Real (non-debug) executions handled by the current Workspace. Unrouted
 * platform events are excluded: LangBot received them but did no work.
 */
async function countHandledExecutions(): Promise<number> {
  const [agent, pipeline] = await Promise.all([
    backendClient.getExecutionTotal({ source: 'agent', mode: 'real' }),
    backendClient.getExecutionTotal({ source: 'pipeline', mode: 'real' }),
  ]);
  return agent + pipeline;
}

/**
 * One-time milestone card asking for a GitHub Star once the Workspace has
 * handled enough executions. The count is Workspace-scoped (Cloud tenants and
 * single-tenant instances alike), while the answer is remembered per browser
 * so a member is not asked again in every Workspace they open.
 */
export default function GitHubStarPrompt() {
  const { t, i18n } = useTranslation();
  const [count, setCount] = useState<number | null>(null);
  const [starCount, setStarCount] = useState<number | null>(null);

  useEffect(() => {
    if (isSupportAdminSession()) return;
    if (!shouldOfferStarPrompt(readStarPromptState(), Date.now())) return;

    let cancelled = false;
    let interval: number | undefined;

    const check = async () => {
      // Never stack on top of an open survey in the same corner.
      if (document.querySelector('[data-survey-widget]')) return;
      if (!shouldOfferStarPrompt(readStarPromptState(), Date.now())) {
        clearInterval(interval);
        return;
      }
      try {
        const total = await countHandledExecutions();
        if (cancelled || total < STAR_PROMPT_THRESHOLD) return;
        clearInterval(interval);
        const repo = await getCloudServiceClientSync()
          .getGitHubRepoInfo()
          .catch(() => null);
        if (cancelled) return;
        setStarCount(repo?.repo?.stargazers_count ?? null);
        setCount(total);
      } catch {
        // Members without monitoring access or a briefly unavailable backend
        // simply do not see the prompt.
      }
    };

    const timer = window.setTimeout(() => {
      void check();
      interval = window.setInterval(() => void check(), RECHECK_INTERVAL_MS);
    }, FIRST_CHECK_DELAY_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, []);

  const close = useCallback(
    (state: Parameters<typeof writeStarPromptState>[0]) => {
      writeStarPromptState(state);
      setCount(null);
    },
    [],
  );

  if (count === null) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="github-star-prompt-title"
      className="fixed bottom-6 right-6 z-50 w-[360px] max-w-[calc(100vw-2rem)] rounded-xl border bg-popover p-4 text-popover-foreground shadow-lg animate-in fade-in-0 slide-in-from-bottom-4 duration-300"
    >
      <div className="flex items-start gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-500 dark:bg-amber-500/15 dark:text-amber-400">
          <Star className="size-4 fill-current animate-twinkle" />
        </div>
        <div className="min-w-0 flex-1 pt-0.5">
          <p
            id="github-star-prompt-title"
            className="pr-5 text-sm font-semibold leading-snug"
          >
            {t('githubStarPrompt.title', {
              total: count.toLocaleString(i18n.language),
            })}
          </p>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground">
            {t('githubStarPrompt.description')}
          </p>
        </div>
        <button
          type="button"
          aria-label={t('githubStarPrompt.close')}
          onClick={() => close({ state: 'dismissed' })}
          className="-mr-1 -mt-1 rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="mt-4 flex items-center justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          onClick={() =>
            close({ state: 'snoozed', until: Date.now() + SNOOZE_MS })
          }
        >
          {t('githubStarPrompt.later')}
        </Button>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => close({ state: 'starred' })}
          className="inline-flex h-8 items-center overflow-hidden rounded-md bg-foreground text-sm font-medium text-background shadow-xs transition-opacity hover:opacity-90"
        >
          <span className="flex items-center gap-1.5 px-3">
            <Github className="size-4" />
            {t('githubStarPrompt.star')}
          </span>
          {starCount !== null && (
            <span className="flex h-full items-center border-l border-background/20 px-2.5 tabular-nums">
              {formatStarCount(starCount)}
            </span>
          )}
        </a>
      </div>
    </div>
  );
}
