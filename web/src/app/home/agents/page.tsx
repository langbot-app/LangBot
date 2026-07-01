import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import AgentDetailContent from './AgentDetailContent';

export default function AgentsPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <AgentDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('agents.selectFromSidebar')}</p>
    </div>
  );
}
