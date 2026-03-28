import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from 'react';
import { httpClient, getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { isNewerVersion } from '@/app/utils/versionCompare';

// Lightweight entity item for sidebar display
export interface SidebarEntityItem {
  id: string;
  name: string;
  description?: string;
  emoji?: string;
  iconURL?: string;
  updatedAt?: string; // ISO timestamp for sorting by most recently edited
  // Bot-specific fields
  enabled?: boolean;
  // MCP-specific fields
  runtimeStatus?: 'connecting' | 'connected' | 'error';
  // Plugin-specific fields
  installSource?: string;
  installInfo?: Record<string, unknown>;
  hasUpdate?: boolean;
  debug?: boolean;
}

// Install action types that can be triggered from sidebar
export type PluginInstallAction = 'local' | 'github' | null;

// Entity lists and refresh functions exposed via context
export interface SidebarDataContextValue {
  bots: SidebarEntityItem[];
  pipelines: SidebarEntityItem[];
  knowledgeBases: SidebarEntityItem[];
  plugins: SidebarEntityItem[];
  mcpServers: SidebarEntityItem[];
  skills: SidebarEntityItem[];
  refreshBots: () => Promise<void>;
  refreshPipelines: () => Promise<void>;
  refreshKnowledgeBases: () => Promise<void>;
  refreshPlugins: () => Promise<void>;
  refreshMCPServers: () => Promise<void>;
  refreshSkills: () => Promise<void>;
  refreshAll: () => Promise<void>;
  // Breadcrumb: entity name shown when viewing a detail page
  detailEntityName: string | null;
  setDetailEntityName: (name: string | null) => void;
  // Pending plugin install action triggered from sidebar
  pendingPluginInstallAction: PluginInstallAction;
  setPendingPluginInstallAction: (action: PluginInstallAction) => void;
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
  const [mcpServers, setMCPServers] = useState<SidebarEntityItem[]>([]);
  const [skills, setSkills] = useState<SidebarEntityItem[]>([]);
  const [detailEntityName, setDetailEntityName] = useState<string | null>(null);
  const [pendingPluginInstallAction, setPendingPluginInstallAction] =
    useState<PluginInstallAction>(null);

  const refreshBots = useCallback(async () => {
    try {
      const resp = await httpClient.getBots();
      setBots(
        resp.bots.map((bot) => ({
          id: bot.uuid || '',
          name: bot.name,
          description: bot.description,
          iconURL: httpClient.getAdapterIconURL(bot.adapter),
          updatedAt: bot.updated_at,
          enabled: bot.enable ?? true,
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
          description: p.description,
          emoji: p.emoji,
          updatedAt: p.updated_at,
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
          description: kb.description,
          emoji: kb.emoji,
          updatedAt: kb.updated_at,
        })),
      );
    } catch (error) {
      console.error('Failed to fetch knowledge bases for sidebar:', error);
    }
  }, []);

  const refreshPlugins = useCallback(async () => {
    try {
      const [pluginsResp, marketplaceResp] = await Promise.all([
        httpClient.getPlugins(),
        getCloudServiceClientSync()
          .getMarketplacePlugins(1, 100)
          .catch(() => ({ plugins: [] })),
      ]);

      // Build marketplace version lookup: "author/name" -> latest_version
      const marketplaceVersions = new Map<string, string>();
      for (const mp of marketplaceResp.plugins) {
        if (mp.latest_version) {
          marketplaceVersions.set(`${mp.author}/${mp.name}`, mp.latest_version);
        }
      }

      setPlugins(
        pluginsResp.plugins.map((plugin) => {
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

          return {
            id: compositeKey,
            name: extractI18nObject(meta.label),
            iconURL: httpClient.getPluginIconURL(author, name),
            installSource: plugin.install_source,
            installInfo: plugin.install_info,
            hasUpdate,
            debug: plugin.debug,
          };
        }),
      );
    } catch (error) {
      console.error('Failed to fetch plugins for sidebar:', error);
    }
  }, []);

  const refreshMCPServers = useCallback(async () => {
    try {
      const resp = await httpClient.getMCPServers();
      setMCPServers(
        resp.servers.map((server) => ({
          id: server.name,
          name: server.name,
          enabled: server.enable,
          runtimeStatus: server.runtime_info?.status,
        })),
      );
    } catch (error) {
      console.error('Failed to fetch MCP servers for sidebar:', error);
    }
  }, []);

  const refreshSkills = useCallback(async () => {
    try {
      const resp = await httpClient.getSkills();
      setSkills(
        resp.skills.map((skill) => ({
          id: skill.name,
          name: skill.display_name || skill.name,
          description: skill.description,
          updatedAt: skill.updated_at,
        })),
      );
    } catch (error) {
      console.error('Failed to fetch skills for sidebar:', error);
    }
  }, []);

  const refreshAll = useCallback(async () => {
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
        mcpServers,
        skills,
        refreshBots,
        refreshPipelines,
        refreshKnowledgeBases,
        refreshPlugins,
        refreshMCPServers,
        refreshSkills,
        refreshAll,
        detailEntityName,
        setDetailEntityName,
        pendingPluginInstallAction,
        setPendingPluginInstallAction,
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
