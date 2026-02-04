'use client';

import { useEffect, useState, useCallback, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { httpClient } from '@/app/infra/http/HttpClient';
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

function SpaceOAuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useTranslation();

  const [status, setStatus] = useState<
    'loading' | 'confirm' | 'success' | 'error'
  >('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [isBindMode, setIsBindMode] = useState(false);
  const [code, setCode] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [localEmail, setLocalEmail] = useState<string>('');

  const handleOAuthCallback = useCallback(
    async (authCode: string) => {
      try {
        const response = await httpClient.exchangeSpaceOAuthCode(authCode);
        localStorage.setItem('token', response.token);
        if (response.user) {
          localStorage.setItem('userEmail', response.user);
        }
        setStatus('success');
        toast.success(t('common.spaceLoginSuccess'));
        setTimeout(() => {
          router.push('/home');
        }, 1000);
      } catch (err) {
        setStatus('error');
        const errorObj = err as { msg?: string };
        const errMsg = (errorObj?.msg || '').toLowerCase();
        if (errMsg.includes('account email mismatch')) {
          setErrorMessage(t('account.spaceEmailMismatch'));
        } else {
          setErrorMessage(t('common.spaceLoginFailed'));
        }
      }
    },
    [router, t],
  );

  const [bindState, setBindState] = useState<string | null>(null);

  const handleBindAccount = useCallback(
    async (authCode: string, state: string) => {
      setIsProcessing(true);
      try {
        const response = await httpClient.bindSpaceAccount(authCode, state);
        localStorage.setItem('token', response.token);
        if (response.user) {
          localStorage.setItem('userEmail', response.user);
        }
        setStatus('success');
        toast.success(t('account.bindSpaceSuccess'));
        setTimeout(() => {
          router.push('/home');
        }, 1000);
      } catch (err) {
        setStatus('error');
        const errorObj = err as { msg?: string };
        const errMsg = (errorObj?.msg || '').toLowerCase();
        if (errMsg.includes('account email mismatch')) {
          setErrorMessage(t('account.spaceEmailMismatch'));
        } else {
          setErrorMessage(t('account.bindSpaceFailed'));
        }
      } finally {
        setIsProcessing(false);
      }
    },
    [router, t],
  );

  useEffect(() => {
    const authCode = searchParams.get('code');
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    const mode = searchParams.get('mode');
    const state = searchParams.get('state');

    if (error) {
      setStatus('error');
      setErrorMessage(
        errorDescription || error || t('common.spaceLoginFailed'),
      );
      return;
    }

    if (!authCode) {
      setStatus('error');
      setErrorMessage(t('common.spaceLoginNoCode'));
      return;
    }

    setCode(authCode);

    if (mode === 'bind') {
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
    } else {
      // Normal login/register mode
      handleOAuthCallback(authCode);
    }
  }, [searchParams, handleOAuthCallback, t]);

  const handleConfirmBind = () => {
    if (code && bindState) {
      handleBindAccount(code, bindState);
    }
  };

  const handleCancelBind = () => {
    router.push('/home');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-neutral-900">
      <Card className="w-[400px] shadow-lg dark:shadow-white/10">
        <CardHeader className="text-center">
          <img
            src={langbotIcon.src}
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
              (isBindMode
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
                onClick={() => router.push(isBindMode ? '/home' : '/login')}
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
