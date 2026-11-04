import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import BotDetailContent from './BotDetailContent';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <BotDetailContent key={detailId} id={detailId} />;
  }

  return (
    <div className="space-y-4 p-4">
      <p>{t('bots.selectFromSidebar')}</p>
    </div>
  );
}
