import { createContext, useContext } from 'react';

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
  legacyAdapter?: boolean;
  // MCP-specific fields
  runtimeStatus?: 'connecting' | 'connected' | 'error';
  // Plugin-specific fields
  installSource?: string;
  installInfo?: Record<string, unknown>;
  hasUpdate?: boolean;
  debug?: boolean;
  // Set when this item appears in the unified extensions list
  extensionType?: 'plugin' | 'mcp' | 'skill';
  // Agent-specific: distinguishes Agent processors from Pipelines
  kind?: 'agent' | 'pipeline' | 'event_processor';
}

// Plugin page registered by a plugin
export interface PluginPageItem {
  id: string; // "author/name/pageId"
  name: string; // display label
  pluginAuthor: string;
  pluginName: string;
  pluginLabel: string; // human-readable plugin display name
  pluginIconURL: string; // plugin icon URL
  pageId: string;
  path: string; // asset path (HTML file)
}

// Entity lists and refresh functions exposed via context
export interface SidebarDataContextValue {
  bots: SidebarEntityItem[];
  pipelines: SidebarEntityItem[];
  knowledgeBases: SidebarEntityItem[];
  plugins: SidebarEntityItem[];
  pluginCount: number;
  mcpServers: SidebarEntityItem[];
  skills: SidebarEntityItem[];
  pluginPages: PluginPageItem[];
  quotaDataLoaded: boolean;
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
  // Whether the extensions list is grouped by type (shared between page and sidebar)
  extensionsGroupByType: boolean;
  setExtensionsGroupByType: (enabled: boolean) => void;
  // Whether the Agent list is grouped by kind (Agent vs Pipeline)
  agentsGroupByKind: boolean;
  setAgentsGroupByKind: (enabled: boolean) => void;
}

export const SidebarDataContext = createContext<SidebarDataContextValue | null>(
  null,
);

export function useSidebarData(): SidebarDataContextValue {
  const ctx = useContext(SidebarDataContext);
  if (!ctx) {
    throw new Error('useSidebarData must be used within a SidebarDataProvider');
  }
  return ctx;
}
