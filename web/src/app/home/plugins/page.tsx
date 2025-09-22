'use client';
import PluginInstalledComponent, {
  PluginInstalledComponentRef,
} from '@/app/home/plugins/plugin-installed/PluginInstalledComponent';
import MarketPage from '@/app/home/plugins/plugin-market/PluginMarketComponent';
// import PluginSortDialog from '@/app/home/plugins/plugin-sort/PluginSortDialog';
import styles from './plugins.module.css';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  PlusIcon,
  ChevronDownIcon,
  UploadIcon,
  StoreIcon,
  Download,
  Power,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { useState, useRef, useCallback, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { ApiRespPluginSystemStatus } from '@/app/infra/entities/api';

enum PluginInstallStatus {
  WAIT_INPUT = 'wait_input',
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [modalOpen, setModalOpen] = useState(false);
  // const [sortModalOpen, setSortModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('installed');
  const [installSource, setInstallSource] = useState<string>('local');
  const [installInfo, setInstallInfo] = useState<Record<string, any>>({}); // eslint-disable-line @typescript-eslint/no-explicit-any
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const [installError, setInstallError] = useState<string | null>(null);
  const [githubURL, setGithubURL] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchPluginSystemStatus = async () => {
      try {
        setStatusLoading(true);
        const status = await httpClient.getPluginSystemStatus();
        setPluginSystemStatus(status);
      } catch (error) {
        console.error('Failed to fetch plugin system status:', error);
        toast.error(t('plugins.failedToGetStatus'));
      } finally {
        setStatusLoading(false);
      }
    };

    fetchPluginSystemStatus();
  }, [t]);

  function watchTask(taskId: number) {
    let alreadySuccess = false;
    console.log('taskId:', taskId);

    // 每秒拉取一次任务状态
    const interval = setInterval(() => {
      httpClient.getAsyncTask(taskId).then((resp) => {
        console.log('task status:', resp);
        if (resp.runtime.done) {
          clearInterval(interval);
          if (resp.runtime.exception) {
            setInstallError(resp.runtime.exception);
            setPluginInstallStatus(PluginInstallStatus.ERROR);
          } else {
            // success
            if (!alreadySuccess) {
              toast.success(t('plugins.installSuccess'));
              alreadySuccess = true;
            }
            setGithubURL('');
            setModalOpen(false);
            pluginInstalledRef.current?.refreshPluginList();
          }
        }
      });
    }, 1000);
  }

  function handleModalConfirm() {
    installPlugin(installSource, installInfo as Record<string, any>); // eslint-disable-line @typescript-eslint/no-explicit-any
  }

  function installPlugin(
    installSource: string,
    installInfo: Record<string, any>, // eslint-disable-line @typescript-eslint/no-explicit-any
  ) {
    setPluginInstallStatus(PluginInstallStatus.INSTALLING);
    if (installSource === 'github') {
      httpClient
        .installPluginFromGithub(installInfo.url)
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        })
        .catch((err) => {
          console.log('error when install plugin:', err);
          setInstallError(err.message);
          setPluginInstallStatus(PluginInstallStatus.ERROR);
        });
    } else if (installSource === 'local') {
      httpClient
        .installPluginFromLocal(installInfo.file)
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        })
        .catch((err) => {
          console.log('error when install plugin:', err);
          setInstallError(err.message);
          setPluginInstallStatus(PluginInstallStatus.ERROR);
        });
    } else if (installSource === 'marketplace') {
      httpClient
        .installPluginFromMarketplace(
          installInfo.plugin_author,
          installInfo.plugin_name,
          installInfo.plugin_version,
        )
        .then((resp) => {
          const taskId = resp.task_id;
          watchTask(taskId);
        });
    }
  }

  const validateFileType = (file: File): boolean => {
    const allowedExtensions = ['.lbpkg', '.zip'];
    const fileName = file.name.toLowerCase();
    return allowedExtensions.some((ext) => fileName.endsWith(ext));
  };

  const uploadPluginFile = useCallback(
    async (file: File) => {
      if (!pluginSystemStatus?.is_enable || !pluginSystemStatus?.is_connected) {
        toast.error(t('plugins.pluginSystemNotReady'));
        return;
      }

      if (!validateFileType(file)) {
        toast.error(t('plugins.unsupportedFileType'));
        return;
      }

      setModalOpen(true);
      setPluginInstallStatus(PluginInstallStatus.INSTALLING);
      setInstallError(null);
      installPlugin('local', { file });
    },
    [t, pluginSystemStatus],
  );

  const handleFileSelect = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  }, []);

  const handleFileChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) {
        uploadPluginFile(file);
      }
      // 清空input值，以便可以重复选择同一个文件
      event.target.value = '';
    },
    [uploadPluginFile],
  );

  const isPluginSystemReady =
    pluginSystemStatus?.is_enable && pluginSystemStatus?.is_connected;

  const handleDragOver = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      if (isPluginSystemReady) {
        setIsDragOver(true);
      }
    },
    [isPluginSystemReady],
  );

  const handleDragLeave = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      setIsDragOver(false);

      if (!isPluginSystemReady) {
        toast.error(t('plugins.pluginSystemNotReady'));
        return;
      }

      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        uploadPluginFile(files[0]);
      }
    },
    [uploadPluginFile, isPluginSystemReady, t],
  );

  // 插件系统未启用的状态显示
  const renderPluginDisabledState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]">
      <Power className="w-16 h-16 text-gray-400 mb-4" />
      <h2 className="text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {t('plugins.systemDisabled')}
      </h2>
      <p className="text-gray-500 dark:text-gray-400 max-w-md">
        {t('plugins.systemDisabledDesc')}
      </p>
    </div>
  );

  // 插件系统连接异常的状态显示
  const renderPluginConnectionErrorState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] text-center pt-[10vh]">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width="72"
        height="72"
        fill="#BDBDBD"
      >
        <path d="M17.657 14.8284L16.2428 13.4142L17.657 12C19.2191 10.4379 19.2191 7.90526 17.657 6.34316C16.0949 4.78106 13.5622 4.78106 12.0001 6.34316L10.5859 7.75737L9.17171 6.34316L10.5859 4.92895C12.9291 2.5858 16.7281 2.5858 19.0712 4.92895C21.4143 7.27209 21.4143 11.0711 19.0712 13.4142L17.657 14.8284ZM14.8286 17.6569L13.4143 19.0711C11.0712 21.4142 7.27221 21.4142 4.92907 19.0711C2.58592 16.7279 2.58592 12.9289 4.92907 10.5858L6.34328 9.17159L7.75749 10.5858L6.34328 12C4.78118 13.5621 4.78118 16.0948 6.34328 17.6569C7.90538 19.219 10.438 19.219 12.0001 17.6569L13.4143 16.2427L14.8286 17.6569ZM14.8286 7.75737L16.2428 9.17159L9.17171 16.2427L7.75749 14.8284L14.8286 7.75737ZM5.77539 2.29291L7.70724 1.77527L8.74252 5.63897L6.81067 6.15661L5.77539 2.29291ZM15.2578 18.3611L17.1896 17.8434L18.2249 21.7071L16.293 22.2248L15.2578 18.3611ZM2.29303 5.77527L6.15673 6.81054L5.63909 8.7424L1.77539 7.70712L2.29303 5.77527ZM18.3612 15.2576L22.2249 16.2929L21.7072 18.2248L17.8435 17.1895L18.3612 15.2576Z"></path>
      </svg>

      <h2 className="text-2xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {t('plugins.connectionError')}
      </h2>
      <p className="text-gray-500 dark:text-gray-400 max-w-md mb-4">
        {t('plugins.connectionErrorDesc')}
      </p>
    </div>
  );

  // 加载状态显示
  const renderLoadingState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] pt-[10vh]">
      <p className="text-gray-500 dark:text-gray-400">
        {t('plugins.loadingStatus')}
      </p>
    </div>
  );

  // 根据状态返回不同的内容
  if (statusLoading) {
    return renderLoadingState();
  }

  if (!pluginSystemStatus?.is_enable) {
    return renderPluginDisabledState();
  }

  if (!pluginSystemStatus?.is_connected) {
    return renderPluginConnectionErrorState();
  }

  return (
    <div
      className={`${styles.pageContainer} ${isDragOver ? 'bg-blue-50' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".lbpkg,.zip"
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <div className="flex flex-row justify-between items-center px-[0.8rem]">
          <TabsList className="shadow-md py-5 bg-[#f0f0f0] dark:bg-[#2a2a2e]">
            <TabsTrigger value="installed" className="px-6 py-4 cursor-pointer">
              {t('plugins.installed')}
            </TabsTrigger>
            {systemInfo.enable_marketplace && (
              <TabsTrigger value="market" className="px-6 py-4 cursor-pointer">
                {t('plugins.marketplace')}
              </TabsTrigger>
            )}
          </TabsList>

          <div className="flex flex-row justify-end items-center">
            {/* <Button
              variant="outline"
              className="px-6 py-4 cursor-pointer mr-2"
              onClick={() => {
                // setSortModalOpen(true);
              }}
            >
              {t('plugins.arrange')}
            </Button> */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="default" className="px-6 py-4 cursor-pointer">
                  <PlusIcon className="w-4 h-4" />
                  {t('plugins.install')}
                  <ChevronDownIcon className="ml-2 w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleFileSelect}>
                  <UploadIcon className="w-4 h-4" />
                  {t('plugins.uploadLocal')}
                </DropdownMenuItem>
                {systemInfo.enable_marketplace && (
                  <DropdownMenuItem
                    onClick={() => {
                      setActiveTab('market');
                    }}
                  >
                    <StoreIcon className="w-4 h-4" />
                    {t('plugins.marketplace')}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <TabsContent value="installed">
          <PluginInstalledComponent ref={pluginInstalledRef} />
        </TabsContent>
        <TabsContent value="market">
          <MarketPage
            installPlugin={(plugin: PluginV4) => {
              setInstallSource('marketplace');
              setInstallInfo({
                plugin_author: plugin.author,
                plugin_name: plugin.name,
                plugin_version: plugin.latest_version,
              });
              setPluginInstallStatus(PluginInstallStatus.ASK_CONFIRM);
              setModalOpen(true);
            }}
          />
        </TabsContent>
      </Tabs>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="w-[500px] p-6 bg-white dark:bg-[#1a1a1e]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-4">
              <Download className="size-6" />
              <span>{t('plugins.installPlugin')}</span>
            </DialogTitle>
          </DialogHeader>
          {pluginInstallStatus === PluginInstallStatus.WAIT_INPUT && (
            <div className="mt-4">
              <p className="mb-2">{t('plugins.onlySupportGithub')}</p>
              <Input
                placeholder={t('plugins.enterGithubLink')}
                value={githubURL}
                onChange={(e) => setGithubURL(e.target.value)}
                className="mb-4"
              />
            </div>
          )}
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
            {(pluginInstallStatus === PluginInstallStatus.WAIT_INPUT ||
              pluginInstallStatus === PluginInstallStatus.ASK_CONFIRM) && (
              <>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  {t('common.cancel')}
                </Button>
                <Button onClick={() => handleModalConfirm()}>
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

      {/* 拖拽提示覆盖层 */}
      {isDragOver && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-50 flex items-center justify-center z-50 pointer-events-none">
          <div className="bg-white rounded-lg p-8 shadow-lg border-2 border-dashed border-gray-500">
            <div className="text-center">
              <UploadIcon className="mx-auto h-12 w-12 text-gray-500 mb-4" />
              <p className="text-lg font-medium text-gray-700">
                {t('plugins.dragToUpload')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* <PluginSortDialog
        open={sortModalOpen}
        onOpenChange={setSortModalOpen}
        onSortComplete={() => {
          pluginInstalledRef.current?.refreshPluginList();
        }}
      /> */}
    </div>
  );
}
