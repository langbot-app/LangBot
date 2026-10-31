/**
 * Marketplace extensions are addressed as `author/name`. Installed extensions
 * only carry a publisher-scoped identity for plugins and MCP servers:
 * - plugins: `author/name`
 * - MCP servers: `author__name` (double underscore)
 * - skills: the bare skill name, with no publisher recorded
 *
 * The index below normalises those to a single `type:author/name` shape so a
 * marketplace card can be matched with one lookup.
 *
 * Skills are deliberately *not* indexable: the backend derives a skill's name
 * from the `name` field in its own SKILL.md (falling back to the package
 * directory name), so a skill published by `alice/review` and one published by
 * `bob/review` both install as the plain name `review`. Matching on that bare
 * name would mark every publisher's `review` as installed once any single one
 * of them is. Until the installed skill carries its publisher, a skill card
 * cannot be resolved authoritatively, and so is reported as not installed.
 *
 * This module is intentionally free of React imports so it can be unit tested
 * directly; the reactive hook lives in `useMarketplaceInstalledIndex.ts`.
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

/** Split an `author/name` identity, tolerating a missing author. */
function splitIdentity(identity: string): [string, string] {
  const slash = identity.indexOf('/');
  if (slash < 0) return ['', identity];
  return [identity.slice(0, slash), identity.slice(slash + 1)];
}

/**
 * Build the installed-extension lookup from the sidebar entity lists.
 *
 * Skills are intentionally omitted — see the module header for why a bare
 * skill name cannot be attributed to a publisher.
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

  // `skills` is accepted for call-site symmetry (and so the surrounding
  // useMemo still re-runs when the list changes) but contributes nothing.
  void skills;

  return index;
}

/**
 * Resolve whether a marketplace extension is already installed.
 *
 * Matching requires the full `type:author/name` identity, so a card is only
 * marked installed when the installed extension carries the same publisher.
 * Unknown types fall back to `plugin`, matching the marketplace defaults.
 */
export function resolveInstalledState(
  index: Map<string, InstalledExtensionEntry>,
  extension: { type?: string; author: string; pluginName: string },
): MarketplaceInstalledState {
  const type = extension.type || 'plugin';
  const entry = index.get(
    `${type}:${extension.author}/${extension.pluginName}`,
  );

  if (entry) {
    return { installed: true, hasUpdate: entry.hasUpdate };
  }

  return { installed: false, hasUpdate: false };
}
