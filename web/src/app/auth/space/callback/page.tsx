import { useEffect, useState, useCallback, Suspense, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  beginAuthenticatedSession,
  beginSupportAdminSession,
  bootstrapWorkspaceSession,
  clearPendingInvitationToken,
  getPendingInvitationToken,
} from '@/app/infra/http';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import langbotIcon from '@/app/assets/langbot-logo.webp';

type SpaceOAuthLoginResult = {
  token: string;
  user?: string;
  workspace_uuid?: string;
  principal_type?: 'account' | 'support_admin';
  actor_account_uuid?: string;
};

const pendingSpaceOAuthLogins = new Map<
  string,
  Promise<SpaceOAuthLoginResult>
>();

function getOrCreateSpaceOAuthLoginPromise(
  authCode: string,
  state: string,
  redirectUri: string,
  workspaceUuid?: string,
  launchAssertion?: string,
): Promise<SpaceOAuthLoginResult> {
  const requestKey = `${authCode}:${state}:${redirectUri}:${workspaceUuid ?? ''}:${launchAssertion ?? ''}`;
  const pendingRequest = pendingSpaceOAuthLogins.get(requestKey);
  if (pendingRequest) {
    return pendingRequest;
  }

  const requestPromise = httpClient
    .exchangeSpaceOAuthCode(
      authCode,
      state,
      redirectUri,
      workspaceUuid,
      launchAssertion,
    )
    .finally(() => {
      pendingSpaceOAuthLogins.delete(requestKey);
    });

  pendingSpaceOAuthLogins.set(requestKey, requestPromise);
  return requestPromise;
}

