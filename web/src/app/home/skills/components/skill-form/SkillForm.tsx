import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { FolderSearch, ChevronDown, ChevronRight, File, Folder, FolderOpen, RefreshCw } from 'lucide-react';
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
  selectedFile?: string;
}

interface FileEntry {
  path: string;
  name: string;
  is_dir: boolean;
  size: number | null;
}

interface DirectoryContent {
  path: string;
  entries: FileEntry[];
  loading: boolean;
}

interface FileTreeProps {
  skillName: string;
  onFileSelect: (path: string, content: string) => void;
}

function FileTree({ skillName, onFileSelect }: FileTreeProps) {
  const { t } = useTranslation();
  const [rootEntries, setRootEntries] = useState<FileEntry[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [dirContents, setDirContents] = useState<Map<string, FileEntry[]>>(new Map());
  const [loading, setLoading] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const loadRootFiles = useCallback(async () => {
    setLoading(true);
    try {
      const result = await httpClient.listSkillFiles(skillName, '.');
      setRootEntries(result.entries);
    } catch (error) {
      console.error('Failed to load skill files:', error);
      toast.error(t('skills.loadFilesError') + String(error));
    } finally {
      setLoading(false);
    }
  }, [skillName, t]);

  const loadDirFiles = useCallback(async (dirPath: string) => {
    setDirContents(prev => {
      const newMap = new Map(prev);
      newMap.set(dirPath, []); // Clear while loading
      return newMap;
    });
    try {
      const result = await httpClient.listSkillFiles(skillName, dirPath);
      setDirContents(prev => {
        const newMap = new Map(prev);
        newMap.set(dirPath, result.entries);
        return newMap;
      });
    } catch (error) {
      console.error('Failed to load directory files:', error);
      toast.error(t('skills.loadFilesError') + String(error));
    }
  }, [skillName, t]);

  useEffect(() => {
    if (skillName) {
      loadRootFiles();
    }
  }, [skillName, loadRootFiles]);

  const toggleDir = async (dirPath: string) => {
    const newExpanded = new Set(expandedDirs);
    if (newExpanded.has(dirPath)) {
      newExpanded.delete(dirPath);
      setExpandedDirs(newExpanded);
    } else {
      newExpanded.add(dirPath);
      setExpandedDirs(newExpanded);
      loadDirFiles(dirPath);
    }
  };

  const handleFileClick = async (filePath: string) => {
    setSelectedPath(filePath);
    try {
      const result = await httpClient.readSkillFile(skillName, filePath);
      onFileSelect(filePath, result.content);
    } catch (error) {
      console.error('Failed to read file:', error);
      toast.error(t('skills.readFileError') + String(error));
    }
  };

  const renderEntry = (entry: FileEntry, depth: number = 0): React.ReactNode => {
    const isExpanded = expandedDirs.has(entry.path);
    const isSelected = selectedPath === entry.path;

    return (
      <div key={entry.path}>
        <div
          className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer hover:bg-muted ${
            isSelected ? 'bg-muted' : ''
          }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() => entry.is_dir ? toggleDir(entry.path) : handleFileClick(entry.path)}
        >
          {entry.is_dir ? (
            <>
              {isExpanded ? (
                <FolderOpen className="h-4 w-4 text-blue-500" />
              ) : (
                <Folder className="h-4 w-4 text-blue-500" />
              )}
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </>
          ) : (
            <File className="h-4 w-4 text-gray-500" />
          )}
          <span className="text-sm truncate">{entry.name}</span>
          {!entry.is_dir && entry.size !== null && (
            <span className="text-xs text-muted-foreground ml-auto">
              {entry.size > 1024 ? `${Math.round(entry.size / 1024)}KB` : `${entry.size}B`}
            </span>
          )}
        </div>
        {entry.is_dir && isExpanded && (
          <div>
            {(dirContents.get(entry.path) || []).map((child) => renderEntry(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="border rounded-md p-2">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium">{t('skills.files')}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => loadRootFiles()}
          disabled={loading}
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {rootEntries.length === 0 && !loading && (
          <div className="text-sm text-muted-foreground py-2">
            {t('skills.noFiles')}
          </div>
        )}
        {rootEntries.map((entry) => renderEntry(entry))}
      </div>
    </div>
  );
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
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');

  const loadSkill = useCallback(
    async (skillName: string) => {
      try {
        const resp = await httpClient.getSkill(skillName);
        setSkill(resp.skill);
        setFileContent(resp.skill.instructions || '');
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
    onDraftChange?.({ skill, showAdvanced, selectedFile: selectedFile || undefined });
  }, [initSkillName, onDraftChange, skill, showAdvanced, selectedFile]);

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
      setFileContent(result.instructions);
      toast.success(t('skills.scanSuccess'));
    } catch (error) {
      console.error('Failed to scan directory:', error);
      toast.error(t('skills.scanError') + String(error));
    } finally {
      setScanning(false);
    }
  }

  const handleFileSelect = (path: string, content: string) => {
    setSelectedFile(path);
    setFileContent(content);
    // If selecting SKILL.md, also sync to skill.instructions
    if (path === 'SKILL.md' || path.endsWith('/SKILL.md')) {
      setSkill((prev) => ({ ...prev, instructions: content }));
    }
  };

  const handleContentChange = (content: string) => {
    setFileContent(content);
    // If editing SKILL.md, sync to skill.instructions
    if (selectedFile === 'SKILL.md' || selectedFile?.endsWith('/SKILL.md')) {
      setSkill((prev) => ({ ...prev, instructions: content }));
    }
  };

  const handleSaveFile = async () => {
    if (!initSkillName || !selectedFile) return;

    try {
      await httpClient.writeSkillFile(initSkillName, selectedFile, fileContent);
      toast.success(t('skills.saveFileSuccess'));
    } catch (error) {
      console.error('Failed to save file:', error);
      toast.error(t('skills.saveFileError') + String(error));
    }
  };

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

      {/* File tree for existing skills */}
      {initSkillName && (
        <div className="space-y-2">
          <FileTree skillName={initSkillName} onFileSelect={handleFileSelect} />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="instructions">
          {selectedFile ? `${t('skills.skillInstructions')} (${selectedFile})` : t('skills.skillInstructions')}
        </Label>
        <Textarea
          id="instructions"
          value={fileContent}
          onChange={(e) => handleContentChange(e.target.value)}
          placeholder={t('skills.instructionsPlaceholder')}
          rows={16}
          className="font-mono text-sm"
        />
        {selectedFile && selectedFile !== 'SKILL.md' && !selectedFile.endsWith('/SKILL.md') && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleSaveFile}
          >
            {t('skills.saveFile')}
          </Button>
        )}
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