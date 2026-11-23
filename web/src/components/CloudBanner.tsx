import { useTranslation } from 'react-i18next';
import { AlertCircle, Info, Wrench, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

import { backendClient } from '@/app/infra/http';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { ApiRespCloudBanner } from '@/app/infra/entities/api';
import {
  cloudBannerSignature,
  resolveCloudBannerCopy,
} from '@/lib/cloud-banner';

const RETRY_DELAYS_MS = [1000, 2000, 4000, 8000];
// The dismissal is bound to the copy that was dismissed, so publishing a new
// notice (or editing the current one) brings the banner back instead of
// leaving every returning reader permanently blind to it.
const DISMISSED_SIGNATURE_KEY = 'langbot_cloud_banner_dismissed';

const TONE_CLASSES: Record<string, string> = {
  info: 'bg-sky-50 dark:bg-sky-950/25 border-sky-200 dark:border-sky-900/50 text-sky-900 dark:text-sky-100 [&>svg]:text-sky-600 dark:[&>svg]:text-sky-400',
  warning:
    'bg-amber-50 dark:bg-amber-950/25 border-amber-200 dark:border-amber-900/50 text-amber-900 dark:text-amber-100 [&>svg]:text-amber-600 dark:[&>svg]:text-amber-400',
  maintenance:
    'bg-rose-50 dark:bg-rose-950/25 border-rose-200 dark:border-rose-900/50 text-rose-900 dark:text-rose-100 [&>svg]:text-rose-600 dark:[&>svg]:text-rose-400',
};

const TONE_ICONS: Record<string, typeof Info> = {
  info: Info,
  warning: AlertCircle,
  maintenance: Wrench,
};

const LOCALE_KEYS = [
  'zh-Hans',
  'zh-Hant',
  'en-US',
  'ja-JP',
  'th-TH',
  'vi-VN',
  'es-ES',
  'ru-RU',
] as const;

function currentLanguage(): string {
  const candidates = [
    typeof document !== 'undefined' ? document.documentElement.lang : '',
    typeof navigator !== 'undefined' ? navigator.language : '',
    ...LOCALE_KEYS,
  ];
  return (
    candidates.find(
      (value) => typeof value === 'string' && value.trim() !== '',
    ) || 'en-US'
  );
}

/**
 * Instance notice banner for Cloud deployments.
 *
 * Rendered once by the root layout so every route (login included) sees the
 * same announcement. It publishes its own height as ``--cloud-banner-height``
 * so the fixed app shell starts below it rather than underneath it.
 */
export function CloudBanner() {
  const { t, i18n } = useTranslation();
  const bannerRef = useRef<HTMLDivElement>(null);
  const [banner, setBanner] = useState<ApiRespCloudBanner | null>(null);
  const [dismissedSignature, setDismissedSignature] = useState<string | null>(
    () =>
      typeof window === 'undefined'
        ? null
        : window.sessionStorage.getItem(DISMISSED_SIGNATURE_KEY),
  );

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | undefined;

    const probe = async (attempt = 0) => {
      try {
        const info = await backendClient.getSystemInfo();
        if (cancelled) {
          return;
        }
        setBanner(
          info.deployment_mode === 'cloud' && info.cloud_banner?.enabled
            ? info.cloud_banner
            : null,
        );
      } catch {
        if (cancelled) {
          return;
        }
        // A cold start or a restarting backend must not hide an active notice
        // for the rest of the session, so retry with backoff and keep the last
        // known state in between.
        if (attempt < RETRY_DELAYS_MS.length) {
          retryTimer = window.setTimeout(
            () => void probe(attempt + 1),
            RETRY_DELAYS_MS[attempt],
          );
        }
      }
    };

    void probe();

    const recheck = () => {
      if (!cancelled) {
        void probe();
      }
    };
    window.addEventListener('focus', recheck);

    return () => {
      cancelled = true;
      clearTimeout(retryTimer);
      window.removeEventListener('focus', recheck);
    };
  }, []);

  const language = i18n?.language || currentLanguage();
  const customCopy = banner ? resolveCloudBannerCopy(banner, language) : null;
  const message = customCopy ?? (banner ? t('cloud_banner.message') : '');
  const signature = banner ? cloudBannerSignature(banner, message) : '';
  const visible =
    Boolean(banner && message) && signature !== dismissedSignature;

  // Publish the occupied height so the sidebar/shell can offset itself.
  useEffect(() => {
    const root = document.documentElement;
    if (!visible) {
      root.style.removeProperty('--cloud-banner-height');
      return;
    }
    const element = bannerRef.current;
    if (!element) {
      return;
    }
    const sync = () => {
      root.style.setProperty(
        '--cloud-banner-height',
        `${element.getBoundingClientRect().height}px`,
      );
    };
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(element);
    return () => {
      observer.disconnect();
      root.style.removeProperty('--cloud-banner-height');
    };
  }, [visible, signature]);

  const dismiss = useCallback(() => {
    setDismissedSignature(signature);
    try {
      window.sessionStorage.setItem(DISMISSED_SIGNATURE_KEY, signature);
    } catch {
      // Private-mode storage failures must not break the dismissal itself.
    }
  }, [signature]);

  if (!banner || !visible) {
    return null;
  }

  const tone = banner.level in TONE_CLASSES ? banner.level : 'info';
  const Icon = TONE_ICONS[tone];

  return (
    <Alert
      ref={bannerRef}
      className={`relative z-40 rounded-none border-x-0 border-t-0 py-2 ${TONE_CLASSES[tone]}`}
    >
      <Icon />
      <AlertDescription className="text-sm">
        <div className="flex w-full items-start gap-3">
          <span className="flex-1">
            {customCopy ? (
              <>
                {customCopy}{' '}
                {banner.show_links && (
                  <a
                    href={banner.dedicated_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium underline hover:opacity-80"
                  >
                    {t('cloud_banner.cta_dedicated')}
                  </a>
                )}
              </>
            ) : (
              <>
                {t('cloud_banner.message')}{' '}
                {banner.show_links && (
                  <>
                    <a
                      href={banner.dedicated_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium underline hover:opacity-80"
                    >
                      {t('cloud_banner.dedicated_link')}
                    </a>{' '}
                    {t('cloud_banner.or')}{' '}
                    <a
                      href={banner.repository_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium underline hover:opacity-80"
                    >
                      {t('cloud_banner.self_hosted_link')}
                    </a>
                  </>
                )}
                {t('cloud_banner.period')}
              </>
            )}
          </span>
          {banner.dismissible && (
            <button
              type="button"
              onClick={dismiss}
              className="-mr-2 -mt-1 shrink-0 p-1 opacity-80 hover:opacity-100"
              aria-label={t('cloud_banner.dismiss')}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
}
