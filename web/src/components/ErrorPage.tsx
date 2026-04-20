import {
  useRouteError,
  isRouteErrorResponse,
  useNavigate,
} from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { AlertCircle } from 'lucide-react';

export default function ErrorPage() {
  const error = useRouteError();
  const navigate = useNavigate();
  const { t } = useTranslation();

  let status = 500;
  let title = t('errorPage.unexpectedError');
  let description = t('errorPage.unexpectedErrorDescription');

  if (isRouteErrorResponse(error)) {
    status = error.status;
    if (status === 404) {
      title = t('errorPage.notFound');
      description = t('errorPage.notFoundDescription');
    } else {
      description = error.statusText || description;
    }
  } else if (error instanceof Error) {
    description = error.message;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="mx-auto flex max-w-md flex-col items-center text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 mb-6">
          <AlertCircle className="h-8 w-8 text-destructive" />
        </div>

        <p className="text-5xl font-bold tracking-tight text-foreground mb-2">
          {status}
        </p>

        <h1 className="text-xl font-semibold text-foreground mt-2">{title}</h1>

        <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>

        <div className="mt-8 flex gap-3">
          <Button variant="outline" onClick={() => navigate(-1)}>
            {t('errorPage.goBack')}
          </Button>
          <Button onClick={() => navigate('/home/monitoring')}>
            {t('errorPage.backToHome')}
          </Button>
        </div>
      </div>
    </div>
  );
}
