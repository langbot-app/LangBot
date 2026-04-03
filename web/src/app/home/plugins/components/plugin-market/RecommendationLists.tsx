

import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight, Star } from 'lucide-react';
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

// Match the main plugin grid: grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4

function pluginToVO(
  plugin: PluginV4,
  t: (key: string) => string,
): PluginMarketCardVO {
  return new PluginMarketCardVO({
    pluginId: plugin.author + ' / ' + plugin.name,
    author: plugin.author,
    pluginName: plugin.name,
    label: extractI18nObject(plugin.label),
    description:
      extractI18nObject(plugin.description) || t('market.noDescription'),
    installCount: plugin.install_count,
    iconURL: getCloudServiceClientSync().getPluginIconURL(
      plugin.author,
      plugin.name,
    ),
    githubURL: plugin.repository,
    version: plugin.latest_version,
    components: plugin.components,
    tags: plugin.tags || [],
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
  onInstall: (author: string, pluginName: string) => void;
  isLast: boolean;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const [perPage, setPerPage] = useState(4);
  const gridRef = useRef<HTMLDivElement>(null);

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

  // Auto-advance every 5 seconds
  useEffect(() => {
    if (plugins.length <= perPage) return;
    const timer = setInterval(() => {
      setPage((p) => {
        const tp = Math.max(1, Math.ceil(plugins.length / perPage));
        return p >= tp - 1 ? 0 : p + 1;
      });
    }, 5000);
    return () => clearInterval(timer);
  }, [plugins.length, perPage]);

  const totalPages = Math.max(1, Math.ceil(plugins.length / perPage));
  const safePage = Math.min(page, totalPages - 1);
  if (safePage !== page) setPage(safePage);

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
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={safePage === 0}
              className="h-7 w-7 p-0"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-xs text-muted-foreground px-1">
              {safePage + 1} / {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
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
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6"
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
  onInstall: (author: string, pluginName: string) => void;
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
