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
  /** Optional extra context line (e.g. the specific consumer name). */
  context?: string;
  /** When true, render as muted; default uses the destructive variant only
   * for failed (boxUnavailable) state so a deliberate disable looks calm. */
  className?: string;
}

export function BoxUnavailableNotice({
  hint,
  context,
  className,
}: BoxUnavailableNoticeProps) {
  const { t } = useTranslation();
  if (!hint) return null;

  const variant = hint === 'boxDisabled' ? 'default' : 'destructive';
  const Icon = hint === 'boxDisabled' ? Info : ShieldAlert;

  return (
    <Alert variant={variant} className={className}>
      <Icon className="h-4 w-4" />
      <AlertDescription className="space-y-1">
        <div>{t(`monitoring.${hint}`)}</div>
        {context && <div className="text-xs opacity-80">{context}</div>}
        <div className="text-xs opacity-80">
          {t('monitoring.boxRequiredHint')}
        </div>
      </AlertDescription>
    </Alert>
  );
}

export default BoxUnavailableNotice;
