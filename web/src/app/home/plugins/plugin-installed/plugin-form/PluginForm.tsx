import { useState, useEffect } from 'react';
import { ApiRespPluginConfig } from '@/app/infra/entities/api';
import { Plugin } from '@/app/infra/entities/plugin';
import { httpClient } from '@/app/infra/http/HttpClient';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';

export default function PluginForm({
  pluginAuthor,
  pluginName,
  onFormSubmit,
  onFormCancel,
}: {
  pluginAuthor: string;
  pluginName: string;
  onFormSubmit: (timeout?: number) => void;
  onFormCancel: () => void;
}) {
  const { t } = useTranslation();
  const [pluginInfo, setPluginInfo] = useState<Plugin>();
  const [pluginConfig, setPluginConfig] = useState<ApiRespPluginConfig>();
  const [isSaving, setIsLoading] = useState(false);

  useEffect(() => {
    // 获取插件信息
    httpClient.getPlugin(pluginAuthor, pluginName).then((res) => {
      setPluginInfo(res.plugin);
    });
    // 获取插件配置
    httpClient.getPluginConfig(pluginAuthor, pluginName).then((res) => {
      setPluginConfig(res);
    });
  }, [pluginAuthor, pluginName]);

  const handleSubmit = async (values: object) => {
    setIsLoading(true);
    const isDebugPlugin = pluginInfo?.debug;
    httpClient
      .updatePluginConfig(pluginAuthor, pluginName, values)
      .then(() => {
        toast.success(
          isDebugPlugin
            ? t('plugins.saveConfigSuccessDebugPlugin')
            : t('plugins.saveConfigSuccessNormal'),
        );
        onFormSubmit(1000);
      })
      .catch((error) => {
        toast.error(t('plugins.saveConfigError') + error.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  if (!pluginInfo || !pluginConfig) {
    return (
      <div className="flex items-center justify-center h-full mb-[2rem]">
        {t('plugins.loading')}
      </div>
    );
  }

  return (
    <div>
      <div className="space-y-2">
        <div className="text-lg font-medium">
          {extractI18nObject(pluginInfo.manifest.manifest.metadata.label)}
        </div>
        <div className="text-sm text-gray-500 pb-2">
          {extractI18nObject(
            pluginInfo.manifest.manifest.metadata.description ?? {
              en_US: '',
              zh_Hans: '',
            },
          )}
        </div>
        {pluginInfo.manifest.manifest.spec.config.length > 0 && (
          <DynamicFormComponent
            itemConfigList={pluginInfo.manifest.manifest.spec.config}
            initialValues={pluginConfig.config as Record<string, object>}
            onSubmit={(values) => {
              let config = pluginConfig.config;
              config = {
                ...config,
                ...values,
              };
              setPluginConfig({
                config: config,
              });
            }}
          />
        )}
        {pluginInfo.manifest.manifest.spec.config.length === 0 && (
          <div className="text-sm text-gray-500">
            {t('plugins.pluginNoConfig')}
          </div>
        )}
      </div>

      <div className="sticky bottom-0 left-0 right-0 bg-background border-t p-4 mt-4">
        <div className="flex justify-end gap-2">
          <Button
            type="submit"
            onClick={() => handleSubmit(pluginConfig.config)}
            disabled={isSaving}
          >
            {isSaving ? t('plugins.saving') : t('plugins.saveConfig')}
          </Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            {t('plugins.cancel')}
          </Button>
        </div>
      </div>
    </div>
  );
}
