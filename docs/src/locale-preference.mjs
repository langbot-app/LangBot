export const STORAGE_KEY = "langbot-docs-locale";
export const LOCALES = ["en", "zh", "ja"];

export function detectLocale(saved, languages = []) {
  if (LOCALES.includes(saved)) return saved;
  for (const language of languages) {
    if (typeof language !== "string") continue;
    const base = language.toLowerCase().split("-")[0];
    if (LOCALES.includes(base)) return base;
  }
  return "en";
}

export function saveLocale(locale, browser = window) {
  if (!LOCALES.includes(locale)) return;
  try { browser.localStorage.setItem(STORAGE_KEY, locale); } catch { /* Private/blocked storage. */ }
}

export function preferredLocale(browser = window) {
  let saved;
  try { saved = browser.localStorage.getItem(STORAGE_KEY); } catch { /* Storage may throw on access. */ }
  const locale = detectLocale(saved, browser.navigator.languages?.length
    ? browser.navigator.languages : [browser.navigator.language]);
  // Initialize from the browser, never from an explicit shared page's locale.
  if (saved !== locale) saveLocale(locale, browser);
  return locale;
}

export function localeDestination(locale, alternates, origin) {
  if (!LOCALES.includes(locale)) locale = "en";
  for (const alternate of alternates) {
    if (alternate.language.toLowerCase().split("-")[0] !== locale) continue;
    try {
      const url = new URL(alternate.href, origin);
      // Exported canonicals point to production even on previews. Only accept
      // our canonical host or the current origin, and an exact locale prefix.
      if ((url.origin === origin || url.origin === "https://langbot.app") &&
          url.pathname.startsWith(`/docs/${locale}/`)) return url.pathname;
    } catch { /* Ignore malformed alternate metadata. */ }
  }
  return `/docs/${locale}/insight/guide`;
}

export function enterDocs(browser = window) {
  if (!/^\/docs\/?$/.test(browser.location.pathname)) return;
  const locale = preferredLocale(browser);
  browser.location.replace(`/docs/${locale}/insight/guide${browser.location.search}${browser.location.hash}`);
}
