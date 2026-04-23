import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Info } from 'lucide-react';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { httpClient } from '@/app/infra/http/HttpClient';
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';

export default function SkillDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshSkills, skills, setDetailEntityName } = useSidebarData();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('skills.createSkill'));
    } else {
      const skill = skills.find((item) => item.id === id);
      setDetailEntityName(skill?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, setDetailEntityName, skills, t]);

  function handleImportedSkills(skillNames: string[]) {
    void refreshSkills();
    const primarySkill = skillNames[0];
    if (primarySkill) {
      navigate(`/home/skills?id=${encodeURIComponent(primarySkill)}`);
      return;
    }
    navigate('/home/skills');
  }

  function handleSkillUpdated() {
    void refreshSkills();
  }

  async function confirmDelete() {
    try {
      await httpClient.deleteSkill(id);
      toast.success(t('skills.deleteSuccess'));
      setShowDeleteConfirm(false);
      void refreshSkills();
      navigate('/home/skills');
    } catch (error) {
      toast.error(t('skills.deleteError') + String(error));
    }
  }

  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">{t('skills.createSkill')}</h1>
          <Button type="submit" form="skill-form">
            {t('common.save')}
          </Button>
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

  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{t('skills.editSkill')}</h1>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t('skills.editSkillTooltip')}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <Button type="submit" form="skill-form">
            {t('common.save')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-3xl space-y-6 pb-8">
            <SkillForm
              key={id}
              initSkillName={id}
              onNewSkillCreated={(skillName) =>
                handleImportedSkills([skillName])
              }
              onSkillUpdated={handleSkillUpdated}
            />

            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">
                  {t('skills.dangerZone')}
                </CardTitle>
                <CardDescription>
                  {t('skills.dangerZoneDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <p className="text-sm font-medium">{t('common.delete')}</p>
                    <p className="text-sm text-muted-foreground">
                      {t('skills.deleteConfirmation')}
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                  >
                    {t('common.delete')}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
          </DialogHeader>
          <div className="py-4">{t('skills.deleteConfirmation')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
