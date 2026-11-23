import type { ApiRespCloudBanner } from '@/app/infra/entities/api';

/**
 * Map an i18next locale (`zh-Hans`) to the config key form (`zh_hans`).
 *
 * `config.yaml` exposes per-language copy through the `CLOUD__...` environment
 * override namespace, which only splits on `__`, so languages are stored with
 * underscores on the backend.
 */
export function cloudBannerLanguageKey(language: string): string {
  return language
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

/**
 * Resolve the copy for one language: the configured override for that
 * language, then the configured English copy, then `null` so the caller falls
 * back to the built-in translated message with its inline links.
 */
export function resolveCloudBannerCopy(
  banner: Pick<ApiRespCloudBanner, 'content'>,
  language: string,
): string | null {
  const content = banner?.content || {};
  for (const key of [cloudBannerLanguageKey(language), 'en_us']) {
    const value = content[key];
    if (typeof value === 'string' && value.trim() !== '') {
      return value.trim();
    }
  }
  return null;
}

/**
 * Identity of the notice currently on screen. A dismissal is bound to this
 * value so publishing different copy brings the banner back, while a reload
 * of the same notice stays dismissed.
 */
export function cloudBannerSignature(
  banner: Pick<ApiRespCloudBanner, 'level'>,
  message: string,
): string {
  return `${banner.level}:${message}`;
}
