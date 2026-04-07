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
  const {
    refreshSkills,
    pendingSkillInstallAction,
    setPendingSkillInstallAction,
  } = useSidebarData();

  // Local active view: consumed from context on mount/change
  const [activeView, setActiveView] = useState<SkillInstallAction>(null);

  // Consume pending action from sidebar context
  useEffect(() => {
    if (!pendingSkillInstallAction) return;
    const action = pendingSkillInstallAction;
    setPendingSkillInstallAction(null);
    setActiveView(action);
  }, [pendingSkillInstallAction, setPendingSkillInstallAction]);

  // If a detail id is present, show detail content (edit existing / old create mode)
  if (detailId) {
    return <SkillDetailContent id={detailId} />;
  }

  // Handle callback after skills are imported/created
  function handleImportedSkills(skillNames: string[]) {
    void refreshSkills();
    setActiveView(null);
    const primarySkill = skillNames[0];
    if (primarySkill) {
      navigate(`/home/skills?id=${encodeURIComponent(primarySkill)}`);
      return;
    }
    navigate('/home/skills');
  }

  // Inline create manually view
  if (activeView === 'create') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('skills.createSkill')}</h1>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setActiveView(null)}>
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

  // Inline GitHub import view
  if (activeView === 'github') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('skills.importFromGithub')}
          </h1>
          <Button variant="outline" onClick={() => setActiveView(null)}>
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

  // Inline upload ZIP view
  if (activeView === 'upload') {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('skills.uploadZip')}</h1>
          <Button variant="outline" onClick={() => setActiveView(null)}>
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

  // Default: no selection
  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      <p>{t('skills.selectFromSidebar')}</p>
    </div>
  );
}
