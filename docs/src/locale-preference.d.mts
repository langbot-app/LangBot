export const STORAGE_KEY: string;
export const LOCALES: readonly string[];
export function detectLocale(saved: unknown, languages?: readonly unknown[]): string;
export function saveLocale(locale: string, browser?: Window): void;
export function preferredLocale(browser?: Window): string;
export function localeDestination(locale: string, alternates: {language: string; href: string}[], origin: string): string;
export function enterDocs(browser?: Window): void;
