import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Home, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';

export default function BackendUnavailablePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

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

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button
            variant="outline"
            className="gap-2"
            onClick={() => navigate('/login')}
          >
            <Home className="h-4 w-4" />
            {t('errorPage.backToLogin')}
          </Button>
          <Button className="gap-2" onClick={() => window.location.reload()}>
            <RefreshCw className="h-4 w-4" />
            {t('common.retry')}
          </Button>
        </div>
      </div>
    </div>
  );
}
