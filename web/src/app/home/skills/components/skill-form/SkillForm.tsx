import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { FolderSearch, ChevronDown, ChevronRight } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill } from '@/app/infra/entities/api';
import { toast } from 'sonner';

interface SkillFormProps {
  initSkillName?: string;
  initialDraft?: SkillFormDraft;
  onNewSkillCreated: (skillName: string) => void;
  onSkillUpdated: (skillName: string) => void;
  onDraftChange?: (draft: SkillFormDraft) => void;
}

export interface SkillFormDraft {
  skill: Partial<Skill>;
  showAdvanced: boolean;
}

const emptySkillDraft: SkillFormDraft = {
  skill: {
    name: '',
    display_name: '',
    description: '',
    instructions: '',
    package_root: '',
  },
  showAdvanced: false,
};

export default function SkillForm({
  initSkillName,
  initialDraft,
  onNewSkillCreated,
  onSkillUpdated,
  onDraftChange,
}: SkillFormProps) {
  const { t } = useTranslation();
  const initialDraftRef = useRef(initialDraft ?? emptySkillDraft);
  const [skill, setSkill] = useState<Partial<Skill>>(
    initialDraftRef.current.skill,
  );
  const [scanning, setScanning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(
    initialDraftRef.current.showAdvanced,
  );

  const loadSkill = useCallback(
    async (skillName: string) => {
      try {
        const resp = await httpClient.getSkill(skillName);
        setSkill(resp.skill);
      } catch (error) {
        console.error('Failed to load skill:', error);
        toast.error(t('skills.getSkillListError') + String(error));
      }
    },
    [t],
  );

  useEffect(() => {
    if (initSkillName) {
      loadSkill(initSkillName);
      return;
    }
    setSkill(initialDraftRef.current.skill);
    setShowAdvanced(initialDraftRef.current.showAdvanced);
  }, [initSkillName, loadSkill]);

  useEffect(() => {
    if (initSkillName) return;
    onDraftChange?.({ skill, showAdvanced });
  }, [initSkillName, onDraftChange, skill, showAdvanced]);

  async function scanDirectory() {
    const path = skill.package_root?.trim();
    if (!path) {
      toast.error(t('skills.packageRootRequired'));
      return;
    }
    setScanning(true);
    try {
      const result = await httpClient.scanSkillDirectory(path);
      setSkill((prev) => ({
        ...prev,
        name: prev.name || result.name,
        display_name: prev.display_name || result.display_name || '',
        description: prev.description || result.description,
        package_root: result.package_root,
        instructions: result.instructions,
      }));
      toast.success(t('skills.scanSuccess'));
    } catch (error) {
      console.error('Failed to scan directory:', error);
      toast.error(t('skills.scanError') + String(error));
    } finally {
      setScanning(false);
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!skill.name?.trim()) {
      toast.error(t('skills.skillNameRequired'));
      return;
    }
    if (!skill.description?.trim()) {
      toast.error(t('skills.skillDescriptionRequired'));
      return;
    }

    const baseSkillData = {
      name: skill.name,
      display_name: skill.display_name || '',
      description: skill.description || '',
      instructions: skill.instructions || '',
    };

    try {
      if (initSkillName) {
        const resp = await httpClient.updateSkill(initSkillName, baseSkillData);
        toast.success(t('skills.saveSuccess'));
        onSkillUpdated(resp.skill.name);
      } else {
        const skillData: Omit<Skill, 'name'> & { name: string } = {
          ...baseSkillData,
          package_root: skill.package_root || '',
        };
        const resp = await httpClient.createSkill(skillData);
        toast.success(t('skills.createSuccess'));
        onNewSkillCreated(resp.skill.name);
      }
    } catch (error) {
      toast.error(
        (initSkillName ? t('skills.saveError') : t('skills.createError')) +
          String(error),
      );
    }
  };

  return (
    <form id="skill-form" onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="display_name">{t('skills.displayName')}</Label>
        <Input
          id="display_name"
          value={skill.display_name || ''}
          onChange={(e) => setSkill({ ...skill, display_name: e.target.value })}
          placeholder={t('skills.displayNamePlaceholder')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="name">{t('skills.skillSlug')} *</Label>
        <Input
          id="name"
          value={skill.name || ''}
          onChange={(e) =>
            setSkill({
              ...skill,
              name: e.target.value.replace(/[^a-zA-Z0-9_-]/g, ''),
            })
          }
          placeholder={t('skills.skillSlugPlaceholder')}
          className="font-mono"
          disabled={Boolean(initSkillName)}
        />
        <p className="text-xs text-muted-foreground">
          {t('skills.skillSlugHelp')}
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t('skills.skillDescription')} *</Label>
        <Textarea
          id="description"
          value={skill.description || ''}
          onChange={(e) => setSkill({ ...skill, description: e.target.value })}
          placeholder={t('skills.descriptionPlaceholder')}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="instructions">{t('skills.skillInstructions')}</Label>
        <Textarea
          id="instructions"
          value={skill.instructions || ''}
          onChange={(e) => setSkill({ ...skill, instructions: e.target.value })}
          placeholder={t('skills.instructionsPlaceholder')}
          rows={16}
          className="font-mono text-sm"
        />
      </div>

      <div className="space-y-3">
        <button
          type="button"
          className="flex w-full items-center justify-between rounded-md bg-muted/40 px-3 py-2 text-left text-sm font-medium hover:bg-muted/70"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {t('skills.advancedSettings')}
          {showAdvanced ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>
        {showAdvanced && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{t('skills.packageRoot')}</Label>
              <div className="flex gap-2">
                <Input
                  value={skill.package_root || ''}
                  onChange={(e) =>
                    setSkill({ ...skill, package_root: e.target.value })
                  }
                  placeholder={`data/skills/${skill.name || '<skill-name>'}/`}
                  className="flex-1"
                  disabled={Boolean(initSkillName)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={scanDirectory}
                  disabled={
                    Boolean(initSkillName) ||
                    scanning ||
                    !skill.package_root?.trim()
                  }
                  className="shrink-0"
                >
                  <FolderSearch className="h-4 w-4 mr-1" />
                  {scanning ? t('common.loading') : t('skills.scan')}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {t('skills.packageRootHelp')}
              </p>
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
