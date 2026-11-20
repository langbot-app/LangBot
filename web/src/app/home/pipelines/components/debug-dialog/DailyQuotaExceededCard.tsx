import { CircleAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { Message, MessageError } from '@/app/infra/entities/message';
import { useCurrentWorkspace } from '@/app/infra/http';
import {
  formatQuotaReset,
  openCloudPlans,
} from '@/app/home/components/workspace-quota/useDailyMessageQuota';

export const DAILY_QUOTA_ERROR_CODE = 'daily_message_quota_exceeded';

export function isDailyQuotaError(
  message: Message,
): message is Message & { error: MessageError } {
  return (
    message.role === 'assistant' &&
    message.error?.error_code === DAILY_QUOTA_ERROR_CODE
  );
}

/** Replaces the bot bubble when the pipeline rejected a message over quota. */
export function DailyQuotaExceededCard({
  error,
  compact,
}: {
  error: MessageError;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const workspace = useCurrentWorkspace();
  const quota = error.quota;
  const canUpgrade = workspace?.workspace.source === 'cloud_projection';

  return (
    <div
      role="alert"
      data-daily-quota-error
      className={cn(
        'w-full max-w-md rounded-2xl rounded-bl-none border border-destructive/30 bg-destructive/5',
        compact ? 'p-3 text-sm' : 'p-4',
      )}
    >
      <div className="flex items-start gap-3">
        <CircleAlert className="mt-0.5 size-5 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1 space-y-1.5">
          <p className="font-medium text-destructive">
            {t('dailyMessageQuota.errorTitle')}
          </p>
          <p className="text-sm text-muted-foreground">
            {quota
              ? t('dailyMessageQuota.errorBody', {
                  limit: quota.limit.toLocaleString(),
                  time: formatQuotaReset(t, quota.resets_at),
                })
              : error.message}
          </p>
          {quota && quota.limit > 0 && (
            <div className="flex items-center gap-2 pt-1">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-destructive/15">
                <div className="h-full w-full rounded-full bg-destructive" />
              </div>
              <span className="text-xs tabular-nums text-destructive">
                {t('dailyMessageQuota.usage', {
                  used: quota.used.toLocaleString(),
                  limit: quota.limit.toLocaleString(),
                })}
              </span>
            </div>
          )}
          {canUpgrade && (
            <div className="pt-2">
              <Button size="sm" onClick={openCloudPlans}>
                {t('dailyMessageQuota.errorUpgrade')}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
