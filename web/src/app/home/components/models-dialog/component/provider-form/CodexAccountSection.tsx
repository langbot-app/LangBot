import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import type { useCodexLogin } from './useCodexLogin';

export default function CodexAccountSection({
  login,
  providerId,
}: {
  login: ReturnType<typeof useCodexLogin>;
  providerId?: string;
}) {
  const { t } = useTranslation();
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const { phase, device } = login;
  const waiting = ['starting', 'loading', 'canceling'].includes(phase);
  return (
    <section
      data-testid="codex-account"
      aria-label={t('models.codex.account')}
      className="min-w-0 rounded-lg border p-3 space-y-3 text-sm"
    >
      <div>
        <h3 className="font-medium">{t('models.codex.account')}</h3>
        <p className="mt-1 text-muted-foreground">
          {t('models.codex.description')}
        </p>
      </div>
      <p
        role={phase === 'error' ? 'alert' : 'status'}
        aria-live="polite"
        className={
          phase === 'error' ? 'text-destructive' : 'text-muted-foreground'
        }
      >
        {t(`models.codex.${phase}`)}
      </p>
      {device && phase === 'pending' && (
        <div className="space-y-3">
          <p className="text-muted-foreground">
            {t('models.codex.instructions')}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="select-all break-all rounded border bg-muted px-3 py-2 text-base font-semibold tracking-wider">
              {device.user_code}
            </code>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(device.user_code);
                  setCopied(true);
                  setCopyFailed(false);
                } catch {
                  setCopyFailed(true);
                }
              }}
            >
              {t(copied ? 'models.codex.copied' : 'models.codex.copyCode')}
            </Button>
          </div>
          {copyFailed && (
            <p role="status" className="text-muted-foreground">
              {t('models.codex.copyManually')}
            </p>
          )}
          <a
            href={device.verification_uri}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex text-sm font-medium underline underline-offset-4"
          >
            {t('models.codex.continueAtOpenAI')}
          </a>
          <p className="text-xs text-muted-foreground">
            {t('models.codex.expiresAt', {
              time: new Date(device.expires_at * 1000).toLocaleTimeString(),
            })}
          </p>
          {login.retrying && (
            <p role="status" className="text-xs text-muted-foreground">
              {t('models.codex.retrying')}
            </p>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => providerId && void login.cancel(providerId)}
          >
            {t('models.codex.cancelSignIn')}
          </Button>
        </div>
      )}
      {providerId && !waiting && phase !== 'pending' && (
        <div className="flex flex-wrap gap-2">
          {phase !== 'connected' && (
            <Button type="submit" size="sm" variant="outline">
              {t(
                phase === 'error' || phase === 'expired'
                  ? 'models.codex.tryAgain'
                  : 'models.codex.signIn',
              )}
            </Button>
          )}
          {phase === 'connected' && (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setConfirmDisconnect(false);
                  void login.start(providerId);
                }}
              >
                {t('models.codex.reconnect')}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setConfirmDisconnect(true)}
              >
                {t('models.codex.disconnect')}
              </Button>
            </>
          )}
        </div>
      )}
      {confirmDisconnect && phase === 'connected' && (
        <div className="space-y-2 border-t pt-3">
          <p>{t('models.codex.disconnectConfirm')}</p>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="destructive"
              onClick={() => {
                setConfirmDisconnect(false);
                if (providerId) void login.disconnect(providerId);
              }}
            >
              {t('models.codex.confirmDisconnect')}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setConfirmDisconnect(false)}
            >
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
