import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { useNavigate } from 'react-router-dom';
import { ExtensionCardVO, ExtensionType } from './ExtensionCardVO';
import ExtensionCardComponent from './ExtensionCardComponent';
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
import {
  ToggleGroup,
  ToggleGroupItem,
} from '@/components/ui/toggle-group';
import { Wrench, AudioWaveform, Book } from 'lucide-react';
import { MCPSessionStatus } from '@/app/infra/entities/api';

export interface PluginInstalledComponentRef {
  refreshPluginList: () => void;
}

enum ExtensionOperationType {
  DELETE = 'DELETE',
  UPDATE = 'UPDATE',
}

type FilterType = 'all' | ExtensionType;

const FilterOptions = [
  { value: 'all' as FilterType, labelKey: 'market.filters.allFormats', icon: null },
  { value: 'plugin' as FilterType, labelKey: 'market.typePlugin', icon: Wrench },
  { value: 'mcp' as FilterType, labelKey: 'market.typeMCP', icon: AudioWaveform },
  { value: 'skill' as FilterType, labelKey: 'market.typeSkill', icon: Book },
];

const PluginInstalledComponent = forwardRef<PluginInstalledComponentRef>(
  (props, ref) => {
    const { t } = useTranslation();
    const navigate = useNavigate();
    const { refreshPlugins, refreshMCPServers, refreshSkills } = useSidebarData();
    const [extensionList, setExtensionList] = useState<ExtensionCardVO[]>([]);
    const [filterType, setFilterType] = useState<FilterType>('all');
    const [showOperationModal, setShowOperationModal] = useState(false);
    const [operationType, setOperationType] = useState<ExtensionOperationType>(
      ExtensionOperationType.DELETE,
    );
    const [targetExtension, setTargetExtension] = useState<ExtensionCardVO | null>(null);
    const [deleteData, setDeleteData] = useState<boolean>(false);

    const asyncTask = useAsyncTask({
      onSuccess: () => {
        const successMessage =
          operationType === ExtensionOperationType.DELETE
            ? t('plugins.deleteSuccess')
            : t('plugins.updateSuccess');
        toast.success(successMessage);
        setShowOperationModal(false);
        getExtensionList();
        refreshPlugins();
        refreshMCPServers();
        refreshSkills();
      },
      onError: () => {
      },
    });

    useEffect(() => {
      initData();
    }, []);

    function initData() {
      getExtensionList();
    }

    async function getExtensionList() {
      try {
        const client = getCloudServiceClientSync();

        const [installedPluginsResp, marketplaceResp, mcpResp, skillsResp] = await Promise.all([
          httpClient.getPlugins().catch(() => ({ plugins: [] })),
          client.getMarketplacePlugins(1, 100).catch(() => ({ plugins: [] })),
          httpClient.getMCPServers().catch(() => ({ servers: [] })),
          httpClient.getSkills().catch(() => ({ skills: [] })),
        ]);

        const marketplacePluginMap = new Map<string, any>();
        marketplaceResp.plugins.forEach((plugin: any) => {
          const key = `${plugin.author}/${plugin.name}`;
          marketplacePluginMap.set(key, plugin);
        });

        const extensions: ExtensionCardVO[] = [];

        for (const plugin of installedPluginsResp.plugins) {
          const meta = plugin.manifest.manifest.metadata;
          const author = meta.author ?? '';
          const name = meta.name;
          const marketplaceKey = `${author}/${name}`;
          const marketplacePlugin = marketplacePluginMap.get(marketplaceKey);

          let hasUpdate = false;
          if (plugin.install_source === 'marketplace' && marketplacePlugin) {
            if (marketplacePlugin.latest_version) {
              hasUpdate = isNewerVersion(
                marketplacePlugin.latest_version,
                meta.version ?? '',
              );
            }
          }

          extensions.push(new ExtensionCardVO({
            id: marketplaceKey,
            author,
            label: extractI18nObject(meta.label) || name,
            name,
            description: extractI18nObject(meta.description ?? { en_US: '', zh_Hans: '' }),
            version: meta.version ?? '',
            enabled: plugin.enabled,
            type: marketplacePlugin?.type || 'plugin',
            iconURL: httpClient.getPluginIconURL(author, name),
            install_source: plugin.install_source,
            install_info: plugin.install_info,
            status: plugin.status,
            debug: plugin.debug,
            hasUpdate,
          }));
        }

        for (const server of mcpResp.servers) {
          extensions.push(new ExtensionCardVO({
            id: `mcp-${server.name}`,
            author: '',
            label: server.name.replace(/__/g, '/'),
            name: server.name,
            description: '',
            version: '',
            enabled: server.enable,
            type: 'mcp',
            iconURL: httpClient.getPluginIconURL('mcp', server.name),
            status: server.runtime_info?.status,
            runtimeStatus: server.runtime_info?.status,
            tools: server.runtime_info?.tool_count || 0,
            mode: server.mode,
          }));
        }

        for (const skill of skillsResp.skills) {
          extensions.push(new ExtensionCardVO({
            id: `skill-${skill.name}`,
            author: '',
            label: skill.display_name || skill.name,
            name: skill.name,
            description: skill.description || '',
            version: '',
            enabled: true,
            type: 'skill',
            iconURL: httpClient.getPluginIconURL('skill', skill.name),
          }));
        }

        setExtensionList(extensions);
      } catch (error) {
        console.error('Failed to fetch extension list:', error);
        setExtensionList([]);
      }
    }

    useImperativeHandle(ref, () => ({
      refreshPluginList: getExtensionList,
    }));

    function handleExtensionClick(extension: ExtensionCardVO) {
      if (extension.type === 'mcp') {
        navigate(`/home/mcp`);
      } else if (extension.type === 'skill') {
        navigate(`/home/skills`);
      } else {
        const extensionId = `${extension.author}/${extension.name}`;
        navigate(`/home/plugins?id=${encodeURIComponent(extensionId)}`);
      }
    }

    function handleExtensionDelete(extension: ExtensionCardVO) {
      setTargetExtension(extension);
      setOperationType(ExtensionOperationType.DELETE);
      setShowOperationModal(true);
      setDeleteData(false);
      asyncTask.reset();
    }

    function handleExtensionUpdate(extension: ExtensionCardVO) {
      setTargetExtension(extension);
      setOperationType(ExtensionOperationType.UPDATE);
      setShowOperationModal(true);
      asyncTask.reset();
    }

    function executeOperation() {
      if (!targetExtension) return;

      if (targetExtension.type === 'mcp') {
        httpClient.deleteMCPServer(targetExtension.name)
          .then(() => {
            toast.success(t('mcp.deleteSuccess'));
            setShowOperationModal(false);
            getExtensionList();
            refreshMCPServers();
          })
          .catch((error) => {
            toast.error(t('mcp.deleteError') + error.message);
          });
        return;
      }

      if (targetExtension.type === 'skill') {
        httpClient.deleteSkill(targetExtension.name)
          .then(() => {
            toast.success(t('skills.deleteSuccess'));
            setShowOperationModal(false);
            getExtensionList();
            refreshSkills();
          })
          .catch((error) => {
            toast.error(t('skills.deleteError') + error.message);
          });
        return;
      }

      const apiCall =
        operationType === ExtensionOperationType.DELETE
          ? httpClient.removePlugin(
              targetExtension.author,
              targetExtension.name,
              deleteData,
            )
          : httpClient.upgradePlugin(targetExtension.author, targetExtension.name);

      apiCall
        .then((res) => {
          asyncTask.startTask(res.task_id);
        })
        .catch((error) => {
          const errorMessage =
            operationType === ExtensionOperationType.DELETE
              ? t('plugins.deleteError') + error.message
              : t('plugins.updateError') + error.message;
          toast.error(errorMessage);
        });
    }

    const filteredExtensions = extensionList.filter((ext) => {
      if (filterType === 'all') return true;
      return ext.type === filterType;
    });

    const getDeleteConfirmMessage = () => {
      if (!targetExtension) return '';
      if (targetExtension.type === 'mcp') {
        return t('mcp.confirmDeleteServer');
      }
      if (targetExtension.type === 'skill') {
        return t('skills.deleteConfirmation');
      }
      return t('plugins.confirmDeletePlugin', {
        author: targetExtension.author,
        name: targetExtension.name,
      });
    };

    return (
      <>
        <Dialog
          open={showOperationModal}
          onOpenChange={(open) => {
            if (!open) {
              setShowOperationModal(false);
              setTargetExtension(null);
              asyncTask.reset();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {operationType === ExtensionOperationType.DELETE
                  ? t('plugins.deleteConfirm')
                  : t('plugins.updateConfirm')}
              </DialogTitle>
            </DialogHeader>
            <DialogDescription>
              {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
                <div className="flex flex-col gap-4">
                  <div>{getDeleteConfirmMessage()}</div>
                  {operationType === ExtensionOperationType.DELETE && targetExtension?.type === 'plugin' && (
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
                  {operationType === ExtensionOperationType.DELETE
                    ? t('plugins.deleting')
                    : t('plugins.updating')}
                </div>
              )}
              {asyncTask.status === AsyncTaskStatus.ERROR && (
                <div>
                  {operationType === ExtensionOperationType.DELETE
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
                    setTargetExtension(null);
                    asyncTask.reset();
                  }}
                >
                  {t('plugins.cancel')}
                </Button>
              )}
              {asyncTask.status === AsyncTaskStatus.WAIT_INPUT && (
                <Button
                  variant={
                    operationType === ExtensionOperationType.DELETE
                      ? 'destructive'
                      : 'default'
                  }
                  onClick={() => {
                    executeOperation();
                  }}
                >
                  {operationType === ExtensionOperationType.DELETE
                    ? t('plugins.confirmDelete')
                    : t('plugins.confirmUpdate')}
                </Button>
              )}
              {asyncTask.status === AsyncTaskStatus.RUNNING && (
                <Button
                  variant={
                    operationType === ExtensionOperationType.DELETE
                      ? 'destructive'
                      : 'default'
                  }
                  disabled
                >
                  {operationType === ExtensionOperationType.DELETE
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

        <div className="px-[0.8rem] pb-4">
          <ToggleGroup
            type="single"
            value={filterType}
            onValueChange={(value) => {
              if (value) setFilterType(value as FilterType);
            }}
            className="justify-start"
          >
            {FilterOptions.map((option) => (
              <ToggleGroupItem
                key={option.value}
                value={option.value}
                variant="outline"
                className="px-4 py-2"
              >
                {option.icon && <option.icon className="w-4 h-4 mr-2" />}
                {t(option.labelKey)}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        {filteredExtensions.length === 0 ? (
          <div className="flex flex-col items-center justify-center text-gray-500 min-h-[60vh] w-full gap-2">
            <Puzzle className="h-[3rem] w-[3rem]" />
            <div className="text-lg mb-2">{t('plugins.noPluginInstalled')}</div>
          </div>
        ) : (
          <div className={`${styles.pluginListContainer}`}>
            {filteredExtensions.map((vo, index) => {
              return (
                <div key={vo.id || index}>
                  <ExtensionCardComponent
                    cardVO={vo}
                    onCardClick={() => handleExtensionClick(vo)}
                    onDeleteClick={() => handleExtensionDelete(vo)}
                    onUpgradeClick={vo.type === 'plugin' ? () => handleExtensionUpdate(vo) : undefined}
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