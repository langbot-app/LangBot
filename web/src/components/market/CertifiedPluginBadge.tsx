'use client';

import { BadgeCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export function CertifiedPluginBadge({
  compact = false,
}: {
  compact?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language.startsWith('zh')
    ? 'zh'
    : i18n.language.startsWith('ja')
      ? 'ja'
      : 'en';
  const docsURL = `https://langbot.app/docs/${language}/plugin/certified-plugins`;
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <a
            href={docsURL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${t('market.certifiedPlugin')}: ${t('market.certificationLearnMore')}`}
            onClick={(event) => event.stopPropagation()}
            className={`inline-flex shrink-0 items-center gap-1 rounded border border-emerald-600/25 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 ${compact ? 'h-4 px-0.5' : 'px-2 py-0.5 text-xs font-medium'}`}
          >
            <BadgeCheck
              aria-hidden="true"
              className={compact ? 'h-3 w-3' : 'h-3.5 w-3.5'}
            />
            {!compact && t('market.certifiedPlugin')}
          </a>
        </TooltipTrigger>
        <TooltipContent className="max-w-72 text-xs">
          <p>{t('market.certificationTooltip')}</p>
          <a
            href={docsURL}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-block underline underline-offset-2"
            onClick={(event) => event.stopPropagation()}
          >
            {t('market.certificationLearnMore')}
          </a>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
