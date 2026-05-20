import MarketPage from '@/app/home/plugins/components/plugin-market/PluginMarketComponent';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Download } from 'lucide-react';
import React, { useState, useCallback, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { usePluginInstallTasks } from '@/app/home/plugins/components/plugin-install-task';

enum PluginInstallStatus {
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function MarketplacePage() {
  const { t } = useTranslation();

  if (!systemInfo?.enable_marketplace) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <p className="text-muted-foreground">{t('plugins.marketplace')}</p>
      </div>
    );
  }

  return <MarketplaceContent />;
}

function MarketplaceContent() {
  const { t } = useTranslation();
  const { refreshPlugins } = useSidebarData();
  const {
    addTask,
    setSelectedTaskId,
    registerOnTaskComplete,
    unregisterOnTaskComplete,
  } = usePluginInstallTasks();
  const [modalOpen, setModalOpen] = useState(false);
  const [installInfo, setInstallInfo] = useState<Record<string, string>>({});
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.ASK_CONFIRM);
  const [installError, setInstallError] = useState<string | null>(null);

  async function checkExtensionsLimit(): Promise<boolean> {
    const maxExtensions = systemInfo.limitation?.max_extensions ?? -1;
    if (maxExtensions < 0) return true;
    try {
      const [pluginsResp, mcpResp] = await Promise.all([
        httpClient.getPlugins(),
        httpClient.getMCPServers(),
      ]);
      const total =
        (pluginsResp.plugins?.length ?? 0) + (mcpResp.servers?.length ?? 0);
      if (total >= maxExtensions) {
        toast.error(
          t('limitation.maxExtensionsReached', { max: maxExtensions }),
        );
        return false;
      }
    } catch {
      // If we can't check, let backend handle it
    }
    return true;
  }

  // Register task completion callback for toast and plugin list refresh
  useEffect(() => {
    const onComplete = (_taskId: number, success: boolean, error?: string) => {
      if (success) {
        toast.success(t('plugins.installSuccess'));
        refreshPlugins();
      } else {
        toast.error(error || t('plugins.installFailed'));
      }
    };
    registerOnTaskComplete(onComplete);
    return () => {
      unregisterOnTaskComplete(onComplete);
    };
  }, [registerOnTaskComplete, unregisterOnTaskComplete, refreshPlugins, t]);

  const handleInstallPlugin = useCallback(
    async (plugin: PluginV4) => {
      if (!(await checkExtensionsLimit())) return;
      setInstallInfo({
        plugin_author: plugin.author,
        plugin_name: plugin.name,
        plugin_version: plugin.latest_version,
      });
      setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
      setInstallError(null);
      setModalOpen(true);
    },
    [t],
  );

  function handleModalConfirm() {
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
    const pluginDisplayName = `${installInfo.plugin_author}/${installInfo.plugin_name}`;
    httpClient
      .installPluginFromMarketplace(
        installInfo.plugin_author,
        installInfo.plugin_name,
        installInfo.plugin_version,
      )
      .then((resp) => {
        const taskId = resp.task_id;
        const taskKey = `marketplace-${taskId}`;
        addTask({
          taskId,
          pluginName: pluginDisplayName,
          source: 'marketplace',
        });
        setSelectedTaskId(taskKey);
        setModalOpen(false);
      })
      .catch((err) => {
        setInstallError(err.msg);
        setPluginInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  return (
    <>
      <div className="h-full overflow-y-auto">
        <MarketPage installPlugin={handleInstallPlugin} />
      </div>

      <Dialog
        open={modalOpen}
        onOpenChange={(open) => {
          setModalOpen(open);
          if (!open) {
            setInstallError(null);
          }
        }}
      >
        <DialogContent className="w-[500px] max-h-[80vh] p-6 bg-white dark:bg-[#1a1a1e] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <Download className="size-6" />
              <span>{t('plugins.installPlugin')}</span>
            </DialogTitle>
          </DialogHeader>

          {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
            <div className="mt-4">
              <p className="mb-2">
                {t('plugins.askConfirm', {
                  name: installInfo.plugin_name,
                  version: installInfo.plugin_version,
                })}
              </p>
            </div>
          )}

          {pluginInstallStatus === PluginInstallStatus.INSTALLING && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installing')}</p>
            </div>
          )}

          {pluginInstallStatus === PluginInstallStatus.ERROR && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.installFailed')}</p>
              <p className="mb-2 text-red-500">{installError}</p>
            </div>
          )}

          <DialogFooter>
            {pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  {t('common.cancel')}
                </Button>
                <Button onClick={handleModalConfirm}>
                  {t('common.confirm')}
                </Button>
              </>
            )}
            {pluginInstallStatus === PluginInstallStatus.ERROR && (
              <Button variant="default" onClick={() => setModalOpen(false)}>
                {t('common.close')}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
