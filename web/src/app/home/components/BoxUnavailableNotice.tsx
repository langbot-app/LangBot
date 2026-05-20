import { useTranslation } from 'react-i18next';
import { Info, ShieldAlert } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';

/**
 * Banner shown when a feature depends on the Box sandbox runtime but it is
 * currently disabled in config or otherwise unavailable. Pass the ``hint``
 * key returned by ``useBoxStatus`` (``'boxDisabled' | 'boxUnavailable'``).
 *
 * Renders nothing when there is no hint — safe to drop at the top of any
 * page that may or may not need to surface the notice.
 */
export interface BoxUnavailableNoticeProps {
  hint: 'boxDisabled' | 'boxUnavailable' | null;
  /** Specific failure reason from the backend (``connector_error``). Shown
   *  on a dedicated line so the user sees WHY (e.g. ``Configured sandbox
   *  backend "nsjail" is unavailable``) instead of just the generic
   *  "unavailable" wording. Ignored when ``hint === 'boxDisabled'``
   *  because the disabled-by-config message already carries the reason. */
  reason?: string | null;
  className?: string;
}

export function BoxUnavailableNotice({
  hint,
  reason,
  className,
}: BoxUnavailableNoticeProps) {
  const { t } = useTranslation();
  if (!hint) return null;

  const variant = hint === 'boxDisabled' ? 'default' : 'destructive';
  const Icon = hint === 'boxDisabled' ? Info : ShieldAlert;
  const showReason = hint === 'boxUnavailable' && reason;

  return (
    <Alert variant={variant} className={className}>
      <Icon className="h-4 w-4" />
      <AlertDescription className="space-y-1">
        <div>{t(`monitoring.${hint}`)}</div>
        {showReason && (
          <div className="text-xs font-mono opacity-80 break-all">{reason}</div>
        )}
        <div className="text-xs opacity-80">
          {t('monitoring.boxRequiredHint')}
        </div>
      </AlertDescription>
    </Alert>
  );
}

export default BoxUnavailableNotice;
