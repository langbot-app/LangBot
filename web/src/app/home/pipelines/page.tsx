'use client';

import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import PipelineDetailContent from './PipelineDetailContent';

export default function PipelineConfigPage() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <PipelineDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('pipelines.selectFromSidebar')}</p>
    </div>
  );
}
