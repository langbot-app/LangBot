import React, { useState, useEffect, useCallback, useRef } from 'react';
import { httpClient, getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { isNewerVersion } from '@/app/utils/versionCompare';

// Keep the context identity independent of provider dependencies during HMR.
import {
  SidebarDataContext,
  type SidebarEntityItem,
  type PluginPageItem,
} from './sidebarDataStore';
export { useSidebarData } from './sidebarDataStore';
export type {
  SidebarEntityItem,
  PluginPageItem,
  SidebarDataContextValue,
} from './sidebarDataStore';

export function SidebarDataProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [bots, setBots] = useState<SidebarEntityItem[]>([]);
  const [pipelines, setPipelines] = useState<SidebarEntityItem[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<SidebarEntityItem[]>([]);
  const [plugins, setPlugins] = useState<SidebarEntityItem[]>([]);
  const [pluginCount, setPluginCount] = useState(0);
  const [mcpServers, setMCPServers] = useState<SidebarEntityItem[]>([]);
  const [skills, setSkills] = useState<SidebarEntityItem[]>([]);
  const [pluginPages, setPluginPages] = useState<PluginPageItem[]>([]);
  const [quotaDataLoaded, setQuotaDataLoaded] = useState(false);
  const refreshRequestIds = useRef({
    bots: 0,
    pipelines: 0,
    knowledgeBases: 0,
    plugins: 0,
    mcpServers: 0,
    skills: 0,
  });
  const quotaResourceLoaded = useRef({
    bots: false,
    pipelines: false,
    knowledgeBases: false,
    plugins: false,
    mcpServers: false,
    skills: false,
  });
  const setQuotaResourceLoaded = useCallback(
    (resource: keyof typeof quotaResourceLoaded.current, loaded: boolean) => {
      quotaResourceLoaded.current[resource] = loaded;
      setQuotaDataLoaded(
        Object.values(quotaResourceLoaded.current).every(Boolean),
      );
    },
    [],
  );
  const [detailEntityName, setDetailEntityName] = useState<string | null>(null);
  const [extensionsGroupByType, setExtensionsGroupByTypeState] =
    useState<boolean>(() => {
      if (typeof window === 'undefined') return false;
      return localStorage.getItem('extensions_group_by_type') === 'true';
    });
  const setExtensionsGroupByType = useCallback((enabled: boolean) => {
    setExtensionsGroupByTypeState(enabled);
    try {
      localStorage.setItem('extensions_group_by_type', String(enabled));
    } catch {
      // ignore
    }
  }, []);

  const [agentsGroupByKind, setAgentsGroupByKindState] = useState<boolean>(
    () => {
      if (typeof window === 'undefined') return false;
      return localStorage.getItem('agents_group_by_kind') === 'true';
    },
  );
  const setAgentsGroupByKind = useCallback((enabled: boolean) => {
    setAgentsGroupByKindState(enabled);
    try {
      localStorage.setItem('agents_group_by_kind', String(enabled));
    } catch {
      // ignore
    }
  }, []);

  const refreshBots = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.bots;
    try {
      const [resp, adaptersResp] = await Promise.all([
        httpClient.getBots(),
        httpClient.getAdapters().catch(() => ({ adapters: [] })),
      ]);
      if (requestId !== refreshRequestIds.current.bots) return;
      setQuotaResourceLoaded('bots', true);
      const legacyAdapterNames = new Set(
        adaptersResp.adapters
          .filter((adapter) => adapter.spec.legacy)
          .map((adapter) => adapter.name),
      );
      setBots(
        resp.bots.map((bot) => ({
          id: bot.uuid || '',
          name: bot.name,
          description: bot.description,
          iconURL: httpClient.getAdapterIconURL(bot.adapter),
          updatedAt: bot.updated_at,
          enabled: bot.enable ?? true,
          legacyAdapter: legacyAdapterNames.has(bot.adapter),
        })),
      );
    } catch (error) {
      if (requestId !== refreshRequestIds.current.bots) return;
      setQuotaResourceLoaded('bots', false);
      console.error('Failed to fetch bots for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshPipelines = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.pipelines;
    try {
      const resp = await httpClient.getAgents();
      if (requestId !== refreshRequestIds.current.pipelines) return;
      setQuotaResourceLoaded('pipelines', true);
      setPipelines(
        resp.agents.map((p) => ({
          id: p.uuid || '',
          name: p.name,
          description: p.description,
          emoji: p.emoji,
          updatedAt: p.updated_at,
          kind: p.kind,
        })),
      );
    } catch (error) {
      if (requestId !== refreshRequestIds.current.pipelines) return;
      setQuotaResourceLoaded('pipelines', false);
      console.error('Failed to fetch agents for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshKnowledgeBases = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.knowledgeBases;
    try {
      const resp = await httpClient.getKnowledgeBases();
      if (requestId !== refreshRequestIds.current.knowledgeBases) return;
      setQuotaResourceLoaded('knowledgeBases', true);
      setKnowledgeBases(
        resp.bases.map((kb) => ({
          id: kb.uuid || '',
          name: kb.name,
          description: kb.description,
          emoji: kb.emoji,
          updatedAt: kb.updated_at,
        })),
      );
    } catch (error) {
      if (requestId !== refreshRequestIds.current.knowledgeBases) return;
      setQuotaResourceLoaded('knowledgeBases', false);
      console.error('Failed to fetch knowledge bases for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshPlugins = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.plugins;
    try {
      const [pluginsResp, marketplaceResp] = await Promise.all([
        httpClient.getPlugins(),
        getCloudServiceClientSync()
          .getMarketplacePlugins(1, 100)
          .catch(() => ({ plugins: [] })),
      ]);
      if (requestId !== refreshRequestIds.current.plugins) return;
      setQuotaResourceLoaded('plugins', true);
      setPluginCount(pluginsResp.plugins?.length ?? 0);

      // Build marketplace version lookup: "author/name" -> latest_version
      const marketplaceVersions = new Map<string, string>();
      for (const mp of marketplaceResp.plugins) {
        if (mp.latest_version) {
          marketplaceVersions.set(`${mp.author}/${mp.name}`, mp.latest_version);
        }
      }

      // Deduplicate plugins by composite key (prefer debug over installed)
      const pluginMap = new Map<string, SidebarEntityItem>();
      const pluginIconURLs = new Map<string, string>(
        await Promise.all(
          pluginsResp.plugins.map(async (plugin) => {
            const meta = plugin.manifest.manifest.metadata;
            const author = meta.author ?? '';
            const name = meta.name;
            const url = await httpClient
              .getAuthenticatedPluginIconURL(author, name)
              .catch(() => '');
            return [`${author}/${name}`, url] as const;
          }),
        ),
      );
      for (const plugin of pluginsResp.plugins) {
        const meta = plugin.manifest.manifest.metadata;
        const author = meta.author ?? '';
        const name = meta.name;
        const compositeKey = `${author}/${name}`;
        const installedVersion = meta.version ?? '';

        let hasUpdate = false;
        if (plugin.install_source === 'marketplace') {
          const latestVersion = marketplaceVersions.get(compositeKey);
          if (latestVersion) {
            hasUpdate = isNewerVersion(latestVersion, installedVersion);
          }
        }

        const item: SidebarEntityItem = {
          id: compositeKey,
          name: extractI18nObject(meta.label),
          iconURL: pluginIconURLs.get(compositeKey) || '',
          installSource: plugin.install_source,
          installInfo: plugin.install_info,
          hasUpdate,
          debug: plugin.debug,
        };

        // If duplicate, prefer debug version
        if (!pluginMap.has(compositeKey) || plugin.debug) {
          pluginMap.set(compositeKey, item);
        }
      }
      setPlugins(Array.from(pluginMap.values()));

      // Extract plugin pages from spec.pages (deduplicate by id)
      const pages: PluginPageItem[] = [];
      const seenPageIds = new Set<string>();
      for (const plugin of pluginsResp.plugins) {
        const meta = plugin.manifest.manifest.metadata;
        const author = meta.author ?? '';
        const name = meta.name;
        const label = meta.label ? extractI18nObject(meta.label) : name;
        const spec = plugin.manifest.manifest.spec;
        if (spec?.pages && Array.isArray(spec.pages)) {
          for (const page of spec.pages) {
            const pageId = `${author}/${name}/${page.id}`;
            if (page.id && page.path && !seenPageIds.has(pageId)) {
              seenPageIds.add(pageId);
              pages.push({
                id: pageId,
                name: page.label ? extractI18nObject(page.label) : page.id,
                pluginAuthor: author,
                pluginName: name,
                pluginLabel: label,
                pluginIconURL: pluginIconURLs.get(`${author}/${name}`) || '',
                pageId: page.id,
                path: page.path,
              });
            }
          }
        }
      }
      setPluginPages(pages);
    } catch (error) {
      if (requestId !== refreshRequestIds.current.plugins) return;
      setQuotaResourceLoaded('plugins', false);
      console.error('Failed to fetch plugins for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshMCPServers = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.mcpServers;
    try {
      const resp = await httpClient.getMCPServers();
      if (requestId !== refreshRequestIds.current.mcpServers) return;
      setQuotaResourceLoaded('mcpServers', true);
      setMCPServers(
        resp.servers.map((server) => ({
          id: server.name, // Keep __ for API calls
          name: server.name.replace(/__/g, '/'), // Display with / for readability
          enabled: server.enable,
          runtimeStatus: server.runtime_info?.status,
        })),
      );
    } catch (error) {
      if (requestId !== refreshRequestIds.current.mcpServers) return;
      setQuotaResourceLoaded('mcpServers', false);
      console.error('Failed to fetch MCP servers for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshSkills = useCallback(async () => {
    const requestId = ++refreshRequestIds.current.skills;
    try {
      const resp = await httpClient.getSkills();
      if (requestId !== refreshRequestIds.current.skills) return;
      setQuotaResourceLoaded('skills', true);
      setSkills(
        resp.skills.map((skill) => ({
          id: skill.name,
          name: skill.display_name || skill.name,
          description: skill.description,
          updatedAt: skill.updated_at,
        })),
      );
    } catch (error) {
      if (requestId !== refreshRequestIds.current.skills) return;
      setQuotaResourceLoaded('skills', false);
      console.error('Failed to fetch skills for sidebar:', error);
    }
  }, [setQuotaResourceLoaded]);

  const refreshAll = useCallback(async () => {
    quotaResourceLoaded.current = {
      bots: false,
      pipelines: false,
      knowledgeBases: false,
      plugins: false,
      mcpServers: false,
      skills: false,
    };
    setQuotaDataLoaded(false);
    await Promise.all([
      refreshBots(),
      refreshPipelines(),
      refreshKnowledgeBases(),
      refreshPlugins(),
      refreshMCPServers(),
      refreshSkills(),
    ]);
  }, [
    refreshBots,
    refreshPipelines,
    refreshKnowledgeBases,
    refreshPlugins,
    refreshMCPServers,
    refreshSkills,
  ]);

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
        pluginCount,
        mcpServers,
        skills,
        pluginPages,
        quotaDataLoaded,
        refreshBots,
        refreshPipelines,
        refreshKnowledgeBases,
        refreshPlugins,
        refreshMCPServers,
        refreshSkills,
        refreshAll,
        detailEntityName,
        setDetailEntityName,
        extensionsGroupByType,
        setExtensionsGroupByType,
        agentsGroupByKind,
        setAgentsGroupByKind,
      }}
    >
      {children}
    </SidebarDataContext.Provider>
  );
}
