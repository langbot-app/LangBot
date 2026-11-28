import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import BotDetailContent from './BotDetailContent';
import UpgradeChecksBanner from '@/app/home/components/upgrade-checks/UpgradeChecks';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <BotDetailContent key={detailId} id={detailId} />;
  }

  return (
    <div className="flex h-full flex-col">
      <UpgradeChecksBanner />
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>{t('bots.selectFromSidebar')}</p>
      </div>
    </div>
  );
}
