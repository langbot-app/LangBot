"use client";

import { useEffect, type ReactNode } from "react";
import { I18nProvider, type I18nProviderProps } from "fumadocs-ui/contexts/i18n";
import { useRouter } from "fumapress/client";
import { preferredLocale, saveLocale, localeDestination, LOCALES } from "./locale-preference.mjs";

/** Reuse both stock selectors via their native onLocaleChange callback. */
export function LocalePreferenceProvider({ i18n, children }: {
  i18n: I18nProviderProps;
  children: ReactNode;
}) {
  const router = useRouter();
  useEffect(() => { preferredLocale(); }, []);
  return <I18nProvider {...i18n} onLocaleChange={(locale) => {
    if (!LOCALES.includes(locale)) return;
    saveLocale(locale);
    const alternates = Array.from(document.querySelectorAll<HTMLLinkElement>('link[rel="alternate"][hreflang]'))
      .map((link) => ({ language: link.hreflang, href: link.href }));
    // Fumapress adds /docs itself. Use canonical hreflang routes for API pages
    // whose translated slugs differ, and a guide when no translation exists.
    const target = localeDestination(locale, alternates, location.origin);
    router.push(target.slice("/docs".length) + location.search + location.hash);
  }}>{children}</I18nProvider>;
}
