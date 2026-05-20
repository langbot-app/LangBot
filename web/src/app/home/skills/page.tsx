import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import SkillDetailContent from '@/app/home/skills/SkillDetailContent';
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { BoxUnavailableNotice } from '@/app/home/components/BoxUnavailableNotice';
import { useBoxStatus } from '@/app/infra/hooks/useBoxStatus';

export default function SkillsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const actionParam = searchParams.get('action');
  const { refreshSkills } = useSidebarData();

  const isCreateView = actionParam === 'create';
  const { available: boxAvailable, hint: boxHint } = useBoxStatus();

  useEffect(() => {
    if (!detailId && !isCreateView) {
      navigate('/home/add-extension', { replace: true });
    }
  }, [detailId, isCreateView, navigate]);

  if (detailId) {
    return <SkillDetailContent id={detailId} />;
  }

  function handleCreatedSkill(skillName: string) {
    void refreshSkills();
    navigate(`/home/skills?id=${encodeURIComponent(skillName)}`, {
      replace: true,
    });
  }

  function handleCancel() {
    navigate('/home/add-extension');
  }

  if (!isCreateView) {
    return null;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between pb-4 shrink-0">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-xl font-semibold">{t('skills.createSkill')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('skills.createSkillDescription')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form="skill-form" disabled={!boxAvailable}>
            {t('common.save')}
          </Button>
        </div>
      </div>
      {!boxAvailable && (
        <div className="pb-4 shrink-0">
          <BoxUnavailableNotice hint={boxHint} />
        </div>
      )}
      <div className="min-h-0 flex-1">
        <SkillForm
          key="new-skill"
          initSkillName={undefined}
          layout="split"
          onNewSkillCreated={handleCreatedSkill}
          onSkillUpdated={() => {}}
        />
      </div>
    </div>
  );
}
