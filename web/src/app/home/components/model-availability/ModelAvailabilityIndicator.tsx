import type { LangBotModelAvailability } from '@/app/infra/entities/api';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useTranslation } from 'react-i18next';

interface ModelAvailabilityIndicatorProps {
  availability?: LangBotModelAvailability;
  show: boolean;
}

export default function ModelAvailabilityIndicator({
  availability,
  show,
}: ModelAvailabilityIndicatorProps) {
  const { t, i18n } = useTranslation();
  if (!show) return null;

  const state = availability?.up;
  const label =
    state === true
      ? t('models.availability.available')
      : state === false
        ? t('models.availability.unavailable')
        : t('models.availability.notChecked');
  const dotClass =
    state === true
      ? 'bg-emerald-500'
      : state === false
        ? 'bg-destructive'
        : 'bg-muted-foreground/50';
  const checkedAt = availability?.last_probed_at
    ? new Intl.DateTimeFormat(i18n.language, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(availability.last_probed_at))
    : null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className="inline-flex size-4 shrink-0 items-center justify-center"
          aria-label={label}
          onMouseDown={(event) => event.preventDefault()}
        >
          <span className={`size-1.5 rounded-full ${dotClass}`} />
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-64">
        <div className="space-y-0.5">
          <p>{label}</p>
          {checkedAt && (
            <p className="text-xs text-muted-foreground">
              {t('models.availability.lastChecked', { time: checkedAt })}
              {availability && availability.latency_ms > 0
                ? ` · ${availability.latency_ms} ms`
                : ''}
            </p>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
