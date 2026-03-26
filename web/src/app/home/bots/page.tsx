'use client';

import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import BotDetailContent from './BotDetailContent';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <BotDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('bots.selectFromSidebar')}</p>
    </div>
  );
}
