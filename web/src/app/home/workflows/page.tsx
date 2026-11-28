import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import WorkflowDetailContent from './WorkflowDetailContent';

export default function WorkflowPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <WorkflowDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('workflows.selectFromSidebar')}</p>
    </div>
  );
}
