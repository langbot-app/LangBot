import { useTranslation } from 'react-i18next';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

export default function LegacyAdapterHelp() {
  const { t } = useTranslation();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" aria-label={t('bots.legacyAdapters')} className="inline-flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6" /><circle cx="12" cy="7.5" r=".7" fill="currentColor" /></svg>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 max-w-[calc(100vw-2rem)]">
        <h4 className="mb-2 text-sm font-medium">{t('bots.legacyAdapters')}</h4>
        <p className="whitespace-pre-line text-sm leading-6 text-muted-foreground">{t('bots.legacyAdaptersHint')}</p>
      </PopoverContent>
    </Popover>
  );
}
