/**
 * Compare two version strings and determine if the first is newer than the second.
 * Supports semantic versioning format (e.g., "1.2.3", "1.0.0-beta.1").
 *
 * @param version1 - The version to compare (potentially newer)
 * @param version2 - The version to compare against (base version)
 * @returns true if version1 is newer than version2, false otherwise
 */
export function isNewerVersion(version1: string, version2: string): boolean {
  if (!version1 || !version2) {
    return false;
  }

  // Remove any leading 'v' prefix
  const v1 = version1.replace(/^v/, '');
  const v2 = version2.replace(/^v/, '');

  // Split into main version and pre-release parts
  const [main1, pre1] = v1.split('-');
  const [main2, pre2] = v2.split('-');

  // Split main version into numeric parts
  const parts1 = main1.split('.').map((p) => parseInt(p, 10) || 0);
  const parts2 = main2.split('.').map((p) => parseInt(p, 10) || 0);

  // Normalize length
  const maxLen = Math.max(parts1.length, parts2.length);
  while (parts1.length < maxLen) parts1.push(0);
  while (parts2.length < maxLen) parts2.push(0);

  // Compare main version parts
  for (let i = 0; i < maxLen; i++) {
    if (parts1[i] > parts2[i]) return true;
    if (parts1[i] < parts2[i]) return false;
  }

  // Main versions are equal, compare pre-release
  // A version without pre-release is newer than one with pre-release
  if (!pre1 && pre2) return true;
  if (pre1 && !pre2) return false;
  if (!pre1 && !pre2) return false;

  // Both have pre-release, compare lexicographically
  return pre1! > pre2!;
}
