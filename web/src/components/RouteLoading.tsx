import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import langbotIcon from '@/app/assets/langbot-logo.webp';
import { cn } from '@/lib/utils';

/**
 * Full-viewport loading state shown while the app shell (route chunk and
 * Workspace session) is being prepared. Centered LangBot mark with a subtle
 * breathing animation; fades in after a short delay so fast loads show
 * nothing at all instead of a flash.
 */
export function PageLoading() {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 flex items-center justify-center bg-background"
    >
      <div className="route-loading-delayed flex flex-col items-center gap-5">
        <img
          src={langbotIcon}
          alt=""
          draggable={false}
          className="route-loading-breathe size-12 select-none rounded-xl"
        />
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  );
}

/**
 * Loading state for the content area inside an already-rendered layout
 * (e.g. a lazily loaded page under the /home shell).
 */
export function ContentLoading({ className }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'flex h-full w-full items-center justify-center',
        className,
      )}
    >
      <div className="route-loading-delayed">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
      <span className="sr-only">{t('common.loading')}</span>
    </div>
  );
}
