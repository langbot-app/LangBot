import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckCircle2,
  ChevronDown,
  Loader2,
  Puzzle,
  XCircle,
} from 'lucide-react';
import type { MigrationInstallation } from '@/app/infra/entities/api/pipeline-migration';
import type { PluginV4 } from '@/app/infra/entities/plugin';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';

const stageKeys: Record<string, string> = {
  checking: 'pipelineMigration.checkingPlugin',
  downloading: 'plugins.installProgress.downloading',
  validating: 'plugins.installProgress.validating',
  preparing: 'pipelineMigration.preparingPlugin',
  installing_deps: 'plugins.installProgress.installingDeps',
  activating: 'plugins.installProgress.initializing',
  refreshing: 'plugins.installProgress.activating',
  done: 'plugins.installProgress.completed',
};

function bytes(value: number) {
  return value < 1024 * 1024
    ? `${(value / 1024).toFixed(1)} KB`
    : `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function InstallationPluginIdentity({ item }: { item: MigrationInstallation }) {
  const { t } = useTranslation();
  const [plugin, setPlugin] = useState<PluginV4 | null>(null);

  useEffect(() => {
    let active = true;
    void getCloudServiceClientSync()
      .getPluginDetail(item.author, item.name)
      .then(({ plugin }) => {
        if (active) setPlugin(plugin);
      })
      .catch(() => {
        // Marketplace metadata is optional and must not interrupt installation.
      });
    return () => {
      active = false;
    };
  }, [item.author, item.name]);

  const name = (plugin?.label && extractI18nObject(plugin.label)) || item.name;
  const description =
    (plugin?.description && extractI18nObject(plugin.description)) ||
    t('market.noDescription');
  const iconURL = getCloudServiceClientSync().resolveMarketplaceIconURL(
    'plugin',
    item.author,
    item.name,
    plugin?.icon,
  );

  return (
    <div className="flex items-start gap-3">
      <Avatar className="size-10 rounded-lg">
        <AvatarImage src={iconURL} alt={name} className="object-contain" />
        <AvatarFallback className="rounded-lg">
          <Puzzle className="size-5 text-muted-foreground" />
        </AvatarFallback>
      </Avatar>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2">
          <span
            className="min-w-0 flex-1 truncate text-sm font-medium"
            title={name}
          >
            {name}
          </span>
          <Badge variant="secondary" className="shrink-0">
            {item.version}
          </Badge>
        </div>
        <p
          className="line-clamp-2 break-words text-xs text-muted-foreground"
          title={description}
        >
          {description}
        </p>
      </div>
    </div>
  );
}

export default function MigrationInstallProgress({
  installations,
}: {
  installations: MigrationInstallation[];
}) {
  const { t } = useTranslation();
  if (!installations.length) return null;
  return (
    <div className="space-y-2" data-testid="migration-installations">
      {installations.map((item) => {
        const failed = item.status === 'failed';
        const done = item.status === 'completed';
        const Icon = failed ? XCircle : done ? CheckCircle2 : Loader2;
        const label = t(
          stageKeys[item.stage] ?? 'pipelineMigration.installing',
        );
        const end = item.finished_at ?? item.updated_at;
        const seconds = (start: number, finish: number) =>
          `${Math.max(0, finish - start).toFixed(1)} s`;
        return (
          <Collapsible
            key={`${item.author}/${item.name}/${item.version}`}
            className="rounded-md border p-3"
          >
            <InstallationPluginIdentity item={item} />
            <div className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Icon
                  className={`size-3.5 shrink-0 ${failed ? 'text-destructive' : !done ? 'animate-spin' : 'text-green-600'}`}
                />
                {failed ? t('plugins.installProgress.failed') : label}
              </span>
              <span className="tabular-nums">
                {seconds(item.started_at, end)}
              </span>
            </div>
            {!failed && !done && (
              <Progress
                className="mt-2 h-1.5"
                value={item.progress_percent ?? 0}
                aria-label={t('pipelineMigration.stageProgress')}
              />
            )}
            {failed && (
              <p className="mt-2 text-xs text-destructive">
                {t(
                  item.code === 'plugin_runtime_unavailable'
                    ? 'pipelineMigration.notices.runtimeUnavailable'
                    : `pipelineMigration.installErrors.${item.code}`,
                  { defaultValue: t('pipelineMigration.installFailed') },
                )}
              </p>
            )}
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="group mt-1 h-7 px-0 text-xs text-muted-foreground hover:bg-transparent"
              >
                <ChevronDown className="size-3 group-data-[state=open]:rotate-180" />
                {t('pipelineMigration.installDetails')}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-1 text-xs">
              <p className="break-all text-muted-foreground">
                {item.author}/{item.name}
              </p>
              {item.steps.map((step, index) => (
                <div key={index} className="flex justify-between gap-2">
                  <span
                    className={
                      failed && index === item.steps.length - 1
                        ? 'text-destructive'
                        : ''
                    }
                  >
                    {t(stageKeys[step.stage] ?? 'pipelineMigration.installing')}
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {seconds(step.started_at, step.finished_at ?? end)}
                  </span>
                </div>
              ))}
              {item.download_current !== undefined && (
                <p className="text-muted-foreground">
                  {t('pipelineMigration.downloaded', {
                    size: bytes(item.download_current),
                  })}
                  {item.download_total
                    ? ` / ${bytes(item.download_total)}`
                    : ''}
                  {item.status === 'installing' &&
                  item.stage === 'downloading' &&
                  item.download_speed
                    ? ` · ${bytes(item.download_speed)}/s`
                    : ''}
                </p>
              )}
              {item.deps_total !== undefined && (
                <p className="text-muted-foreground">
                  {t('plugins.installProgress.depsInfo', {
                    count: item.deps_total,
                  })}
                </p>
              )}
            </CollapsibleContent>
          </Collapsible>
        );
      })}
    </div>
  );
}
