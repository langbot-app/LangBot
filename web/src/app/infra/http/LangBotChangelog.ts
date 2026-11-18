/**
 * Release notes published on https://langbot.app/changelog.
 *
 * The landing site serves its curated, user-facing changelog as a public
 * CORS-enabled JSON feed. It lists stable Core releases only, newest first,
 * and every entry carries zh / en / ja text.
 */

export const LANGBOT_CHANGELOG_FEED_URL = 'https://langbot.app/changelog.json';
const LANGBOT_SITE_URL = 'https://langbot.app';
const FETCH_TIMEOUT_MS = 8000;

export type ChangelogLocale = 'zh' | 'en' | 'ja';
export type ChangelogChangeType =
  'new' | 'improved' | 'changed' | 'fixed' | 'security';

export type ChangelogText = Partial<Record<ChangelogLocale, string>>;

export interface ChangelogItem {
  type: ChangelogChangeType;
  text: ChangelogText;
}

export interface ChangelogRelease {
  version: string;
  date: string;
  summary: ChangelogText;
  items: ChangelogItem[];
}

export const CHANGELOG_TYPE_ORDER: ChangelogChangeType[] = [
  'new',
  'improved',
  'changed',
  'security',
  'fixed',
];

const VERSION_RE = /^\d+\.\d+\.\d+$/;

function isRelease(value: unknown): value is ChangelogRelease {
  if (!value || typeof value !== 'object') return false;
  const r = value as Record<string, unknown>;
  return (
    typeof r.version === 'string' &&
    VERSION_RE.test(r.version) &&
    typeof r.date === 'string' &&
    Array.isArray(r.items)
  );
}

export async function fetchLangBotChangelog(): Promise<ChangelogRelease[]> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const resp = await fetch(LANGBOT_CHANGELOG_FEED_URL, {
      signal: controller.signal,
      credentials: 'omit',
    });
    if (!resp.ok) {
      throw new Error(`changelog feed returned HTTP ${resp.status}`);
    }
    const data = (await resp.json()) as { releases?: unknown };
    if (!Array.isArray(data.releases)) {
      throw new Error('changelog feed has no releases array');
    }
    return data.releases.filter(isRelease).map((r) => ({
      ...r,
      summary: r.summary ?? {},
      items: r.items.filter(
        (item) =>
          item &&
          typeof item === 'object' &&
          CHANGELOG_TYPE_ORDER.includes(item.type) &&
          item.text &&
          typeof item.text === 'object',
      ),
    }));
  } finally {
    window.clearTimeout(timer);
  }
}

/** Map a WebUI i18n language to the closest changelog locale. */
export function changelogLocaleFor(language: string | undefined) {
  if (!language) return 'en' as const;
  if (language.startsWith('zh')) return 'zh' as const;
  if (language.startsWith('ja')) return 'ja' as const;
  return 'en' as const;
}

export function pickChangelogText(
  text: ChangelogText | undefined,
  locale: ChangelogLocale,
): string {
  if (!text) return '';
  return text[locale] || text.en || text.zh || text.ja || '';
}

export function changelogPageUrl(locale: ChangelogLocale, version?: string) {
  return version
    ? `${LANGBOT_SITE_URL}/${locale}/changelog/v${version}`
    : `${LANGBOT_SITE_URL}/${locale}/changelog`;
}
