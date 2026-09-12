import { useMemo } from 'react';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';

export interface MarketplaceInstalledState {
  installed: boolean;
  hasUpdate: boolean;
}

export interface InstalledIndexEntry {
  hasUpdate: boolean;
}

/** Composite key used to look up installed extensions: `type:author/name`. */
export function installedExtensionKey(
  type: string | undefined,
  author: string,
  name: string,
): string {
  return `${type || 'plugin'}:${author}/${name}`;
}

/**
 * Build a lookup of already-installed extensions.
 *
 * The sidebar identifies each kind differently:
 * - plugins: `author/name`
 * - MCP servers: `author__name` (double underscore)
 * - skills: the bare skill name
 */
export function buildInstalledIndex(
  plugins: { id: string; hasUpdate?: boolean }[],
  mcpServers: { id: string }[],
  skills: { id: string }[],
): Map<string, InstalledIndexEntry> {
  const index = new Map<string, InstalledIndexEntry>();
  for (const plugin of plugins) {
    index.set(`plugin:${plugin.id}`, { hasUpdate: plugin.hasUpdate ?? false });
  }
  for (const server of mcpServers) {
    index.set(`mcp:${server.id.replace(/__/g, '/')}`, { hasUpdate: false });
  }
  for (const skill of skills) {
    index.set(`skill:${skill.id}`, { hasUpdate: false });
  }
  return index;
}

/**
 * Resolve whether a marketplace extension is installed.
 *
 * Marketplace entries always use `author/name`; skills may be stored under
 * their bare name, so both keys are checked for that case.
 */
export function resolveInstalledState(
  index: Map<string, InstalledIndexEntry>,
  extension: { type?: string; author: string; pluginName: string },
): MarketplaceInstalledState {
  const type = extension.type || 'plugin';
  const keys = [
    `${type}:${extension.author}/${extension.pluginName}`,
    `${type}:${extension.pluginName}`,
  ];
  for (const key of keys) {
    const entry = index.get(key);
    if (entry) {
      return { installed: true, hasUpdate: entry.hasUpdate };
    }
  }
  return { installed: false, hasUpdate: false };
}

/**
 * Reactive installed-extension index derived from the sidebar data context.
 * Recomputes automatically after an install finishes and the sidebar refreshes.
 */
export function useMarketplaceInstalledIndex(): Map<
  string,
  InstalledIndexEntry
> {
  const { plugins, mcpServers, skills } = useSidebarData();
  return useMemo(
    () => buildInstalledIndex(plugins, mcpServers, skills),
    [plugins, mcpServers, skills],
  );
}
