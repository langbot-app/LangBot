import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy, Info, TriangleAlert, Webhook } from 'lucide-react';
import { backendClient } from '@/app/infra/http';
import type { PluginWebhook } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { copyToClipboard } from '@/app/utils/clipboard';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

function CopyableUrl({ url }: { url: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  return (
    <div className="flex min-w-0 items-center gap-2">
      <Input
        value={url}
        readOnly
        className="min-w-0 flex-1 bg-muted font-mono text-xs"
        onClick={(e) => (e.target as HTMLInputElement).select()}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={t('pluginWebhooks.copy')}
        title={t('pluginWebhooks.copy')}
        onClick={() => {
          copyToClipboard(url).catch(() => {});
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        {copied ? (
          <Check className="size-4 text-green-600" />
        ) : (
          <Copy className="size-4" />
        )}
      </Button>
    </div>
  );
}

/**
 * Public webhook URLs exposed by a plugin's Webhook components, displayed
 * like a Bot's generated webhook URL. Renders nothing for plugins that
 * declare no Webhook component.
 */
export default function PluginWebhooks({
  pluginAuthor,
  pluginName,
}: {
  pluginAuthor: string;
  pluginName: string;
}) {
  const { t } = useTranslation();
  const [webhooks, setWebhooks] = useState<PluginWebhook[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    backendClient
      .getPluginWebhooks(pluginAuthor, pluginName)
      .then((resp) => {
        if (!cancelled) setWebhooks(resp.webhooks ?? []);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [pluginAuthor, pluginName]);

  if (!failed && webhooks !== null && webhooks.length === 0) return null;

  const disabled = webhooks?.some((webhook) => !webhook.enabled) ?? false;

  return (
    <Card data-testid="plugin-webhooks">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Webhook className="size-4" />
          {t('pluginWebhooks.title')}
        </CardTitle>
        <CardDescription>{t('pluginWebhooks.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {failed && (
          <p className="text-sm text-destructive">
            {t('pluginWebhooks.loadFailed')}
          </p>
        )}
        {!failed && webhooks === null && <Skeleton className="h-9 w-full" />}
        {disabled && (
          <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 p-3 text-xs text-amber-800 dark:text-amber-300">
            <TriangleAlert className="size-4 shrink-0" />
            <span>{t('pluginWebhooks.disabled')}</span>
          </div>
        )}
        {webhooks?.map((webhook) => {
          const label = extractI18nObject(webhook.label) || webhook.name;
          const description = extractI18nObject(webhook.description);
          return (
            <div key={webhook.name} className="min-w-0 space-y-1.5">
              <div className="flex min-w-0 items-baseline gap-2">
                <span className="truncate text-sm font-medium">{label}</span>
                {label !== webhook.name && (
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">
                    {webhook.name}
                  </span>
                )}
              </div>
              <CopyableUrl url={webhook.webhook_full_url} />
              {webhook.extra_webhook_full_url && (
                <CopyableUrl url={webhook.extra_webhook_full_url} />
              )}
              {description && (
                <p className="text-xs break-words text-muted-foreground">
                  {description}
                </p>
              )}
            </div>
          );
        })}
        {webhooks && webhooks.length > 0 && (
          <p className="flex gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" />
            <span>{t('pluginWebhooks.prefixHint')}</span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}
