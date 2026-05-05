/**
 * Unified i18n utilities for the Workflow module.
 *
 * The backend API returns label dicts with keys like `zh-CN`, `en`,
 * while node-configs use `zh_Hans`, `en_US`, and the i18next system
 * uses `zh-Hans`, `en-US`.  This module normalises **all** variants
 * into a single lookup so every consumer gets the right value without
 * maintaining its own fallback chain.
 */

import i18n from 'i18next';
import { I18nObject } from '@/app/infra/entities/common';

// ─── Key normalisation ──────────────────────────────────────────────

/**
 * All known aliases for a given canonical locale, ordered by priority.
 * When the user's language starts with a prefix we try every alias in
 * order until one hits.
 */
const ZH_KEYS = ['zh-CN', 'zh_Hans', 'zh-Hans', 'zh_CN', 'zh'] as const;
const EN_KEYS = ['en-US', 'en_US', 'en'] as const;

/**
 * Resolve a translated string from a label dict that may use **any**
 * combination of `zh-CN`, `zh_Hans`, `en`, `en-US`, `en_US` etc.
 *
 * Works with both `Record<string, string>` (backend) and the typed
 * `I18nObject` (node-configs).
 *
 * Optionally falls through to `i18n.t(value)` when the stored value
 * itself looks like an i18n key (e.g. `"workflows.nodes.llmCall"`).
 */
export function resolveI18nLabel(
  obj: Record<string, string> | I18nObject | undefined | null,
): string {
  if (!obj || typeof obj !== 'object') return '';

  const record = obj as Record<string, string>;
  const lang = i18n.language; // e.g. "zh-Hans", "en-US"

  // 1. Try exact match with current language
  if (record[lang]) return maybeTranslateKey(record[lang]);

  // 2. Try aliases for the current language family
  const primary = lang.startsWith('zh') ? ZH_KEYS : EN_KEYS;
  const fallback = lang.startsWith('zh') ? EN_KEYS : ZH_KEYS;

  for (const k of primary) {
    if (record[k]) return maybeTranslateKey(record[k]);
  }
  for (const k of fallback) {
    if (record[k]) return maybeTranslateKey(record[k]);
  }

  // 3. Last resort – grab the first non-empty value in the dict
  const first = Object.values(record).find((v) => typeof v === 'string' && v);
  return first ? maybeTranslateKey(first) : '';
}

// ─── i18n key detection ─────────────────────────────────────────────

const I18N_KEY_PREFIXES = ['workflows.', 'common.', 'bots.', 'models.'];

/**
 * If `value` looks like an i18n key (e.g. `"workflows.nodes.llmCall"`)
 * translate it via i18next; otherwise return it unchanged.
 */
export function maybeTranslateKey(value: string): string {
  if (!value) return value;
  if (I18N_KEY_PREFIXES.some((p) => value.startsWith(p))) {
    const translated = i18n.t(value);
    if (translated !== value) return translated;
  }
  return value;
}
