import { useId } from 'react';
import { TriangleAlert } from 'lucide-react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  isPluginIncompatible,
  type PluginCompatibility,
} from '@/app/infra/entities/plugin';

/** Human-readable declared range, e.g. "≥ 4.12, ≤ 4.x". */
export function compatibilityRangeText(
  t: TFunction,
  min: string | null | undefined,
  max: string | null | undefined,
): string {
  const parts: string[] = [];
  if (min) parts.push(t('pluginCompat.rangeAtLeast', { min }));
  if (max) parts.push(t('pluginCompat.rangeAtMost', { max }));
  return parts.length
    ? parts.join(t('pluginCompat.rangeSeparator'))
    : t('pluginCompat.rangeAny');
}

/** Compact marker for installed-plugin cards. Renders nothing when fine. */
export function PluginCompatibilityBadge({
  compatibility,
}: {
  compatibility?: PluginCompatibility | null;
}) {
  const { t } = useTranslation();
  if (!compatibility || !isPluginIncompatible(compatibility)) return null;
  const range = compatibilityRangeText(t, compatibility.min, compatibility.max);
  return (
    <Badge
      status="warning"
      className="gap-1"
      title={t('pluginCompat.declared', { range })}
      data-testid="plugin-compat-badge"
    >
      <TriangleAlert />
      {compatibility.status === 'invalid'
        ? t('pluginCompat.badgeInvalid')
        : t('pluginCompat.badge')}
    </Badge>
  );
}

/**
 * Warning for a package whose declared LangBot range excludes this Core.
 * `context="install"` adds the explicit acknowledgement checkbox required
 * before a non-marketplace install may send `allow_incompatible`.
 */
export function PluginCompatibilityWarning({
  compatibility,
  context,
  acknowledged,
  onAcknowledgedChange,
  className,
}: {
  compatibility?: PluginCompatibility | null;
  context: 'install' | 'installed';
  acknowledged?: boolean;
  onAcknowledgedChange?: (value: boolean) => void;
  className?: string;
}) {
  const { t } = useTranslation();
  const checkboxId = useId();
  if (!compatibility || !isPluginIncompatible(compatibility)) return null;

  const invalid = compatibility.status === 'invalid';
  const values = {
    range: compatibilityRangeText(t, compatibility.min, compatibility.max),
    current: compatibility.current,
  };
  const body =
    context === 'installed'
      ? invalid
        ? t('pluginCompat.installedInvalidBody', values)
        : t('pluginCompat.installedIncompatibleBody', values)
      : invalid
        ? t('pluginCompat.invalidBody', values)
        : t('pluginCompat.incompatibleBody', values);

  return (
    <Alert
      className={
        'border-amber-500/40 bg-amber-50 text-amber-900 dark:bg-amber-950/30 dark:text-amber-100 ' +
        (className ?? '')
      }
      data-testid="plugin-compat-warning"
    >
      <TriangleAlert className="text-amber-600 dark:text-amber-400" />
      <AlertTitle>
        {invalid
          ? t('pluginCompat.invalidTitle')
          : t('pluginCompat.incompatibleTitle')}
      </AlertTitle>
      <AlertDescription className="text-amber-800 dark:text-amber-200/90">
        <p>{body}</p>
        {context === 'install' && onAcknowledgedChange && (
          <label
            htmlFor={checkboxId}
            className="mt-2 flex cursor-pointer items-start gap-2 text-amber-900 dark:text-amber-100"
          >
            <Checkbox
              id={checkboxId}
              checked={!!acknowledged}
              onCheckedChange={(value) => onAcknowledgedChange(value === true)}
              className="mt-0.5 border-amber-600/60 bg-background"
              data-testid="plugin-compat-acknowledge"
            />
            <span>{t('pluginCompat.acknowledge')}</span>
          </label>
        )}
      </AlertDescription>
    </Alert>
  );
}
