import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Star, Pause, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import PluginMarketCardComponent from './plugin-market-card/PluginMarketCardComponent';
import { PluginMarketCardVO } from './plugin-market-card/PluginMarketCardVO';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { I18nObject } from '@/app/infra/entities/common';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { useTranslation } from 'react-i18next';

export interface RecommendationList {
  uuid: string;
  label: I18nObject;
  sort_order: number;
  plugins: PluginV4[];
}

// Match the main plugin grid: auto-fill columns with a 24rem minimum width

function pluginToVO(
  plugin: PluginV4,
  t: (key: string) => string,
): PluginMarketCardVO {
  const cloudClient = getCloudServiceClientSync();
  // Recommendation lists are mixed-type; resolve the icon per extension type,
  // preferring an absolute external icon URL when the record carries one.
  const iconURL = cloudClient.resolveMarketplaceIconURL(
    plugin.type,
    plugin.author,
    plugin.name,
    plugin.icon,
  );

  return new PluginMarketCardVO({
    pluginId: plugin.author + ' / ' + plugin.name,
    author: plugin.author,
    pluginName: plugin.name,
    label: extractI18nObject(plugin.label),
    description:
      extractI18nObject(plugin.description) || t('market.noDescription'),
    installCount: plugin.install_count,
    likeCount: plugin.like_count || 0,
    iconURL,
    githubURL: plugin.repository,
    version: plugin.latest_version,
    components: plugin.components,
    tags: plugin.tags || [],
    type: plugin.type,
  });
}

