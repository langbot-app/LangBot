import { useMemo } from 'react';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import {
  buildInstalledIndex,
  type InstalledExtensionEntry,
} from './marketplace-installed';

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
