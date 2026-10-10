import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, ExternalLink } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { getBackendBaseUrl } from '@/app/infra/http/backendUrl';
import { getActiveWorkspaceUuid } from '@/app/infra/http/workspaceContext';

type Config = Record<string, string | boolean>;

export default function SlackSetupDialog({
  open,
  onOpenChange,
  botId,
  webhookUrl,
  socketMode,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  botId?: string;
  webhookUrl: string;
  socketMode: boolean;
  onSuccess: (config: Config) => void;
}) {
  const { t } = useTranslation();
  const [access, setAccess] = useState('');
  const [refresh, setRefresh] = useState('');
  const [name, setName] = useState('LangBot');
  const [url, setUrl] = useState(webhookUrl);
  const [redirect, setRedirect] = useState('');
  const [appToken, setAppToken] = useState('');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [authorizeUrl, setAuthorizeUrl] = useState('');
  const [appId, setAppId] = useState('');
  const [config, setConfig] = useState<Config | null>(null);
  const generation = useRef(0);
  const session = useRef<{
    id: string;
    base: string;
    headers: Record<string, string>;
  } | null>(null);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;

  const cleanup = () => {
    generation.current++;
    const current = session.current;
    session.current = null;
    if (current)
      void fetch(`${current.base}/${current.id}`, {
        method: 'DELETE',
        headers: current.headers,
        keepalive: true,
      }).catch(() => {});
  };

  useEffect(() => {
    if (open) {
      setUrl(webhookUrl);
      const backend = new URL(
        getBackendBaseUrl() || window.location.origin,
        window.location.origin,
      );
      if (backend.hostname === '127.0.0.1') backend.hostname = 'localhost';
      setRedirect(
        `${backend.href.replace(/\/$/, '')}/api/v1/platform/adapters/slack/setup/callback`,
      );
      setStatus('idle');
      setError('');
      setConfig(null);
      setAppId('');
      setAuthorizeUrl('');
    }
    return () => {
      cleanup();
      setAccess('');
      setRefresh('');
      setAppToken('');
    };
  }, [open, webhookUrl]);

  const start = async () => {
    cleanup();
    const version = generation.current;
    setStatus('creating');
    setError('');
    const workspace = getActiveWorkspaceUuid();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      ...(workspace ? { 'X-Workspace-Id': workspace } : {}),
    };
    const base = `${getBackendBaseUrl()}/api/v1/platform/adapters/slack/setup`;
    try {
      const response = await fetch(base, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          bot_uuid: botId,
          access_token: access,
          refresh_token: refresh,
          name,
          webhook_url: url,
          socket_mode: socketMode,
          redirect_url: redirect,
        }),
      });
      const result = await response.json();
      if (!response.ok || result.code !== 0)
        throw new Error(result.msg || `HTTP ${response.status}`);
      const current = { id: result.data.session_id as string, base, headers };
      if (generation.current !== version) {
        void fetch(`${base}/${current.id}`, { method: 'DELETE', headers });
        return;
      }
      session.current = current;
      setAccess('');
      setRefresh('');
      const deadline = Date.now() + 15 * 60 * 1000;
      while (generation.current === version && Date.now() < deadline) {
        const poll = await fetch(`${base}/${current.id}`, {
          headers,
          cache: 'no-store',
        });
        const json = await poll.json();
        if (generation.current !== version) return;
        if (!poll.ok || json.code !== 0)
          throw new Error(json.msg || `HTTP ${poll.status}`);
        const data = json.data;
        setStatus(data.status);
        if (data.app_id) setAppId(data.app_id);
        if (data.authorize_url) setAuthorizeUrl(data.authorize_url);
        if (data.status === 'error') throw new Error(data.error);
        if (data.status === 'success') {
          setConfig(data.config);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      if (generation.current === version) throw new Error('session_expired');
    } catch (cause) {
      if (generation.current !== version) return;
      setError(cause instanceof Error ? cause.message : 'setup_failed');
      setStatus('error');
    }
  };

  const apply = () => {
    if (!config) return;
    onSuccessRef.current({
      ...config,
      ...(socketMode ? { app_token: appToken.trim() } : {}),
    });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t('slackSetup.title')}</DialogTitle>
          <DialogDescription>{t('slackSetup.description')}</DialogDescription>
        </DialogHeader>
        {!botId ? (
          <p>{t('slackSetup.saveFirst')}</p>
        ) : (
          <div className="space-y-4">
            {status === 'idle' && (
              <>
                <a
                  className="text-sm text-primary underline"
                  href="https://api.slack.com/apps"
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('slackSetup.generate')}
                </a>
                <div className="space-y-2">
                  <Label htmlFor="slack-name">{t('slackSetup.name')}</Label>
                  <Input
                    id="slack-name"
                    value={name}
                    maxLength={35}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slack-access">Access Token</Label>
                  <Input
                    id="slack-access"
                    type="password"
                    autoComplete="off"
                    value={access}
                    onChange={(e) => setAccess(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slack-refresh">Refresh Token</Label>
                  <Input
                    id="slack-refresh"
                    type="password"
                    autoComplete="off"
                    value={refresh}
                    onChange={(e) => setRefresh(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="slack-url">
                    {t(
                      socketMode ? 'slackSetup.redirect' : 'slackSetup.webhook',
                    )}
                  </Label>
                  <Input
                    id="slack-url"
                    value={socketMode ? redirect : url}
                    onChange={(e) =>
                      socketMode
                        ? setRedirect(e.target.value)
                        : setUrl(e.target.value)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    {t(
                      socketMode
                        ? 'slackSetup.redirectHint'
                        : 'slackSetup.webhookHint',
                    )}
                  </p>
                </div>
                <Button
                  type="button"
                  onClick={() => void start()}
                  disabled={!access.trim() || !refresh.trim() || !name.trim()}
                >
                  {t('slackSetup.create')}
                </Button>
              </>
            )}
            {(status === 'creating' || status === 'authorizing') && (
              <p className="flex items-center gap-2 text-sm">
                <Loader2 className="size-4 animate-spin" />
                {t(`slackSetup.${status}`)}
              </p>
            )}
            {status === 'waiting' && (
              <div className="space-y-3">
                <p className="text-sm">{t('slackSetup.waiting')}</p>
                <Button asChild>
                  <a href={authorizeUrl} target="_blank" rel="noreferrer">
                    {t('slackSetup.authorize')}
                    <ExternalLink className="ml-2 size-4" />
                  </a>
                </Button>
              </div>
            )}
            {socketMode && appId && (
              <div className="space-y-2 rounded-lg border p-3">
                <p className="text-sm">{t('slackSetup.appTokenHint')}</p>
                <a
                  className="text-sm text-primary underline"
                  href={`https://api.slack.com/apps/${appId}/general`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('slackSetup.openApp')}
                </a>
                <Label htmlFor="slack-app-token" className="block">
                  App-Level Token
                </Label>
                <Input
                  id="slack-app-token"
                  type="password"
                  autoComplete="off"
                  placeholder="xapp-…"
                  value={appToken}
                  onChange={(e) => setAppToken(e.target.value)}
                />
              </div>
            )}
            {status === 'error' && (
              <div className="space-y-2">
                <p role="alert" className="text-sm text-destructive">
                  {t('slackSetup.failed')} {error}
                </p>
                {appId && (
                  <p className="text-xs text-muted-foreground">
                    {t('slackSetup.appCreated')} {appId}
                  </p>
                )}
                <Button
                  type="button"
                  onClick={() => {
                    cleanup();
                    setStatus('idle');
                  }}
                >
                  {t('slackSetup.retry')}
                </Button>
              </div>
            )}
            {status === 'success' && (
              <div className="space-y-3">
                <p className="text-sm">{t('slackSetup.success')}</p>
                <Button
                  type="button"
                  onClick={apply}
                  disabled={socketMode && !appToken.trim().startsWith('xapp-')}
                >
                  {t('slackSetup.apply')}
                </Button>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
