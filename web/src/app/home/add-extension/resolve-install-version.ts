/**
 * Resolve which marketplace version a Space one-click install link may
 * install on this Core. The link carries the version Space's web page
 * showed (its latest), but the web page does not know the Core version.
 */

export interface VersionEntry {
  version: string;
  /** Present only when Space evaluated the request's Core version. */
  compatible?: boolean;
}

export interface VersionDetail {
  latest_version?: string;
  /** null: no compatible release; undefined: Space predates the field. */
  compatible_version?: string | null;
}

export type InstallVersionResolution =
  | { kind: 'install'; version: string }
  | { kind: 'switched'; version: string; requested: string }
  | { kind: 'none' };

export function resolveInstallVersion(
  requested: string,
  versions: VersionEntry[] | null | undefined,
  detail: VersionDetail | null | undefined,
): InstallVersionResolution {
  const compatibleVersion = detail?.compatible_version;
  // Older Space: no compatibility data, keep the old behaviour.
  if (compatibleVersion === undefined) {
    const version = requested || detail?.latest_version || '';
    return version ? { kind: 'install', version } : { kind: 'none' };
  }

  if (requested) {
    const entry = versions?.find((v) => v.version === requested);
    // An entry without `compatible` means Space ignored the Core version
    // (absent or unparseable), so it applied no filter either.
    if (entry && entry.compatible !== false) {
      return { kind: 'install', version: requested };
    }
  }

  if (!compatibleVersion) return { kind: 'none' };
  if (!requested || requested === compatibleVersion) {
    return { kind: 'install', version: compatibleVersion };
  }
  return { kind: 'switched', version: compatibleVersion, requested };
}
