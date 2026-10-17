import { useTranslation } from 'react-i18next';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

export default function WorkspacePlanBadge({
  planName,
}: {
  planName?: string | null;
}) {
  const { t } = useTranslation();
  const isPaidPlan =
    Boolean(planName?.trim()) && planName?.trim().toLowerCase() !== 'free';

  return (
    <Badge
      variant="outline"
      className={cn(
        'text-[11px] uppercase',
        isPaidPlan
          ? 'border-blue-200 bg-blue-50 font-semibold text-blue-700 dark:border-blue-400/30 dark:bg-blue-500/15 dark:text-blue-300'
          : 'bg-muted text-muted-foreground',
      )}
    >
      {planName || t('workspace.planUnavailable')}
    </Badge>
  );
}
