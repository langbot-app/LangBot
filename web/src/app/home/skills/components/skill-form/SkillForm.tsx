'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { FolderSearch, ChevronDown, ChevronRight } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill } from '@/app/infra/entities/api';
import { toast } from 'sonner';

interface SkillFormProps {
  initSkillId?: string;
  onNewSkillCreated: (skillId: string) => void;
  onSkillUpdated: (skillId: string) => void;
}

export default function SkillForm({
  initSkillId,
  onNewSkillCreated,
  onSkillUpdated,
}: SkillFormProps) {
  const { t } = useTranslation();
  const [skill, setSkill] = useState<Partial<Skill>>({
    name: '',
    display_name: '',
    description: '',
    instructions: '',
    type: 'skill',
    package_root: '',
    entry_file: 'SKILL.md',
    sandbox_timeout_sec: 120,
    sandbox_network: false,
    auto_activate: true,
    trigger_keywords: [],
    is_enabled: true,
  });
  const [keywordsInput, setKeywordsInput] = useState('');
  const [scanning, setScanning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (initSkillId) {
      loadSkill(initSkillId);
    }
  }, [initSkillId]);

  async function loadSkill(skillId: string) {
    try {
      const resp = await httpClient.getSkill(skillId);
      setSkill(resp.skill);
      setKeywordsInput(resp.skill.trigger_keywords?.join(', ') || '');
    } catch (error) {
      console.error('Failed to load skill:', error);
      toast.error(t('skills.getSkillListError') + String(error));
    }
  }

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
        description: prev.description || result.description,
        package_root: result.package_root,
        entry_file: result.entry_file,
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

    const parsedKeywords = keywordsInput
      .split(',')
      .map((k) => k.trim())
      .filter((k) => k);

    const skillData = {
      ...skill,
      trigger_keywords: parsedKeywords,
    };

    try {
      if (initSkillId) {
        await httpClient.updateSkill(initSkillId, skillData);
        toast.success(t('skills.saveSuccess'));
        onSkillUpdated(initSkillId);
      } else {
        const resp = await httpClient.createSkill(skillData as Omit<Skill, 'uuid'>);
        toast.success(t('skills.createSuccess'));
        onNewSkillCreated(resp.uuid);
      }
    } catch (error) {
      toast.error(
        (initSkillId ? t('skills.saveError') : t('skills.createError')) +
          String(error),
      );
    }
  };

  return (
    <form id="skill-form" onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="display_name">{t('skills.displayName')} *</Label>
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
          onChange={(e) => setSkill({ ...skill, name: e.target.value.replace(/[^a-zA-Z0-9_-]/g, '') })}
          placeholder={t('skills.skillSlugPlaceholder')}
          className="font-mono"
        />
        <p className="text-xs text-muted-foreground">{t('skills.skillSlugHelp')}</p>
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
        <Label htmlFor="type">{t('skills.skillType')}</Label>
        <div className="flex gap-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="type"
              value="skill"
              checked={skill.type === 'skill'}
              onChange={() => setSkill({ ...skill, type: 'skill', auto_activate: true })}
              className="accent-primary"
            />
            <span className="text-sm">{t('skills.typeSkill')}</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="type"
              value="workflow"
              checked={skill.type === 'workflow'}
              onChange={() => setSkill({ ...skill, type: 'workflow', auto_activate: false })}
              className="accent-primary"
            />
            <span className="text-sm">{t('skills.typeWorkflow')}</span>
          </label>
        </div>
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

      <div className="flex items-center justify-between">
        <Label htmlFor="is_enabled">{t('common.enable')}</Label>
        <Switch
          id="is_enabled"
          checked={skill.is_enabled ?? true}
          onCheckedChange={(checked) =>
            setSkill({ ...skill, is_enabled: checked })
          }
        />
      </div>

      {skill.type !== 'workflow' && (
        <div className="flex items-center justify-between">
          <Label htmlFor="auto_activate">{t('skills.autoActivate')}</Label>
          <Switch
            id="auto_activate"
            checked={skill.auto_activate ?? true}
            onCheckedChange={(checked) =>
              setSkill({ ...skill, auto_activate: checked })
            }
          />
        </div>
      )}

      {/* Advanced Settings */}
      <div className="border rounded-md">
        <button
          type="button"
          className="flex items-center justify-between w-full p-3 text-sm font-medium text-left"
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
          <div className="p-3 pt-0 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="trigger_keywords">{t('skills.triggerKeywords')}</Label>
              <Input
                id="trigger_keywords"
                value={keywordsInput}
                onChange={(e) => setKeywordsInput(e.target.value)}
                placeholder={t('skills.keywordsPlaceholder')}
              />
              <p className="text-xs text-muted-foreground">{t('skills.keywordsHelp')}</p>
            </div>

            <div className="space-y-2">
              <Label>{t('skills.packageRoot')}</Label>
              <div className="flex gap-2">
                <Input
                  value={skill.package_root || ''}
                  onChange={(e) => setSkill({ ...skill, package_root: e.target.value })}
                  placeholder={`data/skills/${skill.name || '<skill-name>'}/`}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={scanDirectory}
                  disabled={scanning || !skill.package_root?.trim()}
                  className="shrink-0"
                >
                  <FolderSearch className="h-4 w-4 mr-1" />
                  {scanning ? t('common.loading') : t('skills.scan')}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">{t('skills.packageRootHelp')}</p>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 flex-1">
                <Label className="text-xs whitespace-nowrap">{t('skills.sandboxTimeout')}</Label>
                <Input
                  type="number"
                  className="w-24"
                  value={skill.sandbox_timeout_sec ?? 120}
                  onChange={(e) =>
                    setSkill({ ...skill, sandbox_timeout_sec: parseInt(e.target.value) || 120 })
                  }
                />
                <span className="text-xs text-muted-foreground">s</span>
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-xs whitespace-nowrap">{t('skills.sandboxNetwork')}</Label>
                <Switch
                  checked={skill.sandbox_network ?? false}
                  onCheckedChange={(checked) =>
                    setSkill({ ...skill, sandbox_network: checked })
                  }
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </form>
  );
}
