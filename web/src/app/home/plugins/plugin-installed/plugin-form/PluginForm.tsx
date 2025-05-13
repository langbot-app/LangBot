import { useState, useEffect } from 'react';
import { ApiRespPluginConfig, Plugin } from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import DynamicFormComponent from '@/app/home/components/dynamic-form/DynamicFormComponent';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { toast } from 'sonner';
import { i18nObj } from '@/i18n/I18nProvider';

enum PluginRemoveStatus {
  WAIT_INPUT = 'WAIT_INPUT',
  REMOVING = 'REMOVING',
  ERROR = 'ERROR',
}

export default function PluginForm({
  pluginAuthor,
  pluginName,
  onFormSubmit,
  onFormCancel,
}: {
  pluginAuthor: string;
  pluginName: string;
  onFormSubmit: () => void;
  onFormCancel: () => void;
}) {
  const [pluginInfo, setPluginInfo] = useState<Plugin>();
  const [pluginConfig, setPluginConfig] = useState<ApiRespPluginConfig>();
  const [isSaving, setIsLoading] = useState(false);

  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [pluginRemoveStatus, setPluginRemoveStatus] =
    useState<PluginRemoveStatus>(PluginRemoveStatus.WAIT_INPUT);
  const [pluginRemoveError, setPluginRemoveError] = useState<string | null>(
    null,
  );

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
    httpClient
      .updatePluginConfig(pluginAuthor, pluginName, values)
      .then(() => {
        onFormSubmit();
        toast.success('保存成功');
      })
      .catch((error) => {
        toast.error('保存失败：' + error.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  if (!pluginInfo || !pluginConfig) {
    return <div>加载中...</div>;
  }

  function deletePlugin() {
    setPluginRemoveStatus(PluginRemoveStatus.REMOVING);
    httpClient
      .removePlugin(pluginAuthor, pluginName)
      .then((res) => {
        const taskId = res.task_id;

        let alreadySuccess = false;

        const interval = setInterval(() => {
          httpClient.getAsyncTask(taskId).then((res) => {
            if (res.runtime.done) {
              clearInterval(interval);
              if (res.runtime.exception) {
                setPluginRemoveError(res.runtime.exception);
                setPluginRemoveStatus(PluginRemoveStatus.ERROR);
              } else {
                // success
                if (!alreadySuccess) {
                  toast.success('插件删除成功');
                  alreadySuccess = true;
                }
                setPluginRemoveStatus(PluginRemoveStatus.WAIT_INPUT);
                setShowDeleteConfirmModal(false);
                onFormSubmit();
              }
            }
          });
        }, 1000);
      })
      .catch((error) => {
        setPluginRemoveError(error.message);
        setPluginRemoveStatus(PluginRemoveStatus.ERROR);
      });
  }

  return (
    <div>
      <Dialog
        open={showDeleteConfirmModal}
        onOpenChange={setShowDeleteConfirmModal}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除确认</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            {pluginRemoveStatus === PluginRemoveStatus.WAIT_INPUT && (
              <div>
                你确定要删除插件（{pluginAuthor}/{pluginName}）吗？
              </div>
            )}
            {pluginRemoveStatus === PluginRemoveStatus.REMOVING && (
              <div>删除中...</div>
            )}
            {pluginRemoveStatus === PluginRemoveStatus.ERROR && (
              <div>
                删除失败：
                <div className="text-red-500">{pluginRemoveError}</div>
              </div>
            )}
          </DialogDescription>
          <DialogFooter>
            {pluginRemoveStatus === PluginRemoveStatus.WAIT_INPUT && (
              <Button
                variant="outline"
                onClick={() => {
                  setShowDeleteConfirmModal(false);
                  setPluginRemoveStatus(PluginRemoveStatus.WAIT_INPUT);
                }}
              >
                取消
              </Button>
            )}
            {pluginRemoveStatus === PluginRemoveStatus.WAIT_INPUT && (
              <Button
                variant="destructive"
                onClick={() => {
                  deletePlugin();
                }}
              >
                确认删除
              </Button>
            )}
            {pluginRemoveStatus === PluginRemoveStatus.REMOVING && (
              <Button variant="destructive" disabled>
                删除中...
              </Button>
            )}
            {pluginRemoveStatus === PluginRemoveStatus.ERROR && (
              <Button
                variant="default"
                onClick={() => {
                  setShowDeleteConfirmModal(false);
                  // setPluginRemoveStatus(PluginRemoveStatus.WAIT_INPUT);
                }}
              >
                关闭
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="space-y-2">
        <div className="text-lg font-medium">{pluginInfo.name}</div>
        <div className="text-sm text-gray-500 pb-2">
          {i18nObj(pluginInfo.description)}
        </div>
        {pluginInfo.config_schema.length > 0 && (
          <DynamicFormComponent
            itemConfigList={pluginInfo.config_schema}
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
        {pluginInfo.config_schema.length === 0 && (
          <div className="text-sm text-gray-500">该插件没有配置项。</div>
        )}
      </div>

      <div className="sticky bottom-0 left-0 right-0 bg-background border-t p-4 mt-4">
        <div className="flex justify-end gap-2">
          <Button
            variant="destructive"
            onClick={() => {
              setShowDeleteConfirmModal(true);
              setPluginRemoveStatus(PluginRemoveStatus.WAIT_INPUT);
            }}
            disabled={pluginRemoveStatus === PluginRemoveStatus.REMOVING}
          >
            {pluginRemoveStatus === PluginRemoveStatus.REMOVING
              ? '删除中...'
              : '删除插件'}
          </Button>

          <Button
            type="submit"
            onClick={() => handleSubmit(pluginConfig.config)}
            disabled={isSaving}
          >
            {isSaving ? '保存中...' : '保存配置'}
          </Button>
          <Button type="button" variant="outline" onClick={onFormCancel}>
            取消
          </Button>
        </div>
      </div>
    </div>
  );
}
