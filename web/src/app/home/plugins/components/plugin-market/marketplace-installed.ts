import { useMemo } from 'react';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';

/**
 * Marketplace extensions are addressed as `author/name`, while installed
 * extensions in the sidebar use slightly different identities per kind:
 * - plugins: `author/name`
 * - MCP servers: `author__name` (double underscore)
 * - skills: the bare skill name
 *
 * The index below normalises all of them to a single `type:author/name` shape
 * so a marketplace card can be matched with one lookup.
 */
export interface InstalledExtensionEntry {
  /** An installed extension of the same identity has a newer remote version. */
  hasUpdate: boolean;
}

export interface MarketplaceInstalledState {
  installed: boolean;
  hasUpdate: boolean;
}

/** Identity for a marketplace extension card. */
export function installedExtensionKey(
  type: string | undefined,
  author: string,
  name: string,
): string {
  return `${type || 'plugin'}:${author}/${name}`;
}

/**
 * Build the installed-extension lookup from the sidebar entity lists.
 *
 * Skills are indexed under both the bare name and the `author/name` form so a
 * marketplace skill card resolves regardless of how it was published.
 */
export function buildInstalledIndex(
  plugins: { id: string; hasUpdate?: boolean }[],
  mcpServers: { id: string }[],
  skills: { id: string }[],
): Map<string, InstalledExtensionEntry> {
  const index = new Map<string, InstalledExtensionEntry>();

  for (const plugin of plugins) {
    index.set(installedExtensionKey('plugin', ...splitIdentity(plugin.id)), {
      hasUpdate: plugin.hasUpdate ?? false,
    });
  }

  for (const server of mcpServers) {
    // MCP servers are keyed with `__`; normalise to `author/name`.
    index.set(
      installedExtensionKey(
        'mcp',
        ...splitIdentity(server.id.replace(/__/g, '/')),
      ),
      { hasUpdate: false },
    );
  }

  for (const skill of skills) {
    const entry: InstalledExtensionEntry = { hasUpdate: false };
    const identity = splitIdentity(skill.id);
    index.set(installedExtensionKey('skill', ...identity), entry);
    // Skills are stored under their bare name but marketplace cards always
    // carry `author/name`, so also index the name-only form.
    index.set(`skill:${skill.id}`, entry);
  }

  return index;
}

/** Split an `author/name` identity, tolerating a missing author. */
function splitIdentity(identity: string): [string, string] {
  const slash = identity.indexOf('/');
  if (slash < 0) return ['', identity];
  return [identity.slice(0, slash), identity.slice(slash + 1)];
}

/**
 * Resolve whether a marketplace extension is already installed.
 *
 * Unknown types fall back to `plugin`, matching the marketplace defaults.
 */
export function resolveInstalledState(
  index: Map<string, InstalledExtensionEntry>,
  extension: { type?: string; author: string; pluginName: string },
): MarketplaceInstalledState {
  const type = extension.type || 'plugin';
  const candidates = [
    `${type}:${extension.author}/${extension.pluginName}`,
    // Skills may be indexed under their bare name.
    `${type}:${extension.pluginName}`,
  ];

  for (const key of candidates) {
    const entry = index.get(key);
    if (entry) {
      return { installed: true, hasUpdate: entry.hasUpdate };
    }
  }

  return { installed: false, hasUpdate: false };
}

/**
 * Reactive installed-extension index derived from the sidebar data context.
 *
 * Because the index is memoised on the sidebar lists, a finished install (which
 * triggers a sidebar refresh) automatically re-evaluates the marketplace cards.
 */
export function useMarketplaceInstalledIndex(): Map<
  string,
  InstalledExtensionEntry
> {
  const { plugins, mcpServers, skills } = useSidebarData();

  return useMemo(
    () => buildInstalledIndex(plugins, mcpServers, skills),
    [plugins, mcpServers, skills],
  );
}
