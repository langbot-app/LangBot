import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const APP_NAME = 'LangBot';

// Map a route path to the i18n key used for its (type-level) document title.
// Reuses existing translation keys so titles stay in sync with the sidebar and
// page headers across all locales. The /home/* section is intentionally NOT
// listed here: those titles are driven from inside HomeLayout, which has access
// to the currently-selected sub-entity name (detailEntityName) via context and
// renders "<entity> · <type> · LangBot".
const ROUTE_TITLE_KEYS: { match: (path: string) => boolean; key: string }[] = [
  { match: (p) => p === '/login', key: 'common.login' },
  { match: (p) => p === '/register', key: 'register.title' },
  { match: (p) => p === '/reset-password', key: 'resetPassword.title' },
  { match: (p) => p === '/wizard', key: 'sidebar.quickStart' },
];

/**
 * Builds a "<...parts> · LangBot" document title from the given page-name parts,
 * dropping empties. Falls back to the bare app name when no parts resolve.
 */
export function buildDocumentTitle(
  ...parts: (string | null | undefined)[]
): string {
  const clean = parts.filter((p): p is string => !!p && p.trim().length > 0);
  return clean.length > 0 ? `${clean.join(' · ')} · ${APP_NAME}` : APP_NAME;
}

/**
 * Imperatively set the document title. Centralized so the format stays
 * consistent across the top-level layout and the home layout.
 */
export function setDocumentTitle(
  ...parts: (string | null | undefined)[]
): void {
  document.title = buildDocumentTitle(...parts);
}

/**
 * Top-level document-title driver for routes OUTSIDE the /home section
 * (login, register, reset-password, wizard, and any unmapped route). The /home
 * section manages its own title from HomeLayout so it can include the selected
 * sub-entity name. Re-runs on navigation and language change so the title stays
 * localized.
 */
export function useDocumentTitle() {
  const { pathname } = useLocation();
  const { t, i18n } = useTranslation();

  useEffect(() => {
    // Home routes are handled by HomeLayout (it has the entity name in context).
    if (pathname.startsWith('/home')) return;

    const entry = ROUTE_TITLE_KEYS.find((e) => e.match(pathname));
    if (!entry) {
      document.title = APP_NAME;
      return;
    }
    const pageName = t(entry.key);
    // Guard against an unresolved key (t returns the key itself).
    setDocumentTitle(pageName !== entry.key ? pageName : null);
  }, [pathname, t, i18n.language]);
}