function SpaceOAuthCallbackContent() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const isMountedRef = useRef(true);
  const directLaunchFragmentRef = useRef<{
    workspaceUuid: string | null;
    launchAssertion: string | null;
  } | null>(null);

  const [status, setStatus] = useState<
    'loading' | 'confirm' | 'success' | 'error'
  >('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [terminalErrorCode, setTerminalErrorCode] = useState<
    'space_account_not_registered' | 'space_account_binding_required' | null
  >(null);
  const [isBindMode, setIsBindMode] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [localEmail, setLocalEmail] = useState<string>('');

  const handleOAuthCallback = useCallback(
    async (
      authCode: string,
      state: string,
      workspaceUuid?: string,
      launchAssertion?: string,
    ) => {
      try {
        const response = await getOrCreateSpaceOAuthLoginPromise(
          authCode,
          state,
          `${window.location.origin}/auth/space/callback`,
          workspaceUuid,
          launchAssertion,
        );
        if (!isMountedRef.current) {
          return;
        }

        if (response.principal_type === 'support_admin') {
          if (!response.workspace_uuid) {
            throw new Error('Support admin launch did not include a Workspace');
          }
          beginSupportAdminSession(response.token, response.workspace_uuid);
          await bootstrapWorkspaceSession();
          navigate('/home', { replace: true });
          return;
        }

        beginAuthenticatedSession(response.token, response.user);
        const invitationToken = getPendingInvitationToken();
        if (invitationToken) {
          let invitation;
          try {
            invitation =
              await httpClient.acceptWorkspaceInvitation(invitationToken);
          } catch (error) {
            const code = (error as { code?: string }).code;
            const path = code
              ? `/invitations/accept?error=${encodeURIComponent(code)}`
              : '/invitations/accept';
            navigate(path, { replace: true });
            return;
          }

          beginAuthenticatedSession(invitation.token, response.user);
          clearPendingInvitationToken();
          const workspaceResult = await bootstrapWorkspaceSession({
            preferredWorkspaceUuid: invitation.workspace_uuid,
          });
          if (workspaceResult.status === 'unavailable') {
            navigate('/workspace-unavailable', { replace: true });
            return;
          }
          navigate('/home', { replace: true });
          return;
        }
        const workspaceResult = await bootstrapWorkspaceSession({
          preferredWorkspaceUuid: response.workspace_uuid,
        });
        if (workspaceResult.status === 'unavailable') {
          throw new Error('No Workspace is available for this Account');
        }
        if (response.workspace_uuid) {
          navigate('/home', { replace: true });
          return;
        }
        setStatus('success');
        toast.success(t('common.spaceLoginSuccess'));

        // If wizard state exists, redirect back to wizard instead of home
        const wizardState = localStorage.getItem('langbot_wizard_state');
        const destination = wizardState ? '/wizard' : '/home';
        const redirectTo =
          workspaceResult.status === 'selection-required'
            ? `/workspaces/select?returnTo=${encodeURIComponent(destination)}`
            : destination;
        setTimeout(() => {
          navigate(redirectTo);
        }, 1000);
      } catch (err) {
        if (!isMountedRef.current) {
          return;
        }

        setStatus('error');
        const errorObj = err as { code?: string; msg?: string };
        if (
          errorObj.code === 'space_account_not_registered' ||
          errorObj.code === 'space_account_binding_required'
        ) {
          setTerminalErrorCode(errorObj.code);
          setErrorMessage(t(`account.${errorObj.code}`));
          return;
        }
        const errMsg = (errorObj?.msg || '').toLowerCase();
        if (errMsg.includes('account email mismatch')) {
          setErrorMessage(t('account.spaceEmailMismatch'));
        } else {
          setErrorMessage(t('common.spaceLoginFailed'));
        }
      }
    },
    [navigate, t],
  );

  const [bindState, setBindState] = useState<string | null>(null);

  const handleBindAccount = useCallback(
    async (authCode: string, state: string) => {
      setIsProcessing(true);
      try {
        const response = await httpClient.bindSpaceAccount(
          authCode,
          state,
          `${window.location.origin}/auth/space/callback?mode=bind`,
        );
        if (!isMountedRef.current) {
          return;
        }

        beginAuthenticatedSession(response.token, response.user);
        const workspaceResult = await bootstrapWorkspaceSession();
        if (workspaceResult.status === 'unavailable') {
          throw new Error('No Workspace is available for this Account');
        }
        setStatus('success');
        toast.success(t('account.bindSpaceSuccess'));
        const redirectTo =
          workspaceResult.status === 'selection-required'
            ? '/workspaces/select?returnTo=%2Fhome'
            : '/home';
        setTimeout(() => {
          navigate(redirectTo);
        }, 1000);
      } catch (err) {
        if (!isMountedRef.current) {
          return;
        }

        setStatus('error');
        const errorObj = err as { code?: string; msg?: string };
        if (errorObj.code === 'space_account_email_mismatch') {
          setErrorMessage(t('account.spaceEmailMismatch'));
          return;
        }
        const errMsg = (errorObj?.msg || '').toLowerCase();
        if (errMsg.includes('account email mismatch')) {
          setErrorMessage(t('account.spaceEmailMismatch'));
        } else {
          setErrorMessage(t('account.bindSpaceFailed'));
        }
      } finally {
        if (isMountedRef.current) {
          setIsProcessing(false);
        }
      }
    },
    [navigate, t],
  );

  useEffect(() => {
    isMountedRef.current = true;

    const authCode = searchParams.get('code');
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    const mode = searchParams.get('mode');
    const state = searchParams.get('state');
    if (directLaunchFragmentRef.current === null) {
      const fragmentParams = new URLSearchParams(
        window.location.hash.startsWith('#')
          ? window.location.hash.slice(1)
          : window.location.hash,
      );
      directLaunchFragmentRef.current = {
        workspaceUuid: fragmentParams.get('workspace_uuid'),
        launchAssertion: fragmentParams.get('launch_assertion'),
      };
      if (window.location.hash) {
        window.history.replaceState(
          null,
          '',
          `${window.location.pathname}${window.location.search}`,
        );
      }
    }
    const workspaceUuid =
      directLaunchFragmentRef.current.workspaceUuid ??
      searchParams.get('workspace_uuid');
    const launchAssertion = directLaunchFragmentRef.current.launchAssertion;

    if (error) {
      setStatus('error');
      setErrorMessage(
        errorDescription || error || t('common.spaceLoginFailed'),
      );
      return;
    }

    if (mode === 'bind') {
      if (!authCode) {
        setStatus('error');
        setErrorMessage(t('common.spaceLoginNoCode'));
        return;
      }
      setCode(authCode);
      // Bind mode - verify state (token) exists
      if (!state) {
        setStatus('error');
        setErrorMessage(t('account.bindSpaceInvalidState'));
        return;
      }
      setBindState(state);
      setIsBindMode(true);
      setLocalEmail(localStorage.getItem('userEmail') || '');
      setStatus('confirm');
    } else if (workspaceUuid || launchAssertion) {
      if (!workspaceUuid || !launchAssertion) {
        setStatus('error');
        setErrorMessage(t('common.spaceLoginFailed'));
        return;
      }
      handleOAuthCallback(
        authCode ?? '',
        state ?? '',
        workspaceUuid,
        launchAssertion,
      );
    } else {
      if (!authCode) {
        setStatus('error');
        setErrorMessage(t('common.spaceLoginNoCode'));
        return;
      }
      setCode(authCode);
      if (!state) {
        setStatus('error');
        setErrorMessage(t('common.spaceLoginFailed'));
        return;
      }
      handleOAuthCallback(authCode, state);
    }
    return () => {
      isMountedRef.current = false;
    };
  }, [searchParams, handleOAuthCallback, t]);

  const handleConfirmBind = () => {
    if (code && bindState) {
      handleBindAccount(code, bindState);
    }
  };

  const handleCancelBind = () => {
    navigate('/home');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
      <Card className="w-[400px] shadow-lg dark:shadow-white/10">
        <CardHeader className="text-center">
          <img
            src={langbotIcon}
            alt="LangBot"
            className="w-16 h-16 mb-4 mx-auto"
          />
          <CardTitle className="text-xl">
            {status === 'loading' && t('common.spaceLoginProcessing')}
            {status === 'confirm' && t('account.bindSpaceConfirmTitle')}
            {status === 'success' &&
              (isBindMode
                ? t('account.bindSpaceSuccess')
                : t('common.spaceLoginSuccess'))}
            {status === 'error' &&
              (terminalErrorCode
                ? t(`account.${terminalErrorCode}Title`)
                : isBindMode
                  ? t('account.bindSpaceFailed')
                  : t('common.spaceLoginError'))}
          </CardTitle>
          <CardDescription>
            {status === 'loading' &&
              t('common.spaceLoginProcessingDescription')}
            {status === 'confirm' && t('account.bindSpaceConfirmDescription')}
            {status === 'success' && t('common.spaceLoginSuccessDescription')}
            {status === 'error' && errorMessage}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center space-y-4">
          {status === 'loading' && <LoadingSpinner size="lg" text="" />}
          {status === 'confirm' && (
            <>
              <AlertTriangle className="h-12 w-12 text-yellow-500" />
              <p className="text-sm text-center text-muted-foreground px-4">
                {t('account.bindSpaceWarning', {
                  localEmail: localEmail || '-',
                })}
              </p>
              <div className="flex gap-3 w-full">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={handleCancelBind}
                  disabled={isProcessing}
                >
                  {t('common.cancel')}
                </Button>
                <Button
                  className="flex-1"
                  onClick={handleConfirmBind}
                  disabled={isProcessing}
                >
                  {isProcessing ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  {t('common.confirm')}
                </Button>
              </div>
            </>
          )}
          {status === 'success' && (
            <CheckCircle2 className="h-12 w-12 text-green-500" />
          )}
          {status === 'error' && (
            <>
              <AlertCircle className="h-12 w-12 text-red-500" />
              <Button
                onClick={() => navigate(isBindMode ? '/home' : '/login')}
                className="w-full mt-4"
              >
                {isBindMode ? t('common.backToHome') : t('common.backToLogin')}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
      <Card className="w-[400px] shadow-lg dark:shadow-white/10">
        <CardContent className="flex flex-col items-center py-12">
          <LoadingSpinner size="lg" text="" />
        </CardContent>
      </Card>
    </div>
  );
}

export default function SpaceOAuthCallback() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <SpaceOAuthCallbackContent />
    </Suspense>
  );
}
