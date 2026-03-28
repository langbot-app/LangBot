'use client';

import { useSearchParams } from 'next/navigation';
import { useTranslation } from 'react-i18next';
import SkillDetailContent from '@/app/home/skills/SkillDetailContent';

export default function SkillsPage() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <SkillDetailContent id={detailId} />;
  }

  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('skills.selectFromSidebar')}</p>
    </div>
  );
}
