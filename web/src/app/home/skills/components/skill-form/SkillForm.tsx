'use client';

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Plus, Trash2 } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill, SkillToolDef } from '@/app/infra/entities/api';
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
    source_type: 'inline',
    package_root: '',
    entry_file: 'SKILL.md',
    skill_tools: [],
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

  const isPackage = skill.source_type === 'package';

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
    if (!isPackage && !skill.instructions?.trim()) {
      toast.error(t('skills.instructionsRequired'));
      return;
    }
    if (isPackage && !skill.package_root?.trim()) {
      toast.error(t('skills.packageRootRequired'));
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

  const addSkillTool = () => {
    const tools = [...(skill.skill_tools || [])];
    tools.push({
      name: '',
      description: '',
      entry: '',
      parameters: {},
      timeout_sec: 30,
      network: false,
    });
    setSkill({ ...skill, skill_tools: tools });
  };

  const removeSkillTool = (index: number) => {
    const tools = [...(skill.skill_tools || [])];
    tools.splice(index, 1);
    setSkill({ ...skill, skill_tools: tools });
  };

  const updateSkillTool = (index: number, field: keyof SkillToolDef, value: unknown) => {
    const tools = [...(skill.skill_tools || [])];
    tools[index] = { ...tools[index], [field]: value };
    setSkill({ ...skill, skill_tools: tools });
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
        <Label htmlFor="source_type">{t('skills.sourceType')}</Label>
        <Select
          value={skill.source_type || 'inline'}
          onValueChange={(value) =>
            setSkill({ ...skill, source_type: value as 'inline' | 'package' })
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="inline">{t('skills.sourceInline')}</SelectItem>
            <SelectItem value="package">{t('skills.sourcePackage')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isPackage ? (
        <>
          <div className="space-y-2">
            <Label htmlFor="package_root">{t('skills.packageRoot')} *</Label>
            <Input
              id="package_root"
              value={skill.package_root || ''}
              onChange={(e) => setSkill({ ...skill, package_root: e.target.value })}
              placeholder="/path/to/skill/package"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="entry_file">{t('skills.entryFile')}</Label>
            <Input
              id="entry_file"
              value={skill.entry_file || 'SKILL.md'}
              onChange={(e) => setSkill({ ...skill, entry_file: e.target.value })}
              placeholder="SKILL.md"
            />
          </div>
        </>
      ) : (
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
      )}

      {/* Skill Tools */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('skills.skillTools')}</Label>
          <Button type="button" variant="outline" size="sm" onClick={addSkillTool}>
            <Plus className="h-4 w-4 mr-1" />
            {t('common.add')}
          </Button>
        </div>
        {(skill.skill_tools || []).map((tool, index) => (
          <div key={index} className="border rounded-md p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Tool #{index + 1}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeSkillTool(index)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                value={tool.name}
                onChange={(e) => updateSkillTool(index, 'name', e.target.value)}
                placeholder={t('skills.toolName')}
              />
              <Input
                value={tool.entry}
                onChange={(e) => updateSkillTool(index, 'entry', e.target.value)}
                placeholder={t('skills.toolEntry')}
              />
            </div>
            <Input
              value={tool.description}
              onChange={(e) => updateSkillTool(index, 'description', e.target.value)}
              placeholder={t('skills.toolDescription')}
            />
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Label className="text-xs">{t('skills.toolTimeout')}</Label>
                <Input
                  type="number"
                  className="w-20"
                  value={tool.timeout_sec ?? 30}
                  onChange={(e) => updateSkillTool(index, 'timeout_sec', parseInt(e.target.value) || 30)}
                />
              </div>
              <div className="flex items-center gap-2">
                <Label className="text-xs">{t('skills.toolNetwork')}</Label>
                <Switch
                  checked={tool.network ?? false}
                  onCheckedChange={(checked) => updateSkillTool(index, 'network', checked)}
                />
              </div>
            </div>
          </div>
        ))}
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
