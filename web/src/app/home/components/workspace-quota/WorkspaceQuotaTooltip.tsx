import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { WorkspaceQuotaItem } from './useWorkspaceQuotaStatus';

export function WorkspaceQuotaTooltip({
  quota,
  resource,
  children,
  side = 'top',
}: {
  quota: WorkspaceQuotaItem;
  resource: string;
  children: ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
}) {
  const { t } = useTranslation();
  if (!quota.disabled) return children;
  const message = quota.loading
    ? t('limitation.quotaLoadingTooltip')
    : t('limitation.createDisabledTooltip', {
        resource,
        max: quota.max,
      });

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          aria-disabled="true"
          aria-label={message}
          className="inline-flex cursor-not-allowed rounded-sm focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          {children}
        </span>
      </TooltipTrigger>
      <TooltipContent side={side} className="max-w-72 text-center">
        {message}
      </TooltipContent>
    </Tooltip>
  );
}
