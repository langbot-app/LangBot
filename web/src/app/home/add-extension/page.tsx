import MarketPage from '@/app/home/plugins/components/plugin-market/PluginMarketComponent';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Download, PlusIcon, ChevronDownIcon } from 'lucide-react';
import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { httpClient, systemInfo } from '@/app/infra/http/HttpClient';
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

export default function AddExtensionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (!systemInfo?.enable_marketplace) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <p className="text-muted-foreground">{t('plugins.marketplace')}</p>
      </div>
    );
  }

  return <AddExtensionContent />;
}

function AddExtensionContent() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { refreshPlugins } = useSidebarData();
  const {
    addTask,
    setSelectedTaskId,
    registerOnTaskComplete,
    unregisterOnTaskComplete,
  } = usePluginInstallTasks();
  const [modalOpen, setModalOpen] = useState(false);
  const [installInfo, setInstallInfo] = useState<Record<string, string>>({});
  const [installExtensionType, setInstallExtensionType] = useState<'plugin' | 'mcp' | 'skill'>('plugin');
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.ASK_CONFIRM);
  const [installError, setInstallError] = useState<string | null>(null);

  useEffect(() => {
    const onComplete = (_taskId: number, success: boolean) => {
      if (success) {
        toast.success(t('plugins.installSuccess'));
        refreshPlugins();
      }
    };
    registerOnTaskComplete(onComplete);
    return () => {
      unregisterOnTaskComplete(onComplete);
    };
  }, [registerOnTaskComplete, unregisterOnTaskComplete, refreshPlugins, t]);

  const handleInstallPlugin = useCallback(
    async (plugin: PluginV4) => {
      setInstallInfo({
        plugin_author: plugin.author,
        plugin_name: plugin.name,
        plugin_version: plugin.latest_version,
      });
      setInstallExtensionType(plugin.type || 'plugin');
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
      .then((resp: { task_id: number }) => {
        const taskId = resp.task_id;
        const taskKey = `marketplace-${taskId}`;
        addTask({
          taskId,
          pluginName: pluginDisplayName,
          source: 'marketplace',
          extensionType: installExtensionType,
        });
        setSelectedTaskId(taskKey);
        setModalOpen(false);
      })
      .catch((err: { msg?: string }) => {
        setInstallError(err.msg || null);
        setPluginInstallStatus(PluginInstallStatus.ERROR);
      });
  }

  return (
    <>
      <div className="h-full flex flex-col">
        <div className="flex flex-row justify-end items-center px-[0.8rem] pb-4 flex-shrink-0 gap-2">
          <Button
            variant="default"
            className="px-6 py-4 cursor-pointer"
            onClick={() => navigate('/home/mcp?id=new')}
          >
            <PlusIcon className="w-4 h-4" />
            {t('mcp.addMCPServer')}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="default" className="px-6 py-4 cursor-pointer">
                <PlusIcon className="w-4 h-4" />
                {t('skills.addSkill')}
                <ChevronDownIcon className="ml-2 w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate('/home/skills?action=create')}>
                {t('skills.createManually')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/home/skills?action=upload')}>
                {t('skills.uploadZip')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/home/skills?action=github')}>
                {t('skills.importFromGithub')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="default" className="px-6 py-4 cursor-pointer">
                <PlusIcon className="w-4 h-4" />
                {t('plugins.newPlugin')}
                <ChevronDownIcon className="ml-2 w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => navigate('/home/add-plugin?action=github')}>
                {t('plugins.installFromGithub')}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => navigate('/home/add-plugin?action=upload')}>
                {t('plugins.uploadLocal')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex-1 overflow-y-auto">
          <MarketPage installPlugin={handleInstallPlugin} />
        </div>
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