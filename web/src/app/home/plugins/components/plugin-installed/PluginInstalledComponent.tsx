import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { useNavigate } from 'react-router-dom';
import { PluginCardVO } from '@/app/home/plugins/components/plugin-installed/PluginCardVO';
import PluginCardComponent from '@/app/home/plugins/components/plugin-installed/plugin-card/PluginCardComponent';
import styles from '@/app/home/plugins/plugins.module.css';
import { httpClient } from '@/app/infra/http/HttpClient';
import { getCloudServiceClientSync } from '@/app/infra/http';
import { isNewerVersion } from '@/app/utils/versionCompare';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { useTranslation } from 'react-i18next';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { toast } from 'sonner';
import { useAsyncTask, AsyncTaskStatus } from '@/hooks/useAsyncTask';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { Puzzle } from 'lucide-react';

export interface PluginInstalledComponentRef {
  refreshPluginList: () => void;
}

enum PluginOperationType {
  DELETE = 'DELETE',
  UPDATE = 'UPDATE',
}

const PluginInstalledComponent = forwardRef<PluginInstalledComponentRef>(
  (props, ref) => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { refreshPlugins } = useSidebarData();
    const [pluginList, setPluginList] = useState<PluginCardVO[]>([]);
    const [showOperationModal, setShowOperationModal] = useState(false);
    const [operationType, setOperationType] = useState<PluginOperationType>(
      PluginOperationType.DELETE,
    );
    const [targetPlugin, setTargetPlugin] = useState<PluginCardVO | null>(null);
    const [deleteData, setDeleteData] = useState<boolean>(false);

    const asyncTask = useAsyncTask({
      onSuccess: () => {
        const successMessage =
          operationType === PluginOperationType.DELETE
            ? t('plugins.deleteSuccess')
            : t('plugins.updateSuccess');
        toast.success(successMessage);
        setShowOperationModal(false);
        getPluginList();
        refreshPlugins();
      },
      onError: () => {
        // Error is already handled in the hook state
      },
    });

    useEffect(() => {
      initData();
    }, []);

    function initData() {
      getPluginList();
    }

    async function getPluginList() {
      try {
        // 获取已安装插件列表
        const installedPluginsResp = await httpClient.getPlugins();
        const installedPlugins = installedPluginsResp.plugins;

        // 获取市场插件列表
        const client = getCloudServiceClientSync();
        const marketplaceResp = await client.getMarketplacePlugins(1, 100);
        const marketplacePlugins = marketplaceResp.plugins;

        // 创建市场插件映射，便于快速查找
        const marketplacePluginMap = new Map();
        marketplacePlugins.forEach((plugin) => {
          const key = `${plugin.author}/${plugin.name}`;
          marketplacePluginMap.set(key, plugin);
        });

        // 转换并比较版本号
        const pluginCards = installedPlugins.map((plugin) => {
          const marketplaceKey = `${plugin.manifest.manifest.metadata.author}/${plugin.manifest.manifest.metadata.name}`;
          const marketplacePlugin = marketplacePluginMap.get(marketplaceKey);
          const cardVO = new PluginCardVO({
            author: plugin.manifest.manifest.metadata.author ?? '',
            label: extractI18nObject(plugin.manifest.manifest.metadata.label),
            description: extractI18nObject(
              plugin.manifest.manifest.metadata.description ?? {
                en_US: '',
                zh_Hans: '',
              },
            ),
            debug: plugin.debug,
            enabled: plugin.enabled,
            name: plugin.manifest.manifest.metadata.name,
            version: plugin.manifest.manifest.metadata.version ?? '',
            status: plugin.status,
            components: plugin.components,
            priority: plugin.priority,
            install_source: plugin.install_source,
            install_info: plugin.install_info,
            type: marketplacePlugin?.type,
          });

          // 检查是否来自市场且有更新
          if (cardVO.install_source === 'marketplace' && marketplacePlugin) {
            if (marketplacePlugin.latest_version) {
              cardVO.hasUpdate = isNewerVersion(
                marketplacePlugin.latest_version,
                cardVO.version,
              );
            }
          }

          return cardVO;
        });

        setPluginList(pluginCards);
      } catch (error) {
        console.error('获取插件列表失败:', error);
        // 失败时仍显示已安装插件，不影响用户体验
        const installedPluginsResp = await httpClient.getPlugins();
        setPluginList(
          installedPluginsResp.plugins.map((plugin) => {
            return new PluginCardVO({
              author: plugin.manifest.manifest.metadata.author ?? '',
              label: extractI18nObject(plugin.manifest.manifest.metadata.label),
              description: extractI18nObject(
                plugin.manifest.manifest.metadata.description ?? {
                  en_US: '',
                  zh_Hans: '',
                },
              ),
              debug: plugin.debug,
              enabled: plugin.enabled,
              name: plugin.manifest.manifest.metadata.name,
              version: plugin.manifest.manifest.metadata.version ?? '',
              status: plugin.status,
              components: plugin.components,
              priority: plugin.priority,
              install_source: plugin.install_source,
              install_info: plugin.install_info,
            });
          }),
        );
      }
    }

    useImperativeHandle(ref, () => ({
      refreshPluginList: getPluginList,
    }));

    function handlePluginClick(plugin: PluginCardVO) {
      const pluginId = `${plugin.author}/${plugin.name}`;
      navigate(`/home/plugins?id=${encodeURIComponent(pluginId)}`);
    }

    function handlePluginDelete(plugin: PluginCardVO) {
      setTargetPlugin(plugin);
      setOperationType(PluginOperationType.DELETE);
      setShowOperationModal(true);
      setDeleteData(false);
      asyncTask.reset();
    }

    function handlePluginUpdate(plugin: PluginCardVO) {
      setTargetPlugin(plugin);
      setOperationType(PluginOperationType.UPDATE);
      setShowOperationModal(true);
      asyncTask.reset();
    }

    function executeOperation() {
      if (!targetPlugin) return;

      const apiCall =
        operationType === PluginOperationType.DELETE
          ? httpClient.removePlugin(
              targetPlugin.author,
              targetPlugin.name,
              deleteData,
            )
          : httpClient.upgradePlugin(targetPlugin.author, targetPlugin.name);

      apiCall
        .then((res) => {
          asyncTask.startTask(res.task_id);
        })
        .catch((error) => {
          const errorMessage =
            operationType === PluginOperationType.DELETE
              ? t('plugins.deleteError') + error.message
              : t('plugins.updateError') + error.message;
          toast.error(errorMessage);
        });
    }

    return (
      <>
        <Dialog
          open={showOperationModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowOperationModal(false);
              setTargetPlugin(null);
              asyncTask.reset();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {operationType === PluginOperationType.DELETE
                  ? t('plugins.deleteConfirm')
                  : t('plugins.updateConfirm')}
              </DialogTitle>
            </DialogHeader>
            <DialogDescription>
              {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
                <div className="flex flex-col gap-4">
                  <div>
                    {operationType === PluginOperationType.DELETE
                      ? t('plugins.confirmDeletePlugin', {
                          author: targetPlugin?.author ?? '',
                          name: targetPlugin?.name ?? '',
                        })
                      : t('plugins.confirmUpdatePlugin', {
                          author: targetPlugin?.author ?? '',
                          name: targetPlugin?.name ?? '',
                        })}
                  </div>
                  {operationType === PluginOperationType.DELETE && (
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="delete-data"
                        checked={deleteData}
                        onCheckedChange={(checked) =>
                          setDeleteData(checked === true)
                        }
                      />
                      <label
                        htmlFor="delete-data"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                      >
                        {t('plugins.deleteDataCheckbox')}
                      </label>
                    </div>
                  )}
                </div>
              )}
              {asyncTask.status === AsyncTaskStatus.RUNNING && (
                <div>
                  {operationType === PluginOperationType.DELETE
                    ? t('plugins.deleting')
                    : t('plugins.updating')}
                </div>
              )}
              {asyncTask.status === AsyncTaskStatus.ERROR && (
                <div>
                  {operationType === PluginOperationType.DELETE
                    ? t('plugins.deleteError')
                    : t('plugins.updateError')}
                  <div className="text-red-500">{asyncTask.error}</div>
                </div>
              )}
            </DialogDescription>
            <DialogFooter>
              {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowOperationModal(false);
                    setTargetPlugin(null);
                    asyncTask.reset();
                  }}
                >
                  {t('plugins.cancel')}
                </Button>
              )}
              {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
                <Button
                  variant={
                    operationType === PluginOperationType.DELETE
                      ? 'destructive'
                      : 'default'
                  }
                  onClick={() => {
                    executeOperation();
                  }}
                >
                  {operationType === PluginOperationType.DELETE
                    ? t('plugins.confirmDelete')
                    : t('plugins.confirmUpdate')}
                </Button>
              )}
              {asyncTask.status === AsyncTaskStatus.RUNNING && (
                <Button
                  variant={
                    operationType === PluginOperationType.DELETE
                      ? 'destructive'
                      : 'default'
                  }
                  disabled
                >
                  {operationType === PluginOperationType.DELETE
                    ? t('plugins.deleting')
                    : t('plugins.updating')}
                </Button>
              )}
              {asyncTask.status === AsyncTaskStatus.ERROR && (
                <Button
                  variant="default"
                  onClick={() => {
                    setShowOperationModal(false);
                    asyncTask.reset();
                  }}
                >
                  {t('plugins.close')}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {pluginList.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-gray-500 min-h-[60vh] w-full gap-2">
            <Puzzle className="h-[3rem] w-[3rem]" />
            <div className="text-lg mb-2">{t('plugins.noPluginInstalled')}</div>
          </div>
        ) : (
          <div className={`${styles.pluginListContainer}`}>
            {pluginList.map((vo, index) => {
              return (
                <div key={index}>
                  <PluginCardComponent
                    cardVO={vo}
                    onCardClick={() => handlePluginClick(vo)}
                    onDeleteClick={() => handlePluginDelete(vo)}
                    onUpgradeClick={() => handlePluginUpdate(vo)}
                  />
                </div>
              );
            })}
          </div>
        )}
      </>
    );
  },
);

export default PluginInstalledComponent;
