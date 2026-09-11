import type { LangBotModelAvailabilityItem } from '@/app/infra/entities/api';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Coins } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ModelAvailabilityIndicator from './ModelAvailabilityIndicator';

interface LangBotModelMetadataProps {
  metadata?: LangBotModelAvailabilityItem;
  loaded: boolean;
  compact?: boolean;
}

function formatCredits(value: number, locale: string): string {
  if (value >= 1000) {
    const thousands = value / 1000;
    return `${thousands.toFixed(thousands >= 10 ? 0 : 1).replace(/\.0$/, '')}K`;
  }
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
  }).format(value);
}

export default function LangBotModelMetadata({
  metadata,
  loaded,
  compact = false,
}: LangBotModelMetadataProps) {
  const { t, i18n } = useTranslation();
  if (!loaded) return null;

  const inputCredits = metadata?.input_credits;
  const outputCredits = metadata?.output_credits;
  const hasPricing = inputCredits != null && outputCredits != null;
  const input =
    inputCredits != null ? formatCredits(inputCredits, i18n.language) : '';
  const output =
    outputCredits != null ? formatCredits(outputCredits, i18n.language) : '';

  return (
    <span className="ml-auto inline-flex shrink-0 items-center gap-2 pl-3">
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex items-center gap-1 text-xs tabular-nums text-muted-foreground"
            onMouseDown={(event) => event.preventDefault()}
          >
            <Coins className="size-3" />
            {hasPricing
              ? compact
                ? t('models.pricing.compact', { input, output })
                : t('models.pricing.inline', { input, output })
              : compact
                ? '—'
                : t('models.pricing.unavailable')}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-64">
          {hasPricing ? (
            <div className="space-y-0.5">
              <p>{t('models.pricing.title')}</p>
              <p className="text-xs text-muted-foreground">
                {t('models.pricing.input', {
                  credits: input,
                })}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('models.pricing.output', {
                  credits: output,
                })}
              </p>
            </div>
          ) : (
            <p>{t('models.pricing.unavailable')}</p>
          )}
        </TooltipContent>
      </Tooltip>
      <ModelAvailabilityIndicator
        availability={metadata?.availability}
        show={loaded}
      />
    </span>
  );
}
