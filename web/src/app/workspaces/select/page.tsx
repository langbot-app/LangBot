import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, ArrowRight, Building2, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import langbotIcon from '@/app/assets/langbot-logo.webp';
import {
  bootstrapWorkspaceSession,
  clearUserInfo,
  selectWorkspace,
  useWorkspaceBootstrap,
} from '@/app/infra/http';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { LanguageSelector } from '@/components/ui/language-selector';
import { ThemeToggle } from '@/components/ui/theme-toggle';

function safeReturnPath(value: string | null): string {
  if (
    value &&
    value.startsWith('/') &&
    !value.startsWith('//') &&
    (value === '/wizard' || value.startsWith('/home'))
  ) {
    return value;
  }
  return '/home';
}

export default function WorkspaceSelectPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const workspaces = useWorkspaceBootstrap();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectingUuid, setSelectingUuid] = useState<string | null>(null);
  const returnTo = safeReturnPath(searchParams.get('returnTo'));

  const loadWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const result = await bootstrapWorkspaceSession({
        requireExplicitSelection: true,
      });
      if (result.status === 'ready') {
        navigate(returnTo, { replace: true });
      } else if (result.status === 'unavailable') {
        setError(true);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [navigate, returnTo]);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  async function handleSelect(workspaceUuid: string) {
    setSelectingUuid(workspaceUuid);
    setError(false);
    try {
      const result = await selectWorkspace(workspaceUuid);
      if (result.status === 'ready') {
        navigate(returnTo, { replace: true });
        return;
      }
      setError(true);
    } catch {
      setError(true);
    } finally {
      setSelectingUuid(null);
    }
  }

  function handleLogout() {
    clearUserInfo();
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    navigate('/login', { replace: true });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-neutral-900">
      <Card className="w-full max-w-xl shadow-lg dark:shadow-white/10">
        <CardHeader>
          <div className="mb-5 flex items-center justify-between">
            <ThemeToggle />
            <LanguageSelector />
          </div>
          <img
            src={langbotIcon}
            alt="LangBot"
            className="mx-auto mb-4 size-16"
          />
          <CardTitle
            className="text-center text-2xl"
            role="heading"
            aria-level={1}
          >
            {t('workspace.selectTitle')}
          </CardTitle>
          <CardDescription className="text-center">
            {t('workspace.selectDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-3">
              {error && (
                <div className="flex items-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                  <AlertCircle className="size-4 shrink-0" />
                  <span>{t('workspace.selectionLoadFailed')}</span>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="ml-auto"
                    onClick={() => void loadWorkspaces()}
                  >
                    {t('common.retry')}
                  </Button>
                </div>
              )}

              {workspaces.map((entry) => {
                const selecting = selectingUuid === entry.workspace.uuid;
                return (
                  <button
                    key={entry.workspace.uuid}
                    type="button"
                    className="flex w-full items-center gap-3 rounded-xl border bg-card p-4 text-left transition-colors hover:border-primary/40 hover:bg-accent disabled:cursor-wait disabled:opacity-70"
                    onClick={() => void handleSelect(entry.workspace.uuid)}
                    disabled={selectingUuid !== null}
                  >
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Building2 className="size-5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {entry.workspace.name}
                      </span>
                      <span className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="secondary">
                          {t(`workspace.roles.${entry.membership.role}`)}
                        </Badge>
                        <span>
                          {entry.workspace.type === 'personal'
                            ? t('workspace.types.personal')
                            : t('workspace.types.team')}
                        </span>
                      </span>
                    </span>
                    {selecting ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <ArrowRight className="size-4 text-muted-foreground" />
                    )}
                  </button>
                );
              })}
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={handleLogout}
              >
                {t('common.logout')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
