import PluginInstalledComponent, {
  PluginInstalledComponentRef,
  FilterOptions,
  FilterType,
} from '@/app/home/plugins/components/plugin-installed/PluginInstalledComponent';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import PluginDetailContent from './PluginDetailContent';
import styles from './plugins.module.css';
import { Button } from '@/components/ui/button';
import { Power, Code, Copy, Check, Bug, Unlink } from 'lucide-react';
import { copyToClipboard } from '@/app/utils/clipboard';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { ApiRespPluginSystemStatus } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import {
  PluginInstallTaskQueue,
  usePluginInstallTasks,
} from '@/app/home/plugins/components/plugin-install-task';

export default function PluginConfigPage() {
  const [searchParams] = useSearchParams();
  const detailId = searchParams.get('id');

  if (detailId) {
    return <PluginDetailContent id={detailId} />;
  }

  return <PluginListView />;
}

function PluginListView() {
  const { t } = useTranslation();
  const {
    refreshPlugins,
    extensionsGroupByType: groupByType,
    setExtensionsGroupByType: setGroupByType,
  } = useSidebarData();
  const { registerOnTaskComplete, unregisterOnTaskComplete } =
    usePluginInstallTasks();
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [debugInfo, setDebugInfo] = useState<{
    debug_url: string;
    plugin_debug_key: string;
  } | null>(null);
  const [debugPopoverOpen, setDebugPopoverOpen] = useState(false);
  const [copiedDebugUrl, setCopiedDebugUrl] = useState(false);
  const [copiedDebugKey, setCopiedDebugKey] = useState(false);
  const [filterType, setFilterType] = useState<FilterType>('all');
  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);

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

    void fetchPluginSystemStatus();
  }, [t]);

  useEffect(() => {
    const onComplete = (_taskId: number, success: boolean) => {
      if (success) {
        toast.success(t('plugins.installSuccess'));
        pluginInstalledRef.current?.refreshPluginList();
        refreshPlugins();
      }
    };
    registerOnTaskComplete(onComplete);
    return () => {
      unregisterOnTaskComplete(onComplete);
    };
  }, [registerOnTaskComplete, unregisterOnTaskComplete, refreshPlugins, t]);

  const handleShowDebugInfo = async () => {
    try {
      const info = await httpClient.getPluginDebugInfo();
      setDebugInfo(info);
      setDebugPopoverOpen(true);
    } catch (error) {
      console.error('Failed to fetch debug info:', error);
      toast.error(t('plugins.failedToGetDebugInfo'));
    }
  };

  const handleCopyDebugInfo = (text: string, type: 'url' | 'key') => {
    copyToClipboard(text).catch(() => {});
    if (type === 'url') {
      setCopiedDebugUrl(true);
      setTimeout(() => setCopiedDebugUrl(false), 2000);
    } else {
      setCopiedDebugKey(true);
      setTimeout(() => setCopiedDebugKey(false), 2000);
    }
  };

  const renderPluginDisabledState = () => (
    <div className="flex justify-center pt-[10vh] px-4">
      <Alert className="max-w-md">
        <Power />
        <AlertTitle>{t('plugins.systemDisabled')}</AlertTitle>
        <AlertDescription>{t('plugins.systemDisabledDesc')}</AlertDescription>
      </Alert>
    </div>
  );

  const renderPluginConnectionErrorState = () => (
    <div className="flex justify-center pt-[10vh] px-4">
      <Alert variant="destructive" className="max-w-md">
        <Unlink />
        <AlertTitle>{t('plugins.connectionError')}</AlertTitle>
        <AlertDescription>{t('plugins.connectionErrorDesc')}</AlertDescription>
      </Alert>
    </div>
  );

  const renderLoadingState = () => (
    <div className="flex flex-col gap-3 pt-[10vh] px-4 max-w-md mx-auto">
      <Skeleton className="h-6 w-1/2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
    </div>
  );

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
    <div className={`${styles.pageContainer} h-full flex flex-col`}>
      <div className="flex flex-col md:flex-row md:justify-between md:items-center px-[0.8rem] pb-4 flex-shrink-0 gap-2">
        <div className="overflow-x-auto -mx-1 px-1">
          <Tabs
            value={filterType}
            onValueChange={(value) => setFilterType(value as FilterType)}
          >
            <TabsList>
              {FilterOptions.map((option) => (
                <TabsTrigger key={option.value} value={option.value}>
                  {option.icon && <option.icon className="size-4" />}
                  {t(option.labelKey)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
        <div className="flex flex-row items-center gap-2 flex-wrap">
          <div className="flex items-center gap-2 px-1 sm:px-2">
            <Switch
              id="group-by-type"
              checked={groupByType}
              onCheckedChange={setGroupByType}
              disabled={filterType !== 'all'}
            />
            <Label
              htmlFor="group-by-type"
              className="text-sm cursor-pointer whitespace-nowrap"
            >
              {t('plugins.groupByType')}
            </Label>
          </div>
          <PluginInstallTaskQueue />

          <Popover open={debugPopoverOpen} onOpenChange={setDebugPopoverOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className="px-3 sm:px-4 py-4 cursor-pointer"
                onClick={handleShowDebugInfo}
              >
                <Code className="w-4 h-4 sm:mr-2" />
                <span className="hidden sm:inline">
                  {t('plugins.debugInfo')}
                </span>
              </Button>
            </PopoverTrigger>
            <PopoverContent
              className="w-[calc(100vw-2rem)] max-w-[380px]"
              align="end"
            >
              <div className="space-y-3">
                <div className="flex items-center gap-2 pb-2 border-b">
                  <Bug className="w-4 h-4" />
                  <h4 className="font-semibold text-sm">
                    {t('plugins.debugInfoTitle')}
                  </h4>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-sm font-medium whitespace-nowrap min-w-[50px]">
                    {t('plugins.debugUrl')}:
                  </label>
                  <Input
                    value={debugInfo?.debug_url || ''}
                    readOnly
                    className="flex-1 min-w-0 font-mono text-xs h-8"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0"
                    onClick={() =>
                      handleCopyDebugInfo(debugInfo?.debug_url || '', 'url')
                    }
                  >
                    {copiedDebugUrl ? (
                      <Check className="w-3.5 h-3.5 text-green-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </Button>
                </div>

                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <label className="text-sm font-medium whitespace-nowrap min-w-[50px]">
                      {t('plugins.debugKey')}:
                    </label>
                    <Input
                      value={
                        debugInfo?.plugin_debug_key || t('plugins.noDebugKey')
                      }
                      readOnly
                      className="w-[220px] font-mono text-xs h-8"
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 shrink-0"
                      onClick={() =>
                        handleCopyDebugInfo(
                          debugInfo?.plugin_debug_key || '',
                          'key',
                        )
                      }
                      disabled={!debugInfo?.plugin_debug_key}
                    >
                      {copiedDebugKey ? (
                        <Check className="w-3.5 h-3.5 text-green-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </Button>
                  </div>
                  {!debugInfo?.plugin_debug_key && (
                    <p className="text-xs text-muted-foreground ml-[58px]">
                      {t('plugins.debugKeyDisabled')}
                    </p>
                  )}
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <PluginInstalledComponent
          ref={pluginInstalledRef}
          filterType={filterType}
          groupByType={groupByType}
        />
      </div>
    </div>
  );
}
