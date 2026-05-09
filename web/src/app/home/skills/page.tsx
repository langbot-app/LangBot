import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import SkillDetailContent from '@/app/home/skills/SkillDetailContent';
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';
import SkillGithubImportPanel from '@/app/home/skills/components/SkillGithubImportPanel';
import {
  useSidebarData,
  type SkillInstallAction,
} from '@/app/home/components/home-sidebar/SidebarDataContext';

export default function SkillsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');
  const actionParam = searchParams.get('action') as SkillInstallAction | null;
  const {
    refreshSkills,
    pendingSkillInstallAction,
    setPendingSkillInstallAction,
  } = useSidebarData();

  const [activeView, setActiveView] = useState<SkillInstallAction>(null);

  useEffect(() => {
    if (actionParam && ['create', 'github', 'upload'].includes(actionParam)) {
      setActiveView(actionParam);
      return;
    }
    if (!pendingSkillInstallAction) return;
    const action = pendingSkillInstallAction;
    setPendingSkillInstallAction(null);
    setActiveView(action);
  }, [actionParam, pendingSkillInstallAction, setPendingSkillInstallAction]);

  if (detailId) {
    return <SkillDetailContent id={detailId} />;
  }

  function handleImportedSkills(skillNames: string[]) {
    void refreshSkills();
    setActiveView(null);
    navigate('/home/add-extension');
  }

  function handleCancel() {
    setActiveView(null);
    navigate('/home/add-extension');
  }

  if (activeView === 'create') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('skills.createSkill')}</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleCancel}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" form="skill-form">
              {t('common.save')}
            </Button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <SkillForm
              key="new-skill"
              initSkillName={undefined}
              onNewSkillCreated={(skillName) =>
                handleImportedSkills([skillName])
              }
              onSkillUpdated={() => {}}
            />
          </div>
        </div>
      </div>
    );
  }

  if (activeView === 'github') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('skills.importFromGithub')}
          </h1>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <SkillGithubImportPanel
              mode="github"
              onImported={handleImportedSkills}
            />
          </div>
        </div>
      </div>
    );
  }

  if (activeView === 'upload') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('skills.uploadZip')}</h1>
          <Button variant="outline" onClick={handleCancel}>
            {t('common.cancel')}
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <SkillGithubImportPanel
              mode="upload"
              onImported={handleImportedSkills}
            />
          </div>
        </div>
      </div>
    );
  }

  navigate('/home/add-extension');
  return null;
}