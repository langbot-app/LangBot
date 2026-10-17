import { useEffect, useState } from 'react';

import { httpClient } from '@/app/infra/http';

/**
 * Resolve the icon of an *installed* plugin in every deployment.
 *
 * The Core's public `/icon` route only exists in single-workspace (OSS)
 * installs; in multi-Workspace deployments it 404s, so installed-plugin
 * surfaces must go through the authenticated `/authenticated-icon` route and
 * stream the bytes as a blob object URL.
 *
 * - Core backend client: blob-fetch `getAuthenticatedPluginIconURL` and cache
 *   the resulting object URL per `author/name` (module-level, shared across
 *   every mounted consumer of the same icon).
 * - Cloud/Space marketplace surfaces: callers that already resolved a
 *   marketplace URL pass it as `marketplaceURL`; it is returned verbatim and
 *   no blob fetch happens.
 * - Returns `null` while loading / when the plugin has no icon, so callers
 *   keep rendering their existing fallback.
 *
 * Object URLs are revoked once the last subscriber unmounts (or the last
 * subscriber's fetch settles with no remaining subscriber).
 */

type CachedIcon = { url: string };

// Resolved object URLs, keyed by `author/name`.
const iconCache = new Map<string, CachedIcon>();
// In-flight authenticated fetches, de-duplicated per key.
const inflightIcons = new Map<string, Promise<string | null>>();
// Mounted subscriber count per key, so we only revoke when nobody needs it.
const iconRefCounts = new Map<string, number>();

function loadIcon(
  key: string,
  author: string,
  name: string,
): Promise<string | null> {
  const existing = inflightIcons.get(key);
  if (existing) return existing;

  const request = httpClient
    .getAuthenticatedPluginIconURL(author, name)
    .catch(() => null)
    .finally(() => {
      inflightIcons.delete(key);
    });
  inflightIcons.set(key, request);
  return request;
}

export function useInstalledPluginIcon(
  author?: string | null,
  name?: string | null,
  marketplaceURL?: string | null,
): string | null {
  const key = author && name ? `${author}/${name}` : null;
  const [url, setUrl] = useState<string | null>(
    () => marketplaceURL ?? (key ? (iconCache.get(key)?.url ?? null) : null),
  );

  useEffect(() => {
    if (marketplaceURL) {
      // Cloud/Space marketplace surface: already resolved upstream.
      setUrl(marketplaceURL);
      return;
    }
    if (!key || !author || !name) {
      setUrl(null);
      return;
    }

    let active = true;
    iconRefCounts.set(key, (iconRefCounts.get(key) ?? 0) + 1);

    const cached = iconCache.get(key);
    if (cached) {
      setUrl(cached.url);
    } else {
      setUrl(null);
      void loadIcon(key, author, name).then((objectURL) => {
        if (!objectURL) return;
        // The last subscriber may have left while the fetch was in flight.
        if (iconRefCounts.get(key) === undefined) {
          URL.revokeObjectURL(objectURL);
          return;
        }
        const current = iconCache.get(key);
        if (current) {
          // Another subscriber resolved first; share its object URL.
          if (current.url !== objectURL) URL.revokeObjectURL(objectURL);
          if (active) setUrl(current.url);
          return;
        }
        iconCache.set(key, { url: objectURL });
        if (active) setUrl(objectURL);
      });
    }

    return () => {
      active = false;
      const remaining = (iconRefCounts.get(key) ?? 1) - 1;
      if (remaining > 0) {
        iconRefCounts.set(key, remaining);
        return;
      }
      iconRefCounts.delete(key);
      const entry = iconCache.get(key);
      if (entry) {
        iconCache.delete(key);
        URL.revokeObjectURL(entry.url);
      }
    };
  }, [key, author, name, marketplaceURL]);

  return marketplaceURL ?? url;
}
