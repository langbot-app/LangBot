/**
 * LangBot Core version handling for the update prompt.
 *
 * The backend reports `v` + the installed package version, which Python
 * normalizes to PEP 440 (`4.11.0b6`, `4.11.0rc1`, `4.12.0.dev0`,
 * `4.11.8.post1`, `4.11.8+custom`). Git tags and hand-edited builds may also
 * use semver-style suffixes (`4.11.0-beta.6`, `4.3.0.beta1`). The langbot.app
 * changelog lists stable `X.Y.Z` releases only.
 */

export interface CoreVersion {
  major: number;
  minor: number;
  patch: number;
  /**
   * True for pre-releases and dev builds (`b1`, `rc1`, `.dev0`,
   * `-beta.6`, ...). They sort before the matching stable release.
   * Post releases and local builds (`.post1`, `+custom`) count as that
   * stable release.
   */
  prerelease: boolean;
}

const VERSION_RE = /^v?(\d+)\.(\d+)\.(\d+)(.*)$/i;
const STABLE_SUFFIX_RE = /^(?:[.-]?post\d*)?(?:\+.*)?$/i;

/** Parse a Core version; returns null when it is not `X.Y.Z[suffix]`. */
export function parseCoreVersion(
  raw: string | null | undefined,
): CoreVersion | null {
  const match = VERSION_RE.exec((raw ?? '').trim());
  if (!match) return null;
  const [, major, minor, patch, suffix] = match;
  return {
    major: Number(major),
    minor: Number(minor),
    patch: Number(patch),
    prerelease: !STABLE_SUFFIX_RE.test(suffix),
  };
}

/** Compare release triples, ignoring pre-release state. */
function compareRelease(a: CoreVersion, b: CoreVersion) {
  return a.major - b.major || a.minor - b.minor || a.patch - b.patch;
}

/**
 * Whether stable release `candidate` should be offered to a Core running
 * `current`. An unparseable `current` (a hand-edited version) never gets an
 * update prompt, because there is no reliable way to order it.
 */
export function isCoreUpdate(
  candidate: string | null | undefined,
  current: string | null | undefined,
): boolean {
  const next = parseCoreVersion(candidate);
  const running = parseCoreVersion(current);
  if (!next || !running) return false;
  const diff = compareRelease(next, running);
  if (diff !== 0) return diff > 0;
  // Same X.Y.Z: the stable release supersedes a pre-release of it.
  return running.prerelease && !next.prerelease;
}

/**
 * The stable `X.Y.Z` whose notes describe `current`, or null. Post releases
 * and local builds map to their base release; pre-releases and dev builds
 * have no published notes yet.
 */
export function coreReleaseOf(current: string | null | undefined) {
  const v = parseCoreVersion(current);
  if (!v || v.prerelease) return null;
  return `${v.major}.${v.minor}.${v.patch}`;
}
