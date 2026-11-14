import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { KeyRound, Loader2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import type { MCPSharePreview } from '@/app/infra/entities/space-share';
import { Input } from '@/components/ui/input';
import ShareToSpaceDialog from './ShareToSpaceDialog';

/**
 * Share a remote MCP server. Credentials never leave the instance: Core
 * replaces them with ${VAR} placeholders, and installers are asked for their
 * own values. The preview shows exactly what will be published.
 */
export default function ShareMCPDialog({
  open,
  onOpenChange,
  serverName,
  description,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverName: string;
  description: string;
}) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<MCPSharePreview | null>(null);
  const [error, setError] = useState('');
  const [labels, setLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    setError('');
    setLabels({});
    httpClient
      .previewMCPShare(serverName)
      .then(setPreview)
      .catch((e) => setError((e as { msg?: string })?.msg || ''));
  }, [open, serverName]);

  const overrides = useMemo(
    () => ({
      inputs: Object.fromEntries(
        Object.entries(labels)
          .filter(([, v]) => v.trim())
          .map(([k, v]) => [k, { label: v.trim() }]),
      ),
    }),
    [labels],
  );

  const shortName = serverName.includes('__')
    ? serverName.split('__').pop() || serverName
    : serverName;

  return (
    <ShareToSpaceDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('spaceShare.mcpTitle')}
      description={t('spaceShare.mcpDescription')}
      defaultName={shortName}
      defaultLabel={shortName}
      defaultDescription={description}
      canSubmit={!!preview && !error}
      onSubmit={(meta) =>
        httpClient.shareMCP(serverName, { ...meta, overrides })
      }
    >
      {error ? (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      ) : !preview ? (
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      ) : (
        <div className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">
              {t('spaceShare.mcpPublishedConfig')}
            </div>
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all rounded-md bg-muted p-2 text-xs">
              {JSON.stringify(
                { url: preview.payload.url, headers: preview.payload.headers },
                null,
                2,
              )}
            </pre>
            <div className="text-xs text-muted-foreground">
              {t('spaceShare.mcpToolsCount', {
                count: preview.payload.tools.length,
              })}
            </div>
          </div>
          {preview.payload.required_inputs.length > 0 ? (
            <div className="space-y-2 rounded-md border border-emerald-300/60 bg-emerald-50/50 p-3 dark:border-emerald-700/50 dark:bg-emerald-900/10">
              <div className="flex items-center gap-1.5 text-sm font-medium">
                <KeyRound className="size-4 text-emerald-600" />
                {t('spaceShare.mcpRedactedTitle', {
                  count: preview.payload.required_inputs.length,
                })}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('spaceShare.mcpRedactedHint')}
              </div>
              {preview.payload.required_inputs.map((inp) => (
                <div
                  key={inp.name}
                  className="grid grid-cols-[140px_1fr] items-center gap-2"
                >
                  <code className="truncate text-xs">{`\${${inp.name}}`}</code>
                  <Input
                    className="h-8"
                    placeholder={t('spaceShare.mcpInputLabelPlaceholder', {
                      label: inp.label,
                    })}
                    value={labels[inp.name] ?? ''}
                    onChange={(e) =>
                      setLabels((prev) => ({
                        ...prev,
                        [inp.name]: e.target.value,
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">
              {t('spaceShare.mcpNoCredentials')}
            </div>
          )}
        </div>
      )}
    </ShareToSpaceDialog>
  );
}
