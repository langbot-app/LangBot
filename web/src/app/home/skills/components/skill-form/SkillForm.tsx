import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { FolderSearch, ChevronDown, ChevronRight } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import rehypeHighlight from 'rehype-highlight';
import '@/styles/github-markdown.css';

interface SkillFormProps {
  initSkillName?: string;
  onNewSkillCreated: (skillName: string) => void;
  onSkillUpdated: (skillName: string) => void;
}

export default function SkillForm({
  initSkillName,
  onNewSkillCreated,
  onSkillUpdated,
}: SkillFormProps) {
  const { t } = useTranslation();
  const [skill, setSkill] = useState<Partial<Skill>>({
    name: '',
    display_name: '',
    description: '',
    instructions: '',
    package_root: '',
  });
  const [scanning, setScanning] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);

  useEffect(() => {
    if (initSkillName) {
      loadSkill(initSkillName);
      return;
    }
    setSkill({
      name: '',
      display_name: '',
      description: '',
      instructions: '',
      package_root: '',
    });
    setShowAdvanced(false);
    setPreviewMode(false);
  }, [initSkillName]);

  async function loadSkill(skillName: string) {
    try {
      const resp = await httpClient.getSkill(skillName);
      setSkill(resp.skill);
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
        <div className="flex items-center justify-between">
          <Label htmlFor="instructions">{t('skills.skillInstructions')}</Label>
          <div className="flex gap-1 text-xs">
            <button
              type="button"
              className={`px-2 py-0.5 rounded ${
                !previewMode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setPreviewMode(false)}
            >
              {t('skills.edit')}
            </button>
            <button
              type="button"
              className={`px-2 py-0.5 rounded ${
                previewMode
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => setPreviewMode(true)}
            >
              {t('skills.preview')}
            </button>
          </div>
        </div>
        {previewMode ? (
          <div className="markdown-body h-[720px] min-h-60 max-h-[1000px] overflow-y-auto resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm">
            {skill.instructions?.trim() ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw, rehypeSanitize, rehypeHighlight]}
                components={{
                  ul: ({ children }) => (
                    <ul className="list-disc">{children}</ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal">{children}</ol>
                  ),
                  li: ({ children }) => <li className="ml-4">{children}</li>,
                }}
              >
                {skill.instructions}
              </ReactMarkdown>
            ) : (
              <p className="text-muted-foreground italic">
                {t('skills.instructionsPlaceholder')}
              </p>
            )}
          </div>
        ) : (
          <Textarea
            id="instructions"
            value={skill.instructions || ''}
            onChange={(e) =>
              setSkill({ ...skill, instructions: e.target.value })
            }
            placeholder={t('skills.instructionsPlaceholder')}
            className="font-mono text-sm h-[720px] min-h-60 max-h-[1000px] overflow-y-auto resize-y"
          />
        )}
      </div>

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
