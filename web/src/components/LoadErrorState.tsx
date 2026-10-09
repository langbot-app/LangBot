import { useState, type ReactNode } from 'react';
import { FileWarning, RefreshCw } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export default function LoadErrorState({
  title,
  description,
  icon,
  onRetry,
  busy = false,
  compact = false,
  className,
}: {
  title?: string;
  description?: string;
  icon?: ReactNode;
  onRetry?: () => unknown;
  busy?: boolean;
  compact?: boolean;
  className?: string;
}) {
  const { t } = useTranslation();
  const [retrying, setRetrying] = useState(false);

  async function retry() {
    if (!onRetry || retrying || busy) return;
    setRetrying(true);
    try {
      await onRetry();
    } catch {
      // The owning view retains its error state if the request fails again.
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div
      role="alert"
      aria-busy={retrying || busy}
      className={cn(
        'flex w-full items-center justify-center px-4',
        compact ? 'py-4' : 'min-h-64 py-10',
        className,
      )}
    >
      <div className="flex w-full max-w-md items-start gap-4 rounded-xl border bg-card p-5 text-card-foreground shadow-sm sm:p-6">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
          {icon ?? <FileWarning className="size-5" aria-hidden="true" />}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <p className="break-words text-sm font-medium leading-6">
            {title ?? t('common.loadFailedTitle')}
          </p>
          <p className="break-words text-sm leading-6 text-muted-foreground">
            {description ?? t('common.loadFailedHint')}
          </p>
          {onRetry && (
            <div className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={retrying || busy}
                onClick={() => void retry()}
              >
                <RefreshCw
                  aria-hidden="true"
                  className={cn('size-3.5', (retrying || busy) && 'animate-spin motion-reduce:animate-none')}
                />
                {retrying || busy ? t('common.loading') : t('common.retry')}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
