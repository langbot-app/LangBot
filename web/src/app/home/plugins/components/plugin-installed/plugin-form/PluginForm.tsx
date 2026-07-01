import { useState, useEffect, useRef } from 'react';
import { ApiRespPluginConfig } from '@/app/infra/entities/api';
import { Plugin } from '@/app/infra/entities/plugin';
import { httpClient } from '@/app/infra/http/HttpClient';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

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

export default function PluginForm({
  pluginAuthor,
  pluginName,
  onFormSubmit,
}: {
  pluginAuthor: string;
  pluginName: string;
  onFormSubmit: (timeout?: number) => void;
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
      const fileKeys = extractFileKeys(res.config);
      initialFileKeys.current = new Set(fileKeys);
    });
  }, [pluginAuthor, pluginName]);

  const handleSubmit = async () => {
    setIsLoading(true);

    try {
      // 保存配置
      const savedConfig = await httpClient.updatePluginConfig(
        pluginAuthor,
        pluginName,
        currentFormValues.current,
      );
      setPluginConfig(savedConfig);
      currentFormValues.current = savedConfig.config;

      // 提取最终保存的配置中的所有文件 key
      const finalFileKeys = new Set(extractFileKeys(savedConfig.config));

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

      toast.success(t('plugins.saveConfigSuccessNormal'));
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
    <div className="min-w-0 max-w-full space-y-4">
      <Card className="min-w-0 overflow-x-hidden">
        <CardHeader>
          <CardTitle>{t('plugins.pluginConfig')}</CardTitle>
          <CardDescription>{t('plugins.saveConfig')}</CardDescription>
        </CardHeader>
        <CardContent className="min-w-0 overflow-x-hidden">
          {pluginInfo.manifest.manifest.spec.config.length > 0 ? (
            <DynamicFormComponent
              itemConfigList={pluginInfo.manifest.manifest.spec.config}
              initialValues={pluginConfig.config as Record<string, object>}
              onSubmit={(values) => {
                // 只保存表单值的引用,不触发状态更新
                currentFormValues.current = values;
              }}
              onFileUploaded={(fileKey) => {
                // 追踪上传的文件
                uploadedFileKeys.current.add(fileKey);
              }}
            />
          ) : (
            <div className="text-sm text-muted-foreground">
              {t('plugins.pluginNoConfig')}
            </div>
          )}
        </CardContent>
        {pluginInfo.manifest.manifest.spec.config.length > 0 && (
          <CardFooter className="justify-end">
            <Button
              type="submit"
              onClick={() => handleSubmit()}
              disabled={isSaving}
            >
              {isSaving ? t('plugins.saving') : t('plugins.saveConfig')}
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
