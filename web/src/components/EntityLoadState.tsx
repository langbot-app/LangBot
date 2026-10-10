import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import LoadErrorState from '@/components/LoadErrorState';

export default function EntityLoadState({
  error = false,
  onRetry,
}: {
  error?: boolean;
  onRetry?: () => void;
}) {
  const { t } = useTranslation();
  if (error) return <LoadErrorState onRetry={onRetry} className="flex-1" />;
  return (
    <div
      role="status"
      aria-busy="true"
      className="flex min-h-40 flex-1 flex-col items-center justify-center gap-3 p-6 text-sm text-muted-foreground"
    >
      <Loader2 aria-hidden="true" className="size-5 animate-spin" />
      <p>{t('common.loading')}</p>
    </div>
  );
}
