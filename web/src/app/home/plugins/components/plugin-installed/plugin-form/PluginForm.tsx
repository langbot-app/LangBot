import { useState, useEffect, useRef } from 'react';
import { ApiRespPluginConfig } from '@/app/infra/entities/api';
import { Plugin } from '@/app/infra/entities/plugin';
import { httpClient } from '@/app/infra/http/HttpClient';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { useTranslation } from 'react-i18next';
import PluginComponentList from '@/app/home/plugins/components/plugin-installed/PluginComponentList';

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
  const currentFormValues = useRef<object>({});
  const uploadedFileKeys = useRef<Set<string>>(new Set());
  const initialFileKeys = useRef<Set<string>>(new Set());

  useEffect(() => {
    // 获取插件信息
    httpClient.getPlugin(pluginAuthor, pluginName).then((res) => {
      setPluginInfo(res.plugin);
    });
    // 获取插件配置
    httpClient.getPluginConfig(pluginAuthor, pluginName).then((res) => {
      setPluginConfig(res);

      // 提取初始配置中的所有文件 key
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extractFileKeys = (obj: any): string[] => {
        const keys: string[] = [];
        if (obj && typeof obj === 'object') {
          if ('file_key' in obj && typeof obj.file_key === 'string') {
            keys.push(obj.file_key);
          }
          for (const value of Object.values(obj)) {
            if (Array.isArray(value)) {
              value.forEach((item) => keys.push(...extractFileKeys(item)));
            } else if (typeof value === 'object' && value !== null) {
              keys.push(...extractFileKeys(value));
            }
          }
        }
        return keys;
      };

      const fileKeys = extractFileKeys(res.config);
      initialFileKeys.current = new Set(fileKeys);
    });
  }, [pluginAuthor, pluginName]);

  const handleSubmit = async () => {
    setIsLoading(true);
    const isDebugPlugin = pluginInfo?.debug;

    try {
      // 保存配置
      await httpClient.updatePluginConfig(
        pluginAuthor,
        pluginName,
        currentFormValues.current,
      );

      // 提取最终保存的配置中的所有文件 key
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extractFileKeys = (obj: any): string[] => {
        const keys: string[] = [];
        if (obj && typeof obj === 'object') {
          if ('file_key' in obj && typeof obj.file_key === 'string') {
            keys.push(obj.file_key);
          }
          for (const value of Object.values(obj)) {
            if (Array.isArray(value)) {
              value.forEach((item) => keys.push(...extractFileKeys(item)));
            } else if (typeof value === 'object' && value !== null) {
              keys.push(...extractFileKeys(value));
            }
          }
        }
        return keys;
      };

      const finalFileKeys = new Set(extractFileKeys(currentFormValues.current));

      // 计算需要删除的文件：
      // 1. 在编辑期间上传的，但最终未保存的文件
      // 2. 初始配置中有的，但最终配置中没有的文件（被删除的文件）
      const filesToDelete: string[] = [];

      // 上传了但未使用的文件
      uploadedFileKeys.current.forEach((key) => {
        if (!finalFileKeys.has(key)) {
          filesToDelete.push(key);
        }
      });

      // 初始有但最终没有的文件（被删除的）
      initialFileKeys.current.forEach((key) => {
        if (!finalFileKeys.has(key)) {
          filesToDelete.push(key);
        }
      });

      // 删除不需要的文件
      const deletePromises = filesToDelete.map((fileKey) =>
        httpClient.deletePluginConfigFile(fileKey).catch((err) => {
          console.warn(`Failed to delete file ${fileKey}:`, err);
        }),
      );

      await Promise.all(deletePromises);

      toast.success(
        isDebugPlugin
          ? t('plugins.saveConfigSuccessDebugPlugin')
          : t('plugins.saveConfigSuccessNormal'),
      );
      onFormSubmit(1000);
    } catch (error) {
      toast.error(t('plugins.saveConfigError') + (error as Error).message);
    } finally {
      setIsLoading(false);
    }
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

        <div className="mb-4 flex flex-row items-center justify-start gap-[0.4rem]">
          <PluginComponentList
            components={pluginInfo.components}
            showComponentName={true}
            showTitle={false}
            useBadge={true}
            t={t}
          />
        </div>

        {pluginInfo.manifest.manifest.spec.config.length > 0 && (
          <DynamicFormComponent
            itemConfigList={pluginInfo.manifest.manifest.spec.config}
            initialValues={pluginConfig.config as Record<string, object>}
            onSubmit={(values) => {
              // 只保存表单值的引用，不触发状态更新
              currentFormValues.current = values;
            }}
            onFileUploaded={(fileKey) => {
              // 追踪上传的文件
              uploadedFileKeys.current.add(fileKey);
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
            onClick={() => handleSubmit()}
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
