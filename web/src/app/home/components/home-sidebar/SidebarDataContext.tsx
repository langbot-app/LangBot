'use client';

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import { httpClient } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';

// Lightweight entity item for sidebar display
export interface SidebarEntityItem {
  id: string;
  name: string;
  emoji?: string;
  iconURL?: string;
}

// Entity lists and refresh functions exposed via context
export interface SidebarDataContextValue {
  bots: SidebarEntityItem[];
  pipelines: SidebarEntityItem[];
  knowledgeBases: SidebarEntityItem[];
  plugins: SidebarEntityItem[];
  refreshBots: () => Promise<void>;
  refreshPipelines: () => Promise<void>;
  refreshKnowledgeBases: () => Promise<void>;
  refreshPlugins: () => Promise<void>;
  refreshAll: () => Promise<void>;
}

const SidebarDataContext = createContext<SidebarDataContextValue | null>(null);

export function SidebarDataProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [bots, setBots] = useState<SidebarEntityItem[]>([]);
  const [pipelines, setPipelines] = useState<SidebarEntityItem[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<SidebarEntityItem[]>([]);
  const [plugins, setPlugins] = useState<SidebarEntityItem[]>([]);

  const refreshBots = useCallback(async () => {
    try {
      const resp = await httpClient.getBots();
      setBots(
        resp.bots.map((bot) => ({
          id: bot.uuid || '',
          name: bot.name,
          iconURL: httpClient.getAdapterIconURL(bot.adapter),
        })),
      );
    } catch (error) {
      console.error('Failed to fetch bots for sidebar:', error);
    }
  }, []);

  const refreshPipelines = useCallback(async () => {
    try {
      const resp = await httpClient.getPipelines();
      setPipelines(
        resp.pipelines.map((p) => ({
          id: p.uuid || '',
          name: p.name,
          emoji: p.emoji,
        })),
      );
    } catch (error) {
      console.error('Failed to fetch pipelines for sidebar:', error);
    }
  }, []);

  const refreshKnowledgeBases = useCallback(async () => {
    try {
      const resp = await httpClient.getKnowledgeBases();
      setKnowledgeBases(
        resp.bases.map((kb) => ({
          id: kb.uuid || '',
          name: kb.name,
          emoji: kb.emoji,
        })),
      );
    } catch (error) {
      console.error('Failed to fetch knowledge bases for sidebar:', error);
    }
  }, []);

  const refreshPlugins = useCallback(async () => {
    try {
      const resp = await httpClient.getPlugins();
      setPlugins(
        resp.plugins.map((plugin) => {
          const meta = plugin.manifest.manifest.metadata;
          const author = meta.author ?? '';
          const name = meta.name;
          return {
            id: `${author}/${name}`,
            name: extractI18nObject(meta.label),
            iconURL: httpClient.getPluginIconURL(author, name),
          };
        }),
      );
    } catch (error) {
      console.error('Failed to fetch plugins for sidebar:', error);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshBots(),
      refreshPipelines(),
      refreshKnowledgeBases(),
      refreshPlugins(),
    ]);
  }, [refreshBots, refreshPipelines, refreshKnowledgeBases, refreshPlugins]);

  // Fetch all entity lists on mount
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  return (
    <SidebarDataContext.Provider
      value={{
        bots,
        pipelines,
        knowledgeBases,
        plugins,
        refreshBots,
        refreshPipelines,
        refreshKnowledgeBases,
        refreshPlugins,
        refreshAll,
      }}
    >
      {children}
    </SidebarDataContext.Provider>
  );
}

export function useSidebarData(): SidebarDataContextValue {
  const ctx = useContext(SidebarDataContext);
  if (!ctx) {
    throw new Error('useSidebarData must be used within a SidebarDataProvider');
  }
  return ctx;
}
