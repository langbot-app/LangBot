import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FileText, Loader2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { ShareFinding } from '@/app/infra/entities/space-share';
import ShareToSpaceDialog from './ShareToSpaceDialog';

/** Share an installed/created Skill to LangBot Space for review. */
export default function ShareSkillDialog({
  open,
  onOpenChange,
  skillName,
  displayName,
  description,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  skillName: string;
  displayName: string;
  description: string;
}) {
  const { t } = useTranslation();
  const [files, setFiles] = useState<{ path: string; size: number }[] | null>(
    null,
  );
  const [findings, setFindings] = useState<ShareFinding[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setFiles(null);
    setError('');
    httpClient
      .previewSkillShare(skillName)
      .then((res) => {
        setFiles(res.files);
        setFindings(res.findings || []);
      })
      .catch((e) => setError((e as { msg?: string })?.msg || ''));
  }, [open, skillName]);

  return (
    <ShareToSpaceDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('spaceShare.skillTitle')}
      description={t('spaceShare.skillDescription')}
      defaultName={skillName}
      defaultLabel={displayName}
      defaultDescription={description}
      findings={findings}
      canSubmit={!!files && !error}
      showChangelog
      onSubmit={(meta) => httpClient.shareSkill(skillName, meta)}
    >
      <div className="space-y-1.5">
        <div className="text-sm font-medium">
          {t('spaceShare.packageFiles')}
        </div>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : !files ? (
          <Loader2 className="size-4 animate-spin text-muted-foreground" />
        ) : (
          <div className="max-h-40 overflow-y-auto rounded-md border p-2 font-mono text-xs">
            {files.map((f) => (
              <div key={f.path} className="flex items-center gap-1.5 py-0.5">
                <FileText className="size-3 shrink-0 text-muted-foreground" />
                <span className="truncate">{f.path}</span>
                <span className="ml-auto text-muted-foreground">
                  {f.size} B
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </ShareToSpaceDialog>
  );
}
