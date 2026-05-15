import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { httpClient } from '@/app/infra/http/HttpClient';
import SkillForm from '@/app/home/skills/components/skill-form/SkillForm';
import { Sparkles, Trash2 } from 'lucide-react';

export default function SkillDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshSkills, skills, setDetailEntityName } = useSidebarData();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const skill = skills.find((item) => item.id === id);

  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('skills.createSkill'));
    } else {
      setDetailEntityName(skill?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, setDetailEntityName, skill, t]);

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
        <div className="flex shrink-0 flex-col gap-3 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 items-center gap-3">
              <h1 className="truncate text-xl font-semibold">
                {t('skills.createSkill')}
              </h1>
              <Badge variant="outline" className="shrink-0 text-[0.7rem]">
                <Sparkles className="size-3.5" />
                {t('skills.title')}
              </Badge>
            </div>
          </div>
          <Button type="submit" form="skill-form" className="shrink-0">
            {t('common.save')}
          </Button>
        </div>

        <div className="min-h-0 flex-1">
          <SkillForm
            key="new-skill"
            initSkillName={undefined}
            layout="split"
            onNewSkillCreated={(skillName) => handleImportedSkills([skillName])}
            onSkillUpdated={() => {}}
          />
        </div>
      </div>
    );
  }

  const editActions = (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="text-destructive">
          {t('skills.dangerZone')}
        </CardTitle>
        <CardDescription>{t('skills.dangerZoneDescription')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium">{t('skills.delete')}</p>
            <p className="text-sm text-muted-foreground">
              {t('skills.deleteConfirmation')}
            </p>
          </div>
          <Button
            variant="destructive"
            type="button"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0"
          >
            <Trash2 className="mr-1.5 size-4" />
            {t('common.delete')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 flex-col gap-3 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex min-w-0 items-center gap-3">
              <h1 className="truncate text-xl font-semibold">
                {skill?.name ?? id}
              </h1>
              <Badge variant="outline" className="shrink-0 text-[0.7rem]">
                <Sparkles className="size-3.5" />
                {t('skills.title')}
              </Badge>
            </div>
            {skill?.description && (
              <p className="line-clamp-2 text-sm text-muted-foreground">
                {skill.description}
              </p>
            )}
          </div>
          <Button type="submit" form="skill-form" className="shrink-0">
            {t('common.save')}
          </Button>
        </div>

        <div className="min-h-0 flex-1">
          <SkillForm
            key={id}
            initSkillName={id}
            layout="split"
            sideFooter={editActions}
            onNewSkillCreated={(skillName) => handleImportedSkills([skillName])}
            onSkillUpdated={handleSkillUpdated}
          />
        </div>
      </div>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-h-[min(420px,80vh)] overflow-y-auto">
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
