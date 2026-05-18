import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { BookOpen, FileArchive, Loader2, PackageOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { Skill } from '@/app/infra/entities/api';
import { cn } from '@/lib/utils';

interface PreviewSkill extends Skill {
  source_path?: string;
}

interface SkillZipPreviewPanelProps {
  file: File;
  onImported: (skillNames: string[]) => void;
  onCancel?: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

function previewPath(skill: PreviewSkill): string {
  return skill.source_path ?? '';
}

function displayPreviewPath(skill: PreviewSkill): string {
  return previewPath(skill) || skill.name;
}

function truncateInstructions(instructions?: string): string {
  if (!instructions) return '';
  const trimmed = instructions.trim();
  if (trimmed.length <= 900) return trimmed;
  return trimmed.slice(0, 900).trimEnd() + '\n...';
}

export default function SkillZipPreviewPanel({
  file,
  onImported,
  onCancel,
}: SkillZipPreviewPanelProps) {
  const { t } = useTranslation();
  const [previewSkills, setPreviewSkills] = useState<PreviewSkill[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [activePath, setActivePath] = useState('');
  const [previewing, setPreviewing] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const lastPreviewSignatureRef = useRef('');
  const previewFileSignature = `${file.name}:${file.size}:${file.lastModified}`;

  const activeSkill = useMemo(
    () =>
      previewSkills.find((skill) => previewPath(skill) === activePath) ||
      previewSkills[0] ||
      null,
    [activePath, previewSkills],
  );

  const loadPreview = useCallback(async () => {
    setPreviewing(true);
    setPreviewSkills([]);
    setSelectedPaths([]);
    setActivePath('');
    setErrorMessage(null);

    try {
      const resp = await httpClient.previewSkillInstallFromUpload(file);
      const skills = (resp.skills || []) as PreviewSkill[];
      setPreviewSkills(skills);
      const paths = skills.map(previewPath);
      setSelectedPaths(paths);
      setActivePath(paths[0] || '');
      if (skills.length === 0) {
        setErrorMessage(t('skills.noSkillMdInDirectory'));
      } else {
        setErrorMessage(null);
      }
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : typeof error === 'object' && error && 'msg' in error
            ? String((error as { msg?: string }).msg || '')
            : String(error);
      setErrorMessage(message || t('skills.previewLoadError'));
    } finally {
      setPreviewing(false);
    }
  }, [file, t]);

  useEffect(() => {
    if (lastPreviewSignatureRef.current === previewFileSignature) return;
    lastPreviewSignatureRef.current = previewFileSignature;
    void loadPreview();
  }, [loadPreview, previewFileSignature]);

  function toggleSelection(path: string) {
    setSelectedPaths((current) => {
      if (current.includes(path)) {
        const next = current.filter((item) => item !== path);
        if (activePath === path) {
          setActivePath(next[0] || path);
        }
        return next;
      }
      setActivePath(path);
      return [...current, path];
    });
  }

  async function handleInstall() {
    if (selectedPaths.length === 0) return;

    setInstalling(true);
    setErrorMessage(null);
    try {
      const resp = await httpClient.installSkillFromUpload(file, selectedPaths);
      toast.success(t('skills.installSuccess'));
      onImported(resp.skills.map((skill) => skill.name));
    } catch (error: unknown) {
      const message =
        error instanceof Error
          ? error.message
          : typeof error === 'object' && error && 'msg' in error
            ? String((error as { msg?: string }).msg || '')
            : String(error);
      setErrorMessage(message || t('skills.installError'));
    } finally {
      setInstalling(false);
    }
  }

  const activeInstructions = truncateInstructions(activeSkill?.instructions);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 rounded-md bg-muted/40 px-3 py-3">
        <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground">
          {previewing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <FileArchive className="size-4" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">
            {previewing ? t('skills.loading') : t('skills.preview')}
          </div>
          <div className="mt-1 break-all text-xs text-muted-foreground">
            {file.name} · {formatFileSize(file.size)}
          </div>
        </div>
      </div>

      {previewSkills.length > 0 && (
        <div
          className={cn(
            'grid gap-4',
            previewSkills.length > 1 && 'md:grid-cols-[240px_minmax(0,1fr)]',
          )}
        >
          {previewSkills.length > 1 && (
            <div className="space-y-2">
              {previewSkills.map((skill) => {
                const path = previewPath(skill);
                const displayPath = displayPreviewPath(skill);
                const selected = selectedPaths.includes(path);
                const active = activePath === path;

                return (
                  <button
                    key={`${path}:${skill.name}`}
                    type="button"
                    className={cn(
                      'flex w-full items-start gap-2 rounded-md px-3 py-2 text-left transition-colors',
                      active ? 'bg-accent' : 'bg-muted/30 hover:bg-accent/70',
                    )}
                    onClick={() => setActivePath(path)}
                  >
                    <Checkbox
                      checked={selected}
                      onCheckedChange={() => toggleSelection(path)}
                      onClick={(event) => event.stopPropagation()}
                      className="mt-0.5"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {skill.display_name || skill.name}
                      </span>
                      {path && (
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                          {displayPath}
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {activeSkill && (
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <BookOpen className="size-4 text-muted-foreground" />
                <h3 className="min-w-0 truncate text-base font-semibold">
                  {activeSkill.display_name || activeSkill.name}
                </h3>
              </div>

              {activeSkill.description && (
                <p className="text-sm leading-6 text-muted-foreground">
                  {activeSkill.description}
                </p>
              )}

              {activeInstructions && (
                <div className="space-y-2">
                  <div className="text-sm font-medium">
                    {t('skills.previewInstructions')}
                  </div>
                  <div className="max-h-56 overflow-y-auto rounded-md bg-muted/40 p-3 font-mono text-xs leading-5 whitespace-pre-wrap">
                    {activeInstructions}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {errorMessage && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {errorMessage}
        </div>
      )}

      <div className="flex justify-end gap-2">
        {onCancel && (
          <Button variant="outline" onClick={onCancel} disabled={installing}>
            {t('common.cancel')}
          </Button>
        )}
        <Button
          type="button"
          onClick={handleInstall}
          disabled={
            previewing ||
            installing ||
            previewSkills.length === 0 ||
            selectedPaths.length === 0
          }
        >
          {installing ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              {t('skills.installing')}
            </>
          ) : (
            <>
              <PackageOpen className="size-4" />
              {t('skills.confirmInstall')}
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
