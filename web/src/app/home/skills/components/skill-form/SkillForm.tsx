import {
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  FolderSearch,
  ChevronDown,
  ChevronRight,
  File,
  Folder,
  FolderOpen,
  RefreshCw,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Skill } from '@/app/infra/entities/api';
import { toast } from 'sonner';

interface SkillFormProps {
  initSkillName?: string;
  initialDraft?: SkillFormDraft;
  onNewSkillCreated: (skillName: string) => void;
  onSkillUpdated: (skillName: string) => void;
  onDraftChange?: (draft: SkillFormDraft) => void;
  layout?: 'stacked' | 'split';
  sideFooter?: ReactNode;
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

interface FileTreeProps {
  skillName: string;
  selectedFile?: string | null;
  onFileSelect: (path: string, content: string) => void;
  onLoadingChange?: (loading: boolean) => void;
}

export interface FileTreeHandle {
  refresh: () => void;
  loading: boolean;
}

function getFileName(path: string) {
  return path.split('/').pop() || path;
}

const FileTree = forwardRef<FileTreeHandle, FileTreeProps>(function FileTree(
  { skillName, selectedFile, onFileSelect, onLoadingChange },
  ref,
) {
  const { t } = useTranslation();
  const [rootEntries, setRootEntries] = useState<FileEntry[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [dirContents, setDirContents] = useState<Map<string, FileEntry[]>>(
    new Map(),
  );
  const [loading, setLoading] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    setSelectedPath(selectedFile ?? null);
  }, [selectedFile]);

  const loadRootFiles = useCallback(async () => {
    setLoading(true);
    onLoadingChange?.(true);
    try {
      const result = await httpClient.listSkillFiles(skillName, '.');
      setRootEntries(result.entries);
    } catch (error) {
      console.error('Failed to load skill files:', error);
      toast.error(t('skills.loadFilesError') + String(error));
    } finally {
      setLoading(false);
      onLoadingChange?.(false);
    }
  }, [skillName, t, onLoadingChange]);

  const loadDirFiles = useCallback(
    async (dirPath: string) => {
      setDirContents((prev) => {
        const newMap = new Map(prev);
        newMap.set(dirPath, []); // Clear while loading
        return newMap;
      });
      try {
        const result = await httpClient.listSkillFiles(skillName, dirPath);
        setDirContents((prev) => {
          const newMap = new Map(prev);
          newMap.set(dirPath, result.entries);
          return newMap;
        });
      } catch (error) {
        console.error('Failed to load directory files:', error);
        toast.error(t('skills.loadFilesError') + String(error));
      }
    },
    [skillName, t],
  );

  useEffect(() => {
    if (skillName) {
      loadRootFiles();
    }
  }, [skillName, loadRootFiles]);

  useImperativeHandle(
    ref,
    () => ({
      refresh: loadRootFiles,
      loading,
    }),
    [loadRootFiles, loading],
  );

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

  const renderEntry = (
    entry: FileEntry,
    depth: number = 0,
  ): React.ReactNode => {
    const isExpanded = expandedDirs.has(entry.path);
    const isSelected = selectedPath === entry.path;

    return (
      <div key={entry.path}>
        <div
          className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer hover:bg-muted ${
            isSelected ? 'bg-muted' : ''
          }`}
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
          onClick={() =>
            entry.is_dir ? toggleDir(entry.path) : handleFileClick(entry.path)
          }
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
            <span className="ml-auto text-xs text-muted-foreground">
              {entry.size > 1024
                ? `${Math.round(entry.size / 1024)}KB`
                : `${entry.size}B`}
            </span>
          )}
        </div>
        {entry.is_dir && isExpanded && (
          <div>
            {(dirContents.get(entry.path) || []).map((child) =>
              renderEntry(child, depth + 1),
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="max-h-48 space-y-1 overflow-y-auto">
        {rootEntries.length === 0 && !loading && (
          <div className="text-sm text-muted-foreground py-2">
            {t('skills.noFiles')}
          </div>
        )}
        {rootEntries.map((entry) => renderEntry(entry))}
      </div>
    </div>
  );
});

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
  layout = 'stacked',
  sideFooter,
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
  const fileTreeRef = useRef<FileTreeHandle>(null);
  const [fileTreeLoading, setFileTreeLoading] = useState(false);

  const loadSkill = useCallback(
    async (skillName: string) => {
      try {
        const resp = await httpClient.getSkill(skillName);
        setSkill(resp.skill);
        setSelectedFile('SKILL.md');
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
    setSelectedFile(initialDraftRef.current.selectedFile ?? null);
    setSkill(initialDraftRef.current.skill);
    setShowAdvanced(initialDraftRef.current.showAdvanced);
  }, [initSkillName, loadSkill]);

  useEffect(() => {
    if (initSkillName) return;
    onDraftChange?.({
      skill,
      showAdvanced,
      selectedFile: selectedFile || undefined,
    });
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

  const handleSubmit = async (e: FormEvent) => {
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

  const metadataFields = (
    <>
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
    </>
  );

  const fileTreeSection = (
    <>
      {initSkillName && (
        <div className="space-y-2">
          <FileTree
            skillName={initSkillName}
            selectedFile={selectedFile}
            onFileSelect={handleFileSelect}
          />
        </div>
      )}
    </>
  );

  const instructionEditor = (showLabel = true) => (
    <div className="space-y-2">
      {showLabel && (
        <Label htmlFor="instructions">
          {selectedFile
            ? getFileName(selectedFile)
            : t('skills.skillInstructions')}
        </Label>
      )}
      <Textarea
        id="instructions"
        value={fileContent}
        onChange={(e) => handleContentChange(e.target.value)}
        placeholder={t('skills.instructionsPlaceholder')}
        rows={16}
        className="min-h-[360px] resize-y font-mono text-sm lg:min-h-[calc(100vh-220px)]"
      />
      {selectedFile &&
        selectedFile !== 'SKILL.md' &&
        !selectedFile.endsWith('/SKILL.md') && (
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
  );

  const advancedSettings = (
    <div className="space-y-2">
      <Label>{t('skills.packageRoot')}</Label>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          value={skill.package_root || ''}
          onChange={(e) => setSkill({ ...skill, package_root: e.target.value })}
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
            Boolean(initSkillName) || scanning || !skill.package_root?.trim()
          }
          className="shrink-0"
        >
          <FolderSearch className="mr-1 h-4 w-4" />
          {scanning ? t('common.loading') : t('skills.scan')}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        {t('skills.packageRootHelp')}
      </p>
    </div>
  );

  if (layout === 'split') {
    return (
      <form
        id="skill-form"
        onSubmit={handleSubmit}
        className="flex h-full min-h-0 max-w-full flex-col gap-6 overflow-y-auto lg:flex-row lg:overflow-hidden"
      >
        <div className="space-y-4 pb-6 lg:min-h-0 lg:w-[360px] lg:flex-shrink-0 lg:overflow-y-auto lg:overflow-x-hidden xl:w-[400px]">
          <Card>
            <CardHeader>
              <CardTitle>{t('bots.basicInfo')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">{metadataFields}</CardContent>
          </Card>
          {initSkillName && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>{t('skills.files')}</CardTitle>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => fileTreeRef.current?.refresh()}
                  disabled={fileTreeLoading}
                  className="size-8"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${fileTreeLoading ? 'animate-spin' : ''}`}
                  />
                </Button>
              </CardHeader>
              <CardContent>
                <FileTree
                  ref={fileTreeRef}
                  skillName={initSkillName}
                  selectedFile={selectedFile}
                  onFileSelect={handleFileSelect}
                  onLoadingChange={setFileTreeLoading}
                />
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>{t('skills.advancedSettings')}</CardTitle>
            </CardHeader>
            <CardContent>{advancedSettings}</CardContent>
          </Card>
          {sideFooter}
        </div>
        <div className="hidden w-px shrink-0 bg-border lg:block" />
        <div className="min-w-0 flex-1 pb-6 lg:min-h-0 lg:overflow-y-auto lg:overflow-x-hidden">
          <Card>
            <CardHeader>
              <CardTitle>
                {selectedFile
                  ? getFileName(selectedFile)
                  : initSkillName
                    ? 'SKILL.md'
                    : t('skills.skillInstructions')}
              </CardTitle>
            </CardHeader>
            <CardContent>{instructionEditor(false)}</CardContent>
          </Card>
        </div>
      </form>
    );
  }

  return (
    <form id="skill-form" onSubmit={handleSubmit} className="space-y-4">
      {metadataFields}
      {fileTreeSection}
      {instructionEditor()}
      {advancedSettings}
      {sideFooter}
    </form>
  );
}
