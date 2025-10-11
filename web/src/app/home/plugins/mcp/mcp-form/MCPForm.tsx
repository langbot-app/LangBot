'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { httpClient } from '@/app/infra/http/HttpClient';
import { MCPServerConfig } from '@/app/infra/entities/api';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PlusIcon, TrashIcon } from 'lucide-react';

interface MCPFormProps {
  serverName?: string;
  isEdit?: boolean;
  onFormSubmit: () => void;
  onFormCancel: () => void;
}

export default function MCPForm({
  serverName,
  isEdit = false,
  onFormSubmit,
  onFormCancel,
}: MCPFormProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<MCPServerConfig>({
    name: '',
    mode: 'stdio',
    enable: true,
    command: '',
    args: [],
    env: {},
    url: '',
    headers: {},
    timeout: 10,
  });

  useEffect(() => {
    if (isEdit && serverName) {
      loadServerConfig();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, serverName]);

  async function loadServerConfig() {
    try {
      const response = await httpClient.getMCPServer(serverName!);
      setFormData(response.server.config);
    } catch (error: unknown) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      toast.error(t('mcp.getServerListError') + errorMessage);
    }
  }

  function handleInputChange(field: keyof MCPServerConfig, value: unknown) {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  function addArrayItem(field: 'args', value: string = '') {
    const currentArray = formData[field] as string[];
    handleInputChange(field, [...currentArray, value]);
  }

  function updateArrayItem(field: 'args', index: number, value: string) {
    const currentArray = formData[field] as string[];
    const newArray = [...currentArray];
    newArray[index] = value;
    handleInputChange(field, newArray);
  }

  function removeArrayItem(field: 'args', index: number) {
    const currentArray = formData[field] as string[];
    const newArray = currentArray.filter((_, i) => i !== index);
    handleInputChange(field, newArray);
  }

  function addObjectItem(
    field: 'env' | 'headers',
    key: string = '',
    value: string = '',
  ) {
    const currentObj = formData[field] as Record<string, string>;
    handleInputChange(field, {
      ...currentObj,
      [key]: value,
    });
  }

  function updateObjectItem(
    field: 'env' | 'headers',
    oldKey: string,
    newKey: string,
    value: string,
  ) {
    const currentObj = formData[field] as Record<string, string>;
    const newObj = { ...currentObj };
    if (oldKey !== newKey) {
      delete newObj[oldKey];
    }
    newObj[newKey] = value;
    handleInputChange(field, newObj);
  }

  function removeObjectItem(field: 'env' | 'headers', key: string) {
    const currentObj = formData[field] as Record<string, string>;
    const newObj = { ...currentObj };
    delete newObj[key];
    handleInputChange(field, newObj);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // 验证表单
    if (!formData.name.trim()) {
      toast.error(t('mcp.serverNameRequired'));
      return;
    }

    if (formData.mode === 'stdio' && !formData.command?.trim()) {
      toast.error(t('mcp.commandRequired'));
      return;
    }

    if (formData.mode === 'sse' && !formData.url?.trim()) {
      toast.error(t('mcp.urlRequired'));
      return;
    }

    setLoading(true);

    try {
      let taskId: number;

      if (isEdit) {
        const response = await httpClient.updateMCPServer(
          serverName!,
          formData,
        );
        taskId = response.task_id;
      } else {
        const response = await httpClient.createMCPServer(formData);
        taskId = response.task_id;
      }

      // 监控任务状态
      const interval = setInterval(() => {
        httpClient.getAsyncTask(taskId).then((taskResp) => {
          if (taskResp.runtime.done) {
            clearInterval(interval);
            setLoading(false);

            if (taskResp.runtime.exception) {
              toast.error(
                (isEdit ? t('mcp.saveError') : t('mcp.createError')) +
                  taskResp.runtime.exception,
              );
            } else {
              toast.success(
                isEdit ? t('mcp.saveSuccess') : t('mcp.createSuccess'),
              );
              onFormSubmit();
            }
          }
        });
      }, 1000);
    } catch (error: unknown) {
      setLoading(false);
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      toast.error(
        (isEdit ? t('mcp.saveError') : t('mcp.createError')) + errorMessage,
      );
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* 基础配置 */}
      <div className="space-y-4">
        <div>
          <Label htmlFor="name">{t('mcp.serverName')}</Label>
          <Input
            id="name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            disabled={isEdit}
            placeholder={t('mcp.serverName')}
          />
        </div>

        <div>
          <Label htmlFor="enable">{t('common.enable')}</Label>
          <div className="flex items-center space-x-2 mt-2">
            <Switch
              id="enable"
              checked={formData.enable}
              onCheckedChange={(checked) =>
                handleInputChange('enable', checked)
              }
            />
          </div>
        </div>

        <div>
          <Label>{t('mcp.serverMode')}</Label>
          <Tabs
            value={formData.mode}
            onValueChange={(value) =>
              handleInputChange('mode', value as 'stdio' | 'sse')
            }
            className="mt-2"
          >
            <TabsList>
              <TabsTrigger value="stdio">{t('mcp.stdio')}</TabsTrigger>
              <TabsTrigger value="sse">{t('mcp.sse')}</TabsTrigger>
            </TabsList>

            <TabsContent value="stdio" className="space-y-4 mt-4">
              <div>
                <Label htmlFor="command">{t('mcp.command')}</Label>
                <Input
                  id="command"
                  value={formData.command || ''}
                  onChange={(e) => handleInputChange('command', e.target.value)}
                  placeholder="python -m your_mcp_server"
                />
              </div>

              <div>
                <Label>{t('mcp.args')}</Label>
                <div className="space-y-2 mt-2">
                  {(formData.args || []).map((arg, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <Input
                        value={arg}
                        onChange={(e) =>
                          updateArrayItem('args', index, e.target.value)
                        }
                        placeholder="参数"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeArrayItem('args', index)}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => addArrayItem('args')}
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    {t('mcp.addArgument')}
                  </Button>
                </div>
              </div>

              <div>
                <Label>{t('mcp.env')}</Label>
                <div className="space-y-2 mt-2">
                  {Object.entries(formData.env || {}).map(([key, value]) => (
                    <div key={key} className="flex items-center space-x-2">
                      <Input
                        value={key}
                        onChange={(e) =>
                          updateObjectItem('env', key, e.target.value, value)
                        }
                        placeholder={t('mcp.keyName')}
                        className="flex-1"
                      />
                      <Input
                        value={value}
                        onChange={(e) =>
                          updateObjectItem('env', key, key, e.target.value)
                        }
                        placeholder={t('mcp.value')}
                        className="flex-1"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeObjectItem('env', key)}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => addObjectItem('env')}
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    {t('mcp.addEnvVar')}
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="sse" className="space-y-4 mt-4">
              <div>
                <Label htmlFor="url">{t('mcp.url')}</Label>
                <Input
                  id="url"
                  value={formData.url || ''}
                  onChange={(e) => handleInputChange('url', e.target.value)}
                  placeholder="http://localhost:3000/sse"
                />
              </div>

              <div>
                <Label htmlFor="timeout">{t('mcp.timeout')}</Label>
                <Input
                  id="timeout"
                  type="number"
                  value={formData.timeout || 10}
                  onChange={(e) =>
                    handleInputChange('timeout', parseInt(e.target.value) || 10)
                  }
                  placeholder="10"
                />
              </div>

              <div>
                <Label>{t('mcp.headers')}</Label>
                <div className="space-y-2 mt-2">
                  {Object.entries(formData.headers || {}).map(
                    ([key, value]) => (
                      <div key={key} className="flex items-center space-x-2">
                        <Input
                          value={key}
                          onChange={(e) =>
                            updateObjectItem(
                              'headers',
                              key,
                              e.target.value,
                              value,
                            )
                          }
                          placeholder={t('mcp.keyName')}
                          className="flex-1"
                        />
                        <Input
                          value={value}
                          onChange={(e) =>
                            updateObjectItem(
                              'headers',
                              key,
                              key,
                              e.target.value,
                            )
                          }
                          placeholder={t('mcp.value')}
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => removeObjectItem('headers', key)}
                        >
                          <TrashIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    ),
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => addObjectItem('headers')}
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    {t('mcp.addHeader')}
                  </Button>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onFormCancel}>
          {t('common.cancel')}
        </Button>
        <Button type="submit" disabled={loading}>
          {loading ? t('common.saving') : t('common.save')}
        </Button>
      </div>
    </form>
  );
}
