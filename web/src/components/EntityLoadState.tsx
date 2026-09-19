import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

export default function EntityLoadState({
  error = false,
  onRetry,
}: {
  error?: boolean;
  onRetry?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div
      role={error ? 'alert' : 'status'}
      aria-busy={!error}
      className="flex min-h-40 flex-1 flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground"
    >
      {error ? (
        <>
          <p>{t('common.loadFailed')}</p>
          {onRetry && (
            <Button type="button" variant="outline" onClick={onRetry}>
              {t('common.retry')}
            </Button>
          )}
        </>
      ) : (
        <>
          <Loader2 aria-hidden="true" className="size-5 animate-spin" />
          <p>{t('common.loading')}</p>
        </>
      )}
    </div>
  );
}
