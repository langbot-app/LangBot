import { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Loader2, Lock, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';

import langbotIcon from '@/app/assets/langbot-logo.webp';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { LanguageSelector } from '@/components/ui/language-selector';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import type {
  Workspace,
  WorkspaceInvitation,
} from '@/app/infra/entities/workspace';
import {
  backendClient,
  beginAuthenticatedSession,
  bootstrapWorkspaceSession,
  clearPendingInvitationToken,
  clearUserInfo,
  getPendingInvitationToken,
  setPendingInvitationToken,
} from '@/app/infra/http';

type InvitationView = {
  invitation: WorkspaceInvitation;
  workspace: Workspace;
};

function captureInvitationTokenFromFragment(): string | null {
  if (typeof window === 'undefined') return null;
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get('token')?.trim();
  if (!token) return getPendingInvitationToken();

  setPendingInvitationToken(token);
  window.history.replaceState(
    null,
    document.title,
    `${window.location.pathname}${window.location.search}`,
  );
  return token;
}

export default function AcceptInvitationPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [invitationHash, setInvitationHash] = useState(() =>
    typeof window === 'undefined' ? '' : window.location.hash,
  );
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<InvitationView | null>(null);
  const [status, setStatus] = useState<
    'loading' | 'ready' | 'submitting' | 'success' | 'error'
  >('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    const handleHashChange = () => setInvitationHash(window.location.hash);
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    setStatus('loading');
    setView(null);
    setErrorMessage('');
    const invitationToken = captureInvitationTokenFromFragment();
    setToken(invitationToken);
    if (!invitationToken) {
      setErrorMessage(t('workspace.invitationMissing'));
      setStatus('error');
      return;
    }

    let cancelled = false;
    backendClient
      .inspectWorkspaceInvitation(invitationToken)
      .then((response) => {
        if (cancelled) return;
        setView(response);
        setStatus('ready');
      })
      .catch((error: { code?: string; msg?: string }) => {
        if (cancelled) return;
        clearPendingInvitationToken();
        const key =
          error.code === 'invitation_expired'
            ? 'workspace.invitationExpired'
            : error.code === 'invitation_revoked'
              ? 'workspace.invitationAlreadyRevoked'
              : error.code === 'invitation_used'
                ? 'workspace.invitationAlreadyUsed'
                : 'workspace.invitationInvalid';
        setErrorMessage(t(key));
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, [invitationHash, t]);

  async function finishAcceptance(registration?: {
    email: string;
    password: string;
  }) {
    if (!token) return;
    setStatus('submitting');
    setErrorMessage('');
    try {
      const response = await backendClient.acceptWorkspaceInvitation(
        token,
        registration,
      );
      beginAuthenticatedSession(
        response.token,
        registration?.email ?? view?.invitation.normalized_email,
      );
      clearPendingInvitationToken();
      const workspaceResult = await bootstrapWorkspaceSession({
        preferredWorkspaceUuid: response.workspace_uuid,
      });
      if (workspaceResult.status !== 'ready') {
        throw new Error('Accepted Workspace could not be initialized');
      }
      setStatus('success');
      toast.success(t('workspace.invitationAccepted'));
      window.setTimeout(() => navigate('/home', { replace: true }), 600);
    } catch (error) {
      const apiError = error as { code?: string; msg?: string };
      if (apiError.code === 'account_exists_login_required') {
        setStatus('ready');
        setErrorMessage(t('workspace.existingAccountLoginRequired'));
        return;
      }
      setStatus('error');
      setErrorMessage(
        apiError.code === 'invitation_email_mismatch'
          ? t('workspace.invitationEmailMismatch')
          : t('workspace.invitationAcceptFailed'),
      );
    }
  }

  function registerAndAccept() {
    if (!view) return;
    if (password.length < 8) {
      setErrorMessage(t('workspace.passwordMinimum'));
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage(t('workspace.passwordMismatch'));
      return;
    }
    void finishAcceptance({
      email: view.invitation.normalized_email,
      password,
    });
  }

  function returnToLogin() {
    clearUserInfo();
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('userEmail');
    }
    navigate('/login', { replace: true });
  }

  const hasLoginToken =
    typeof window !== 'undefined' && Boolean(localStorage.getItem('token'));

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-neutral-900">
      <Card className="w-full max-w-md shadow-lg dark:shadow-white/10">
        <CardHeader>
          <div className="mb-4 flex items-center justify-between">
            <ThemeToggle />
            <LanguageSelector />
          </div>
          <img
            src={langbotIcon}
            alt="LangBot"
            className="mx-auto mb-3 size-14"
          />
          <CardTitle className="text-center">
            {t('workspace.acceptInvitation')}
          </CardTitle>
          <CardDescription className="text-center">
            {view
              ? t('workspace.invitedToWorkspace', {
                  workspace: view.workspace.name,
                })
              : t('workspace.checkingInvitation')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {status === 'loading' && (
            <div className="flex justify-center py-8">
              <Loader2 className="size-6 animate-spin" />
            </div>
          )}

          {status === 'success' && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <CheckCircle2 className="size-9 text-green-600" />
              <p>{t('workspace.invitationAccepted')}</p>
            </div>
          )}

          {status === 'error' && (
            <div className="space-y-4">
              <div className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 size-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
              <Button
                variant="outline"
                className="w-full"
                onClick={returnToLogin}
              >
                {t('workspace.backToLogin')}
              </Button>
            </div>
          )}

          {(status === 'ready' || status === 'submitting') && view && (
            <div className="space-y-4">
              {errorMessage && (
                <div className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <span>{errorMessage}</span>
                </div>
              )}

              {hasLoginToken ? (
                <Button
                  className="w-full"
                  disabled={status === 'submitting'}
                  onClick={() => void finishAcceptance()}
                >
                  {status === 'submitting' && (
                    <Loader2 className="size-4 animate-spin" />
                  )}
                  {t('workspace.acceptAsCurrentAccount')}
                </Button>
              ) : (
                <>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium"
                      htmlFor="invite-email"
                    >
                      {t('common.email')}
                    </label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 size-4 text-muted-foreground" />
                      <Input
                        id="invite-email"
                        value={view.invitation.normalized_email}
                        readOnly
                        className="pl-10"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium"
                      htmlFor="invite-password"
                    >
                      {t('common.password')}
                    </label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-3 size-4 text-muted-foreground" />
                      <Input
                        id="invite-password"
                        type="password"
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        className="pl-10"
                        autoComplete="new-password"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium"
                      htmlFor="invite-password-confirm"
                    >
                      {t('workspace.confirmPassword')}
                    </label>
                    <Input
                      id="invite-password-confirm"
                      type="password"
                      value={confirmPassword}
                      onChange={(event) =>
                        setConfirmPassword(event.target.value)
                      }
                      autoComplete="new-password"
                    />
                  </div>
                  <Button
                    className="w-full"
                    disabled={status === 'submitting'}
                    onClick={registerAndAccept}
                  >
                    {status === 'submitting' && (
                      <Loader2 className="size-4 animate-spin" />
                    )}
                    {t('workspace.registerAndAccept')}
                  </Button>
                  <Button
                    variant="ghost"
                    className="w-full"
                    disabled={status === 'submitting'}
                    onClick={() => navigate('/login?invitation=1')}
                  >
                    {t('workspace.alreadyHaveAccount')}
                  </Button>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
