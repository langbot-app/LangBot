'use client';

import { useState } from 'react';
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

const PAGE_SIZE = 4; // plugins per page in a recommendation row

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
}: {
  list: RecommendationList;
  tagNames: Record<string, string>;
  onInstall: (author: string, pluginName: string) => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);

  const plugins = list.plugins || [];
  const totalPages = Math.ceil(plugins.length / PAGE_SIZE);
  const start = page * PAGE_SIZE;
  const visiblePlugins = plugins.slice(start, start + PAGE_SIZE);

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
              disabled={page === 0}
              className="h-7 w-7 p-0"
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <span className="text-xs text-muted-foreground px-1">
              {page + 1} / {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="h-7 w-7 p-0"
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4 gap-6">
        {visiblePlugins.map((plugin) => (
          <PluginMarketCardComponent
            key={plugin.author + ' / ' + plugin.name}
            cardVO={pluginToVO(plugin, t)}
            tagNames={tagNames}
            onInstall={onInstall}
          />
        ))}
      </div>
      {totalPages > 1 && <div className="border-b border-border mt-6" />}
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
      {lists.map((list) => (
        <RecommendationListRow
          key={list.uuid}
          list={list}
          tagNames={tagNames}
          onInstall={onInstall}
        />
      ))}
      <div className="border-b border-border mb-6" />
    </div>
  );
}