function RecommendationListRow({
  list,
  tagNames,
  onInstall,
  isLast,
}: {
  list: RecommendationList;
  tagNames: Record<string, string>;
  onInstall: (cardVO: PluginMarketCardVO) => void;
  isLast: boolean;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const [perPage, setPerPage] = useState(4);
  // Countdown progress to the next auto-advance, 0 → 1 over AUTO_ADVANCE_MS.
  const [progress, setProgress] = useState(0);
  const [paused, setPaused] = useState(false);
  // Accumulated elapsed time in the current cycle and the timestamp of the last
  // animation frame. Kept in refs so the interval reads live values without
  // re-subscribing, and so pausing freezes progress in place.
  const elapsedRef = useRef<number>(0);
  const lastFrameRef = useRef<number>(Date.now());
  const pausedRef = useRef<boolean>(false);
  const gridRef = useRef<HTMLDivElement>(null);

  const AUTO_ADVANCE_MS = 10000;

  const plugins = (list.plugins || []).filter((plugin) => {
    // Hide plugins that only contain deprecated KnowledgeRetriever components
    const keys = Object.keys(plugin.components || {});
    return !(keys.length > 0 && keys.every((k) => k === 'KnowledgeRetriever'));
  });

  // Measure how many columns the CSS grid actually renders
  const measureCols = useCallback(() => {
    if (!gridRef.current) return;
    const style = window.getComputedStyle(gridRef.current);
    const cols = style.gridTemplateColumns.split(' ').length;
    setPerPage(cols);
  }, []);

  useEffect(() => {
    measureCols();
    const observer = new ResizeObserver(measureCols);
    if (gridRef.current) observer.observe(gridRef.current);
    return () => observer.disconnect();
  }, [measureCols]);

  // Restart the countdown from zero. Called on manual navigation so the user's
  // click resets the time-to-next-page indicator.
  const resetCountdown = useCallback(() => {
    elapsedRef.current = 0;
    lastFrameRef.current = Date.now();
    setProgress(0);
  }, []);

  const togglePaused = () => {
    setPaused((prev) => {
      const next = !prev;
      pausedRef.current = next;
      // Resync the frame clock on resume so the paused gap isn't counted.
      lastFrameRef.current = Date.now();
      return next;
    });
  };

  // Auto-advance every AUTO_ADVANCE_MS, driving a smooth countdown ring. The
  // interval accumulates elapsed time from refs, so resetCountdown() restarts
  // the cycle on manual navigation and pause freezes it without re-creating the
  // interval.
  useEffect(() => {
    if (plugins.length <= perPage) return;
    resetCountdown();
    const timer = setInterval(() => {
      const now = Date.now();
      const delta = now - lastFrameRef.current;
      lastFrameRef.current = now;
      if (pausedRef.current) return;

      elapsedRef.current += delta;
      if (elapsedRef.current >= AUTO_ADVANCE_MS) {
        elapsedRef.current = 0;
        setProgress(0);
        setPage((p) => {
          const tp = Math.max(1, Math.ceil(plugins.length / perPage));
          return p >= tp - 1 ? 0 : p + 1;
        });
      } else {
        setProgress(elapsedRef.current / AUTO_ADVANCE_MS);
      }
    }, 50);
    return () => clearInterval(timer);
  }, [plugins.length, perPage, resetCountdown]);

  const totalPages = Math.max(1, Math.ceil(plugins.length / perPage));
  const safePage = Math.min(page, totalPages - 1);
  if (safePage !== page) setPage(safePage);

  const goPrev = () => {
    setPage((p) => Math.max(0, p - 1));
    resetCountdown();
  };
  const goNext = () => {
    setPage((p) => Math.min(totalPages - 1, p + 1));
    resetCountdown();
  };

  const start = safePage * perPage;
  const visiblePlugins = plugins.slice(start, start + perPage);

  if (plugins.length === 0) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Star className="w-4 h-4 text-yellow-500" />
          <h3 className="font-semibold text-base">
            {extractI18nObject(list.label)}
          </h3>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={goPrev}
              disabled={safePage === 0}
              className="h-7 w-7 p-0"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-xs text-muted-foreground px-1">
              {safePage + 1} / {totalPages}
            </span>
            {/* Auto-advance countdown ring doubles as a pause/resume toggle.
                The ring fills as the next flip approaches; click to pause. */}
            <button
              type="button"
              onClick={togglePaused}
              title={
                paused
                  ? t('market.recommendation.resume')
                  : t('market.recommendation.pause')
              }
              aria-label={
                paused
                  ? t('market.recommendation.resume')
                  : t('market.recommendation.pause')
              }
              className="relative inline-flex h-7 w-7 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 16 16"
                className="-rotate-90 shrink-0"
                aria-hidden="true"
              >
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="text-muted-foreground/25"
                />
                <circle
                  cx="8"
                  cy="8"
                  r="6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  className={
                    paused ? 'text-muted-foreground/50' : 'text-yellow-500'
                  }
                  strokeDasharray={2 * Math.PI * 6}
                  strokeDashoffset={2 * Math.PI * 6 * (1 - progress)}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center">
                {paused ? (
                  <Play className="h-2.5 w-2.5" />
                ) : (
                  <Pause className="h-2.5 w-2.5" />
                )}
              </span>
            </button>
            <Button
              variant="ghost"
              size="sm"
              onClick={goNext}
              disabled={safePage >= totalPages - 1}
              className="h-7 w-7 p-0"
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>
      <div
        ref={gridRef}
        className="grid gap-6 [grid-template-columns:repeat(auto-fill,minmax(min(100%,24rem),1fr))]"
      >
        {visiblePlugins.map((plugin) => (
          <PluginMarketCardComponent
            key={plugin.author + ' / ' + plugin.name}
            cardVO={pluginToVO(plugin, t)}
            tagNames={tagNames}
            onInstall={onInstall}
          />
        ))}
      </div>
      {totalPages > 1 && !isLast && (
        <div className="border-b border-border mt-6" />
      )}
    </div>
  );
}

export function RecommendationLists({
  lists,
  tagNames,
  onInstall,
}: {
  lists: RecommendationList[];
  tagNames: Record<string, string>;
  onInstall: (cardVO: PluginMarketCardVO) => void;
}) {
  if (!lists || lists.length === 0) return null;

  return (
    <div className="mt-6">
      {lists.map((list, index) => (
        <RecommendationListRow
          key={list.uuid}
          list={list}
          tagNames={tagNames}
          onInstall={onInstall}
          isLast={index === lists.length - 1}
        />
      ))}
      <div className="border-b border-border mb-6" />
    </div>
  );
}
