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
  ChevronDown,
  ChevronRight,
  FileIcon,
  Folder,
  FolderOpen,
  FolderUp,
  Loader2,
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

interface PreviewSkill extends Skill {
  source_path?: string;
  entry_file?: string;
}

type DirectoryFile = File & {
  webkitRelativePath?: string;
};

interface DirectoryTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  size: number | null;
  children: DirectoryTreeNode[];
}

const CRC32_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i += 1) {
  let value = i;
  for (let j = 0; j < 8; j += 1) {
    value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
  }
  CRC32_TABLE[i] = value >>> 0;
}

function crc32(bytes: Uint8Array) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc = CRC32_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function writeUint16(target: Uint8Array, offset: number, value: number) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
}

function writeUint32(target: Uint8Array, offset: number, value: number) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  target[offset + 2] = (value >>> 16) & 0xff;
  target[offset + 3] = (value >>> 24) & 0xff;
}

function dosDateTime(timestamp: number) {
  const date = new Date(timestamp || Date.now());
  const year = Math.max(date.getFullYear(), 1980);
  return {
    time:
      (date.getHours() << 11) |
      (date.getMinutes() << 5) |
      Math.floor(date.getSeconds() / 2),
    date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
  };
}

function concatUint8Arrays(chunks: Uint8Array[]) {
  const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

async function createStoredZip(
  entries: Array<{ name: string; file: File }>,
): Promise<Blob> {
  const encoder = new TextEncoder();
  const localChunks: Uint8Array[] = [];
  const centralChunks: Uint8Array[] = [];
  let localOffset = 0;

  for (const entry of entries) {
    const nameBytes = encoder.encode(entry.name);
    const fileBytes = new Uint8Array(await entry.file.arrayBuffer());
    const checksum = crc32(fileBytes);
    const dateTime = dosDateTime(entry.file.lastModified);

    const localHeader = new Uint8Array(30 + nameBytes.length);
    writeUint32(localHeader, 0, 0x04034b50);
    writeUint16(localHeader, 4, 20);
    writeUint16(localHeader, 6, 0);
    writeUint16(localHeader, 8, 0);
    writeUint16(localHeader, 10, dateTime.time);
    writeUint16(localHeader, 12, dateTime.date);
    writeUint32(localHeader, 14, checksum);
    writeUint32(localHeader, 18, fileBytes.length);
    writeUint32(localHeader, 22, fileBytes.length);
    writeUint16(localHeader, 26, nameBytes.length);
    writeUint16(localHeader, 28, 0);
    localHeader.set(nameBytes, 30);
    localChunks.push(localHeader, fileBytes);

    const centralHeader = new Uint8Array(46 + nameBytes.length);
    writeUint32(centralHeader, 0, 0x02014b50);
    writeUint16(centralHeader, 4, 20);
    writeUint16(centralHeader, 6, 20);
    writeUint16(centralHeader, 8, 0);
    writeUint16(centralHeader, 10, 0);
    writeUint16(centralHeader, 12, dateTime.time);
    writeUint16(centralHeader, 14, dateTime.date);
    writeUint32(centralHeader, 16, checksum);
    writeUint32(centralHeader, 20, fileBytes.length);
    writeUint32(centralHeader, 24, fileBytes.length);
    writeUint16(centralHeader, 28, nameBytes.length);
    writeUint16(centralHeader, 30, 0);
    writeUint16(centralHeader, 32, 0);
    writeUint16(centralHeader, 34, 0);
    writeUint16(centralHeader, 36, 0);
    writeUint32(centralHeader, 38, 0);
    writeUint32(centralHeader, 42, localOffset);
    centralHeader.set(nameBytes, 46);
    centralChunks.push(centralHeader);

    localOffset += localHeader.length + fileBytes.length;
  }

  const centralDirectory = concatUint8Arrays(centralChunks);
  const endRecord = new Uint8Array(22);
  writeUint32(endRecord, 0, 0x06054b50);
  writeUint16(endRecord, 4, 0);
  writeUint16(endRecord, 6, 0);
  writeUint16(endRecord, 8, entries.length);
  writeUint16(endRecord, 10, entries.length);
  writeUint32(endRecord, 12, centralDirectory.length);
  writeUint32(endRecord, 16, localOffset);
  writeUint16(endRecord, 20, 0);

  return new Blob([...localChunks, centralDirectory, endRecord] as BlobPart[], {
    type: 'application/zip',
  });
}

function pathDirname(path: string) {
  const normalized = path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  const index = normalized.lastIndexOf('/');
  return index >= 0 ? normalized.slice(0, index) : '';
}

function pathBasename(path: string) {
  const normalized = path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  return normalized.split('/').pop() || normalized;
}

function buildDirectoryTree(
  entries: Array<{ path: string; size: number | null }>,
): DirectoryTreeNode[] {
  const root: DirectoryTreeNode = {
    name: '',
    path: '',
    is_dir: true,
    size: null,
    children: [],
  };

  for (const entry of entries) {
    const path = entry.path;
    const parts = path.split('/').filter(Boolean);
    let current = root;

    parts.forEach((part, index) => {
      const isLast = index === parts.length - 1;
      const nodePath = parts.slice(0, index + 1).join('/');
      let node = current.children.find((child) => child.name === part);
      if (!node) {
        node = {
          name: part,
          path: nodePath,
          is_dir: !isLast,
          size: null,
          children: [],
        };
        current.children.push(node);
      }
      if (!isLast) {
        node.is_dir = true;
      }
      if (isLast) {
        node.size = entry.size;
      }
      current = node;
    });
  }

  function sortNodes(nodes: DirectoryTreeNode[]) {
    nodes.sort((a, b) => {
      if (a.is_dir !== b.is_dir) {
        return a.is_dir ? -1 : 1;
      }
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((node) => sortNodes(node.children));
  }

  sortNodes(root.children);
  return root.children;
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
            <FileIcon className="h-4 w-4 text-gray-500" />
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
      <div className="max-h-[min(46vh,32rem)] space-y-1 overflow-y-auto overscroll-contain pr-1">
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

interface LocalFileTreeProps {
  entries: DirectoryTreeNode[];
  fileMap: Map<string, File>;
  selectedFile?: string | null;
  onFileSelect: (path: string, content: string) => void;
}

function collectDirectoryPaths(nodes: DirectoryTreeNode[]): string[] {
  return nodes.flatMap((node) =>
    node.is_dir ? [node.path, ...collectDirectoryPaths(node.children)] : [],
  );
}

function LocalFileTree({
  entries,
  fileMap,
  selectedFile,
  onFileSelect,
}: LocalFileTreeProps) {
  const { t } = useTranslation();
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    setSelectedPath(selectedFile ?? null);
  }, [selectedFile]);

  useEffect(() => {
    setExpandedDirs(new Set(collectDirectoryPaths(entries)));
  }, [entries]);

  const toggleDir = (dirPath: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dirPath)) {
        next.delete(dirPath);
      } else {
        next.add(dirPath);
      }
      return next;
    });
  };

  const handleFileClick = async (filePath: string) => {
    const file = fileMap.get(filePath);
    if (!file) return;

    setSelectedPath(filePath);
    try {
      onFileSelect(filePath, await file.text());
    } catch (error) {
      console.error('Failed to read local file:', error);
      toast.error(t('skills.readFileError') + String(error));
    }
  };

  const renderEntry = (entry: DirectoryTreeNode, depth: number = 0) => {
    const isExpanded = expandedDirs.has(entry.path);
    const isSelected = selectedPath === entry.path;

    return (
      <div key={entry.path}>
        <div
          className={`flex items-center gap-1 rounded px-2 py-1 hover:bg-muted ${
            isSelected ? 'bg-muted' : ''
          } cursor-pointer`}
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
            <FileIcon className="h-4 w-4 text-gray-500" />
          )}
          <span className="truncate text-sm">{entry.name}</span>
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
            {entry.children.map((child) => renderEntry(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      <div className="max-h-[min(46vh,32rem)] space-y-1 overflow-y-auto overscroll-contain pr-1">
        {entries.length === 0 && (
          <div className="py-2 text-sm text-muted-foreground">
            {t('skills.noFiles')}
          </div>
        )}
        {entries.map((entry) => renderEntry(entry))}
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
  layout = 'stacked',
  sideFooter,
}: SkillFormProps) {
  const { t } = useTranslation();
  const initialDraftRef = useRef(initialDraft ?? emptySkillDraft);
  const [skill, setSkill] = useState<Partial<Skill>>(
    initialDraftRef.current.skill,
  );
  const [importingDirectory, setImportingDirectory] = useState(false);
  const [installingDirectory, setInstallingDirectory] = useState(false);
  const [directoryZipFile, setDirectoryZipFile] = useState<File | null>(null);
  const [directoryPreview, setDirectoryPreview] = useState<PreviewSkill | null>(
    null,
  );
  const [directorySourceName, setDirectorySourceName] = useState('');
  const [directoryTree, setDirectoryTree] = useState<DirectoryTreeNode[]>([]);
  const [directoryFileMap, setDirectoryFileMap] = useState<Map<string, File>>(
    new Map(),
  );
  const [showAdvanced, setShowAdvanced] = useState(
    initialDraftRef.current.showAdvanced,
  );
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const fileTreeRef = useRef<FileTreeHandle>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);
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
    directoryInputRef.current?.setAttribute('webkitdirectory', '');
    directoryInputRef.current?.setAttribute('directory', '');
  }, []);

  useEffect(() => {
    if (initSkillName) {
      loadSkill(initSkillName);
      return;
    }
    setSelectedFile(initialDraftRef.current.selectedFile ?? null);
    setSkill(initialDraftRef.current.skill);
    setShowAdvanced(initialDraftRef.current.showAdvanced);
    setDirectoryZipFile(null);
    setDirectoryPreview(null);
    setDirectorySourceName('');
    setDirectoryTree([]);
    setDirectoryFileMap(new Map());
  }, [initSkillName, loadSkill]);

  useEffect(() => {
    if (initSkillName) return;
    onDraftChange?.({
      skill,
      showAdvanced,
      selectedFile: selectedFile || undefined,
    });
  }, [initSkillName, onDraftChange, skill, showAdvanced, selectedFile]);

  async function handleDirectoryImport(
    event: React.ChangeEvent<HTMLInputElement>,
  ) {
    const files = Array.from(event.target.files ?? []) as DirectoryFile[];
    event.target.value = '';
    if (files.length === 0) {
      return;
    }

    const skillMdFiles = files.filter((file) => {
      const relativePath = file.webkitRelativePath || file.name;
      return pathBasename(relativePath).toLowerCase() === 'skill.md';
    });
    if (skillMdFiles.length === 0) {
      toast.error(t('skills.noSkillMdInDirectory'));
      return;
    }
    if (skillMdFiles.length > 1) {
      toast.error(t('skills.multipleSkillMdInDirectory'));
      return;
    }

    const skillMdRelativePath =
      skillMdFiles[0].webkitRelativePath || skillMdFiles[0].name;
    const skillDir = pathDirname(skillMdRelativePath);
    const packageName = pathBasename(
      skillDir || pathDirname(files[0].webkitRelativePath || '') || 'skill',
    );
    const prefix = skillDir ? `${skillDir}/` : '';
    const selectedFiles = files
      .map((file) => {
        const relativePath = file.webkitRelativePath || file.name;
        if (prefix && !relativePath.startsWith(prefix)) {
          return null;
        }
        const pathInPackage = prefix
          ? relativePath.slice(prefix.length)
          : relativePath;
        if (!pathInPackage || pathInPackage.endsWith('/')) {
          return null;
        }
        return {
          path: pathInPackage.replace(/^\/+/, ''),
          file,
        };
      })
      .filter((entry): entry is { path: string; file: File } => Boolean(entry));
    const packageFiles = selectedFiles.map((entry) => ({
      name: `${packageName}/${entry.path}`,
      file: entry.file,
    }));

    setImportingDirectory(true);
    try {
      const zipBlob = await createStoredZip(packageFiles);
      const zipFile = new File([zipBlob], `${packageName}.zip`, {
        type: 'application/zip',
      });
      const resp = await httpClient.previewSkillInstallFromUpload(zipFile);
      const preview = (resp.skills?.[0] ?? null) as PreviewSkill | null;
      if (!preview) {
        toast.error(t('skills.noSkillMdInDirectory'));
        return;
      }

      setDirectoryZipFile(zipFile);
      setDirectoryPreview(preview);
      setDirectorySourceName(packageName);
      setDirectoryTree(
        buildDirectoryTree(
          selectedFiles.map((entry) => ({
            path: entry.path,
            size: entry.file.size,
          })),
        ),
      );
      setDirectoryFileMap(
        new Map(selectedFiles.map((entry) => [entry.path, entry.file])),
      );
      setSelectedFile(preview.entry_file || 'SKILL.md');
      setFileContent(preview.instructions || '');
      setSkill({
        name: preview.name || packageName,
        display_name: preview.display_name || '',
        description: preview.description || '',
        instructions: preview.instructions || '',
        package_root: preview.package_root || '',
      });
    } catch (error) {
      console.error('Failed to import local skill directory:', error);
      toast.error(t('skills.importDirectoryError') + String(error));
    } finally {
      setImportingDirectory(false);
    }
  }

  function clearDirectoryPreview() {
    setDirectoryZipFile(null);
    setDirectoryPreview(null);
    setDirectorySourceName('');
    setDirectoryTree([]);
    setDirectoryFileMap(new Map());
    setSelectedFile(null);
    setFileContent('');
    setSkill({ ...emptySkillDraft.skill });
  }

  async function handleDirectoryImportConfirm() {
    if (!directoryZipFile) {
      return;
    }

    setInstallingDirectory(true);
    try {
      const resp = await httpClient.installSkillFromUpload(directoryZipFile);
      toast.success(t('skills.installSuccess'));
      onNewSkillCreated(
        resp.skills[0]?.name || directoryPreview?.name || directorySourceName,
      );
    } catch (error) {
      console.error('Failed to install local skill directory:', error);
      toast.error(t('skills.importDirectoryError') + String(error));
    } finally {
      setInstallingDirectory(false);
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

  const handleInstructionDraftChange = (content: string) => {
    setFileContent(content);
    setSkill((prev) => ({ ...prev, instructions: content }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!initSkillName && directoryZipFile) {
      await handleDirectoryImportConfirm();
      return;
    }

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
          disabled={Boolean(directoryPreview)}
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
          disabled={Boolean(initSkillName || directoryPreview)}
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
          disabled={Boolean(directoryPreview)}
        />
      </div>
    </>
  );

  const fileTreeSection = (
    <>
      {initSkillName ? (
        <div className="space-y-2">
          <FileTree
            skillName={initSkillName}
            selectedFile={selectedFile}
            onFileSelect={handleFileSelect}
          />
        </div>
      ) : (
        directoryPreview && (
          <div className="space-y-2">
            <LocalFileTree
              entries={directoryTree}
              fileMap={directoryFileMap}
              selectedFile={selectedFile}
              onFileSelect={handleFileSelect}
            />
          </div>
        )
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
        onChange={(e) => handleInstructionDraftChange(e.target.value)}
        readOnly={Boolean(initSkillName || directoryPreview)}
        placeholder={t('skills.instructionsPlaceholder')}
        rows={16}
        className="min-h-[360px] resize-y font-mono text-sm read-only:cursor-default read-only:bg-muted/30 lg:min-h-[calc(100vh-220px)]"
      />
    </div>
  );

  const localDirectoryImport = (
    <div className="flex flex-col gap-2 sm:flex-row">
      <input
        ref={directoryInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleDirectoryImport}
      />
      <Button
        type="button"
        variant={directoryPreview ? 'secondary' : 'outline'}
        onClick={() => directoryInputRef.current?.click()}
        disabled={importingDirectory || installingDirectory}
        className="w-full shrink-0 sm:w-auto"
      >
        {importingDirectory ? (
          <Loader2 className="mr-1.5 size-4 animate-spin" />
        ) : (
          <FolderUp className="mr-1.5 size-4" />
        )}
        {importingDirectory
          ? t('skills.importingDirectory')
          : directoryPreview
            ? t('skills.chooseAnotherDirectory')
            : t('skills.chooseSkillDirectory')}
      </Button>
      {directoryPreview && (
        <Button
          type="button"
          variant="ghost"
          onClick={clearDirectoryPreview}
          disabled={installingDirectory}
          className="w-full shrink-0 sm:w-auto"
        >
          {t('skills.clearDirectoryPreview')}
        </Button>
      )}
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
          {!initSkillName && (
            <Card>
              <CardHeader>
                <CardTitle>{t('skills.importLocalDirectory')}</CardTitle>
              </CardHeader>
              <CardContent>{localDirectoryImport}</CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>{t('bots.basicInfo')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">{metadataFields}</CardContent>
          </Card>
          {(initSkillName || directoryPreview) && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle>{t('skills.files')}</CardTitle>
                {initSkillName && (
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
                )}
              </CardHeader>
              <CardContent>
                {initSkillName ? (
                  <FileTree
                    ref={fileTreeRef}
                    skillName={initSkillName}
                    selectedFile={selectedFile}
                    onFileSelect={handleFileSelect}
                    onLoadingChange={setFileTreeLoading}
                  />
                ) : (
                  <LocalFileTree
                    entries={directoryTree}
                    fileMap={directoryFileMap}
                    selectedFile={selectedFile}
                    onFileSelect={handleFileSelect}
                  />
                )}
              </CardContent>
            </Card>
          )}
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
      {!initSkillName && localDirectoryImport}
      {metadataFields}
      {fileTreeSection}
      {instructionEditor()}
      {sideFooter}
    </form>
  );
}
