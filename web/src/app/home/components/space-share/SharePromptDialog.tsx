import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import type {
  PromptKind,
  PromptMessage,
  ShareFinding,
} from '@/app/infra/entities/space-share';
import ShareToSpaceDialog from './ShareToSpaceDialog';

/** Share the current Pipeline / Agent prompt to the Space prompt library. */
export default function SharePromptDialog({
  open,
  onOpenChange,
  kind,
  messages,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kind: PromptKind;
  messages: PromptMessage[];
}) {
  const { t, i18n } = useTranslation();
  const [findings, setFindings] = useState<ShareFinding[]>([]);
  const [variables, setVariables] = useState<{ name: string }[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) return;
    setError('');
    httpClient
      .previewPromptShare({ kind, messages })
      .then((res) => {
        setFindings(res.findings || []);
        setVariables(
          ((res.payload as { variables?: { name: string }[] }).variables ||
            []) as { name: string }[],
        );
      })
      .catch((e) => {
        setFindings([]);
        setError((e as { msg?: string })?.msg || '');
      });
  }, [open, kind, messages]);

  return (
    <ShareToSpaceDialog
      open={open}
      onOpenChange={onOpenChange}
      title={t('spaceShare.promptTitle')}
      itemType="prompt"
      promptKind={kind}
      description={
        kind === 'agent'
          ? t('spaceShare.promptDescriptionAgent')
          : t('spaceShare.promptDescriptionMessaging')
      }
      defaultName=""
      defaultLabel=""
      defaultDescription=""
      findings={findings}
      canSubmit={!error}
      onSubmit={(meta, ack) =>
        httpClient.sharePrompt({
          ...meta,
          kind,
          language: (i18n.language || 'en_US').replace('-', '_'),
          messages,
          variables,
          acknowledge_warnings: ack,
        })
      }
    >
      {error && <div className="text-sm text-destructive">{error}</div>}
      <div className="max-h-56 space-y-2 overflow-y-auto rounded-md border p-2">
        {messages.map((m, i) => (
          <div key={i} className="rounded bg-muted/40 p-2">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">
              {m.role}
            </div>
            <div className="line-clamp-6 whitespace-pre-wrap break-words text-sm">
              {m.content}
            </div>
          </div>
        ))}
      </div>
      {variables.length > 0 && (
        <div className="text-xs text-muted-foreground">
          {t('spaceShare.detectedVariables')}{' '}
          {variables.map((v) => (
            <code key={v.name} className="mr-1 rounded bg-muted px-1">
              {`{{${v.name}}}`}
            </code>
          ))}
        </div>
      )}
    </ShareToSpaceDialog>
  );
}
