/**
 * Resolves the documentation URL for a given adapter from its
 * spec.help_links map, selecting the best match for the current locale
 * with a fallback to English.
 */
export function getAdapterDocUrl(
  helpLinks: Record<string, string> | undefined,
  locale: string,
): string | null {
  if (!helpLinks) return null;

  // Map locale to simplified language key
  let lang: string;
  if (locale.startsWith('zh')) {
    lang = 'zh';
  } else if (locale.startsWith('ja')) {
    lang = 'ja';
  } else {
    lang = 'en';
  }

  return helpLinks[lang] ?? helpLinks['en'] ?? null;
}
