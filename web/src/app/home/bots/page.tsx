import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import BotDetailContent from './BotDetailContent';
import ScenarioPacks from './ScenarioPacks';

export default function BotConfigPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return (
      <div className="flex h-full flex-col overflow-y-auto">
        <ScenarioPacks
          key={detailId}
          botId={detailId === 'new' ? undefined : detailId}
        />
        <BotDetailContent key={detailId} id={detailId} />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <ScenarioPacks />
      <p>{t('bots.selectFromSidebar')}</p>
    </div>
  );
}
