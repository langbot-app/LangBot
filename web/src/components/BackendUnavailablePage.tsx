import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Home, Loader2, RefreshCw } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { initializeSystemInfo, systemInfo } from '@/app/infra/http';

const RETURN_TO_STORAGE_KEY = 'langbot_backend_unavailable_return_to';

type BackendUnavailableLocationState = {
  from?: string;
};

export default function BackendUnavailablePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  async function handleRetry() {
    setChecking(true);
    setRetryError(null);

    try {
      await initializeSystemInfo({ throwOnError: true });
      const state = location.state as BackendUnavailableLocationState | null;
      const storedReturnTo = sessionStorage.getItem(RETURN_TO_STORAGE_KEY);
      const returnTo = state?.from || storedReturnTo || '/home';
      sessionStorage.removeItem(RETURN_TO_STORAGE_KEY);

      if (systemInfo.wizard_status === 'none') {
        navigate('/wizard', { replace: true });
        return;
      }

      navigate(returnTo === '/backend-unavailable' ? '/home' : returnTo, {
        replace: true,
      });
    } catch (error) {
      setRetryError(
        error instanceof Error ? error.message : t('errorPage.retryFailed'),
      );
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="h-8 w-8 text-destructive" />
        </div>

        <p className="mb-2 text-sm font-medium text-destructive">
          {t('errorPage.backendUnavailableStatus')}
        </p>

        <h1 className="text-2xl font-semibold text-foreground">
          {t('common.loginLoadError')}
        </h1>

        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          {t('common.loginLoadErrorDesc')}
        </p>

        {retryError ? (
          <p className="mt-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {t('errorPage.retryFailed')}
          </p>
        ) : null}

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => navigate('/login')}
          >
            <Home className="h-4 w-4" />
            {t('errorPage.backToLogin')}
          </Button>
          <Button className="gap-2" onClick={handleRetry} disabled={checking}>
            {checking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {checking ? t('errorPage.retrying') : t('common.retry')}
          </Button>
        </div>
      </div>
    </div>
  );
}
