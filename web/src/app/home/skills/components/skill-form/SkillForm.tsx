'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
    description: '',
    instructions: '',
    type: 'skill',
    auto_activate: false,
    trigger_keywords: [],
    requires_tools: [],
    requires_kbs: [],
    requires_skills: [],
    is_enabled: true,
    author: '',
    version: '1.0.0',
    tags: [],
  });
  const [keywordsInput, setKeywordsInput] = useState('');
  const [tagsInput, setTagsInput] = useState('');

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
      setTagsInput(resp.skill.tags?.join(', ') || '');
    } catch (error) {
      console.error('Failed to load skill:', error);
      toast.error(t('skills.getSkillListError') + String(error));
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
    if (!skill.instructions?.trim()) {
      toast.error(t('skills.instructionsRequired'));
      return;
    }

    // Parse comma-separated inputs
    const parsedKeywords = keywordsInput
      .split(',')
      .map((k) => k.trim())
      .filter((k) => k);
    const parsedTags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t);

    const skillData = {
      ...skill,
      trigger_keywords: parsedKeywords,
      tags: parsedTags,
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
        <Label htmlFor="name">{t('skills.skillName')} *</Label>
        <Input
          id="name"
          value={skill.name || ''}
          onChange={(e) => setSkill({ ...skill, name: e.target.value })}
          placeholder={t('skills.skillName')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t('skills.skillDescription')} *</Label>
        <Textarea
          id="description"
          value={skill.description || ''}
          onChange={(e) => setSkill({ ...skill, description: e.target.value })}
          placeholder={t('skills.descriptionPlaceholder')}
          rows={2}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="type">{t('skills.skillType')}</Label>
        <Select
          value={skill.type || 'skill'}
          onValueChange={(value) =>
            setSkill({ ...skill, type: value as 'skill' | 'workflow' })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="skill">{t('skills.typeSkill')}</SelectItem>
            <SelectItem value="workflow">{t('skills.typeWorkflow')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="instructions">{t('skills.skillInstructions')} *</Label>
        <Textarea
          id="instructions"
          value={skill.instructions || ''}
          onChange={(e) => setSkill({ ...skill, instructions: e.target.value })}
          placeholder={t('skills.instructionsPlaceholder')}
          rows={10}
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

      <div className="flex items-center justify-between">
        <Label htmlFor="auto_activate">{t('skills.autoActivate')}</Label>
        <Switch
          id="auto_activate"
          checked={skill.auto_activate ?? false}
          onCheckedChange={(checked) =>
            setSkill({ ...skill, auto_activate: checked })
          }
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="trigger_keywords">{t('skills.triggerKeywords')}</Label>
        <Input
          id="trigger_keywords"
          value={keywordsInput}
          onChange={(e) => setKeywordsInput(e.target.value)}
          placeholder={t('skills.keywordsPlaceholder')}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="author">{t('skills.author')}</Label>
          <Input
            id="author"
            value={skill.author || ''}
            onChange={(e) => setSkill({ ...skill, author: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="version">{t('skills.version')}</Label>
          <Input
            id="version"
            value={skill.version || ''}
            onChange={(e) => setSkill({ ...skill, version: e.target.value })}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="tags">{t('skills.tags')}</Label>
        <Input
          id="tags"
          value={tagsInput}
          onChange={(e) => setTagsInput(e.target.value)}
          placeholder={t('skills.keywordsPlaceholder')}
        />
      </div>
    </form>
  );
}
