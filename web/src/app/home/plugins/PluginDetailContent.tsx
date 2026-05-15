import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PluginForm from '@/app/home/plugins/components/plugin-installed/plugin-form/PluginForm';
import PluginReadme from '@/app/home/plugins/components/plugin-installed/plugin-readme/PluginReadme';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Plugin } from '@/app/infra/entities/plugin';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useAsyncTask, AsyncTaskStatus } from '@/hooks/useAsyncTask';
import { Bug, Puzzle, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Plugin detail page content.
 * The `id` prop is the composite key "author/name".
 */
export default function PluginDetailContent({ id }: { id: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { plugins, setDetailEntityName, refreshPlugins } = useSidebarData();
  const [pluginInfo, setPluginInfo] = useState<Plugin | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteData, setDeleteData] = useState(false);

  // Parse "author/name" composite key
  const slashIndex = id.indexOf('/');
  const pluginAuthor = slashIndex >= 0 ? id.substring(0, slashIndex) : '';
  const pluginName = slashIndex >= 0 ? id.substring(slashIndex + 1) : id;

  const plugin = plugins.find((p) => p.id === id);
  const title =
    pluginInfo?.manifest.manifest.metadata.label &&
    extractI18nObject(pluginInfo.manifest.manifest.metadata.label)
      ? extractI18nObject(pluginInfo.manifest.manifest.metadata.label)
      : plugin?.name || `${pluginAuthor}/${pluginName}`;
  const description = pluginInfo?.manifest.manifest.metadata.description
    ? extractI18nObject(pluginInfo.manifest.manifest.metadata.description)
    : plugin?.description;

  const asyncTask = useAsyncTask({
    onSuccess: () => {
      toast.success(t('plugins.deleteSuccess'));
      setShowDeleteConfirm(false);
      void refreshPlugins();
      navigate('/home/extensions');
    },
  });

  // Set breadcrumb entity name
  useEffect(() => {
    setDetailEntityName(plugin?.name ?? `${pluginAuthor}/${pluginName}`);
    return () => setDetailEntityName(null);
  }, [plugin, pluginAuthor, pluginName, setDetailEntityName]);

  useEffect(() => {
    let cancelled = false;
    httpClient.getPlugin(pluginAuthor, pluginName).then((res) => {
      if (!cancelled) {
        setPluginInfo(res.plugin);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [pluginAuthor, pluginName]);

  function handleFormSubmit(timeout?: number) {
    if (timeout) {
      setTimeout(() => {
        refreshPlugins();
      }, timeout);
    } else {
      refreshPlugins();
    }
  }

  function executeDelete() {
    httpClient
      .removePlugin(pluginAuthor, pluginName, deleteData)
      .then((res) => {
        asyncTask.startTask(res.task_id);
      })
      .catch((error) => {
        toast.error(t('plugins.deleteError') + error.message);
      });
  }

  const sourceBadge = plugin?.debug ? (
    <Badge
      variant="outline"
      className="shrink-0 border-orange-400 text-[0.7rem] text-orange-400"
    >
      <Bug className="size-3.5" />
      {t('plugins.debugging')}
    </Badge>
  ) : plugin?.installSource === 'github' ? (
    <Badge
      variant="outline"
      className="shrink-0 border-blue-400 text-[0.7rem] text-blue-400"
    >
      {t('plugins.fromGithub')}
    </Badge>
  ) : plugin?.installSource === 'local' ? (
    <Badge
      variant="outline"
      className="shrink-0 border-green-400 text-[0.7rem] text-green-400"
    >
      {t('plugins.fromLocal')}
    </Badge>
  ) : plugin?.installSource === 'marketplace' ? (
    <Badge
      variant="outline"
      className="shrink-0 border-purple-400 text-[0.7rem] text-purple-400"
    >
      {t('plugins.fromMarketplace')}
    </Badge>
  ) : null;

  const componentBadges = pluginInfo && (
    <PluginComponentList
      components={pluginInfo.components.reduce<Record<string, number>>(
        (acc, component) => {
          const kind = component.manifest.manifest.kind;
          acc[kind] = (acc[kind] ?? 0) + 1;
          return acc;
        },
        {},
      )}
      showComponentName
      showTitle={false}
      useBadge
      t={t}
    />
  );

  const dangerZone = (
    <Card className="border-destructive/50">
      <CardHeader>
        <CardTitle className="text-destructive">
          {t('plugins.dangerZone')}
        </CardTitle>
        <CardDescription>{t('plugins.dangerZoneDescription')}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-sm font-medium">{t('plugins.deletePlugin')}</p>
            <p className="text-sm text-muted-foreground">
              {t('plugins.confirmDeletePlugin', {
                author: pluginAuthor,
                name: pluginName,
              })}
            </p>
          </div>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0"
          >
            <Trash2 className="mr-1.5 size-4" />
            {t('common.delete')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex shrink-0 flex-col gap-2 pb-4">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <h1 className="truncate text-xl font-semibold">{title}</h1>
            <Badge variant="outline" className="shrink-0 text-[0.7rem]">
              <Puzzle className="size-3.5" />
              {t('market.typePlugin')}
            </Badge>
            {sourceBadge}
            {componentBadges}
          </div>
          {description && (
            <p className="line-clamp-2 text-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>

        <div className="flex min-h-0 max-w-full flex-1 flex-col gap-6 overflow-y-auto md:flex-row md:overflow-hidden">
          <div className="space-y-4 pb-6 md:min-h-0 md:w-[380px] md:flex-shrink-0 md:overflow-y-auto md:overflow-x-hidden xl:w-[420px]">
            <PluginForm
              pluginAuthor={pluginAuthor}
              pluginName={pluginName}
              onFormSubmit={handleFormSubmit}
            />
            {dangerZone}
          </div>
          <div className="hidden w-px shrink-0 bg-border md:block" />
          <div className="min-w-0 flex-1 pb-6 md:min-h-0 md:overflow-y-auto md:overflow-x-hidden">
            <PluginReadme pluginAuthor={pluginAuthor} pluginName={pluginName} />
          </div>
        </div>
      </div>

      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('plugins.deleteConfirm')}</DialogTitle>
            <DialogDescription>
              {asyncTask.status === AsyncTaskStatus.RUNNING
                ? t('plugins.deleting')
                : t('plugins.confirmDeletePlugin', {
                    author: pluginAuthor,
                    name: pluginName,
                  })}
            </DialogDescription>
          </DialogHeader>
          {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
            <div className="flex items-center space-x-2">
              <Checkbox
                id="delete-plugin-data"
                checked={deleteData}
                onCheckedChange={(checked) => setDeleteData(checked === true)}
              />
              <label
                htmlFor="delete-plugin-data"
                className="cursor-pointer text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {t('plugins.deleteDataCheckbox')}
              </label>
            </div>
          )}
          {asyncTask.status === AsyncTaskStatus.ERROR && (
            <div className="text-sm text-destructive">{asyncTask.error}</div>
          )}
          <DialogFooter>
            {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
              <Button
                variant="outline"
                onClick={() => setShowDeleteConfirm(false)}
              >
                {t('common.cancel')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
              <Button variant="destructive" onClick={executeDelete}>
                {t('common.confirmDelete')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.RUNNING && (
              <Button variant="destructive" disabled>
                {t('plugins.deleting')}
              </Button>
            )}
            {asyncTask.status === AsyncTaskStatus.ERROR && (
              <Button
                variant="outline"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  asyncTask.reset();
                }}
              >
                {t('plugins.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
