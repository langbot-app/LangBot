'use client';
import PluginInstalledComponent, {
  PluginInstalledComponentRef,
} from '@/app/home/plugins/components/plugin-installed/PluginInstalledComponent';
import MarketPage from '@/app/home/plugins/components/plugin-market/PluginMarketComponent';
// import PluginSortDialog from '@/app/home/plugins/plugin-sort/PluginSortDialog';
import MCPComponent, {
  MCPComponentRef,
} from '@/app/home/plugins/mcp/MCPComponent';
import MCPServerComponent from '@/app/home/plugins/mcp-server/MCPServerComponent';
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
import React, { useState, useRef, useCallback, useEffect } from 'react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { PluginV4 } from '@/app/infra/entities/plugin';
import { systemInfo } from '@/app/infra/http/HttpClient';
import { ApiRespPluginSystemStatus } from '@/app/infra/entities/api';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select"

import { Resolver, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { DialogDescription } from '@radix-ui/react-dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

enum PluginInstallStatus {
  WAIT_INPUT = 'wait_input',
  ASK_CONFIRM = 'ask_confirm',
  INSTALLING = 'installing',
  ERROR = 'error',
}

export default function PluginConfigPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('installed');
  const [modalOpen, setModalOpen] = useState(false);
  const [installSource, setInstallSource] = useState<string>('local');
  const [installInfo, setInstallInfo] = useState<Record<string, any>>({}); // eslint-disable-line @typescript-eslint/no-explicit-any
  const [mcpSSEModalOpen, setMcpSSEModalOpen] = useState(false);
  const [pluginInstallStatus, setPluginInstallStatus] =
    useState<PluginInstallStatus>(PluginInstallStatus.WAIT_INPUT);
  const [installError, setInstallError] = useState<string | null>(null);
  const [githubURL, setGithubURL] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [pluginSystemStatus, setPluginSystemStatus] =
    useState<ApiRespPluginSystemStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const addExtraArg = () => {
    setExtraArgs([...extraArgs, { key: '', type: 'string', value: '' }]);
  };
  const getExtraArgSchema = (t: (key: string) => string) =>
    z
      .object({
        key: z.string().min(1, { message: t('models.keyNameRequired') }),
        type: z.enum(['string', 'number', 'boolean']),
        value: z.string(),
      })
      .superRefine((data, ctx) => {
        if (data.type === 'number' && isNaN(Number(data.value))) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: t('models.mustBeValidNumber'),
            path: ['value'],
          });
        }
        if (
          data.type === 'boolean' &&
          data.value !== 'true' &&
          data.value !== 'false'
        ) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: t('models.mustBeTrueOrFalse'),
            path: ['value'],
          });
        }
      });
  const removeExtraArg = (index: number) => {
    const newArgs = extraArgs.filter((_, i) => i !== index);
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };
  const getFormSchema = (t: (key: string) => string) =>
  z.object({
    name: z.string({ required_error: t('mcp.nameRequired') }),
    timeout: z
      .number({ invalid_type_error: t('mcp.timeoutMustBeNumber') })
      .nonnegative({ message: t('mcp.timeoutNonNegative') })
      .default(30),
    ssereadtimeout: z
      .number({ invalid_type_error: t('mcp.sseTimeoutMustBeNumber') })
      .nonnegative({ message: t('mcp.sseTimeoutNonNegative') })
      .default(300),
    url: z.string({ required_error: t('models.requestURLRequired') }),
    extra_args: z
      .array(
        z.object({
          key: z.string(),
          type: z.enum(['string', 'number', 'boolean']),
          value: z.string(),
        })
      )
      .optional(),
  });

const formSchema = getFormSchema(t);


type FormValues = z.infer<typeof formSchema> & {
  timeout: number;
  ssereadtimeout: number;
};

const form = useForm<FormValues>({
  resolver: zodResolver(formSchema) as unknown as Resolver<FormValues>,
  defaultValues: {
    name: '',
    url: '',
    timeout: 30,
    ssereadtimeout: 300,
    extra_args: [],
  },
});


  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);
  const updateExtraArg = (
    index: number,
    field: 'key' | 'type' | 'value',
    value: string,
  ) => {
    const newArgs = [...extraArgs];
    newArgs[index] = {
      ...newArgs[index],
      [field]: value,
    };
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs);
  };
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
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
  //这个是旧版本的测试github url，下面重写了一个新版本的watchTask函数，用来检测Mcp
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

  function watchTestMCPTask(taskId: number) {
  let alreadyHandled = false;
  console.log('Watching MCP test task:', taskId);

  const interval = setInterval(() => {
    httpClient.getAsyncTask(taskId).then((resp) => {
      console.log('task status:', resp);

      // 若任务已完成
      if (resp.runtime && resp.runtime.done) {
        clearInterval(interval);

        if (resp.runtime.exception) {
          // 任务失败
          toast.error(`测试失败: ${resp.runtime.exception}`);
        } else if (resp.runtime.result) {
          // 任务成功
          const result = resp.runtime.result as {
              status?: string;
              tools_count?: number;
              tools_names_lists?: string[];
              error?: string;
            };
        const names = result.tools_names_lists || [];

          if (!alreadyHandled) {
            alreadyHandled = true;
            const names = result.tools_names_lists || [];
            toast.success(`连接成功，找到 ${names.length} 个工具`);
            console.log('工具列表:', names);
          }
        } else {
          // 没结果但标记为完成
          toast.error('测试任务完成但未返回结果');
        }
      }
    }).catch((err) => {
      console.error('任务状态获取失败:', err);
      toast.error('获取任务状态失败');
      clearInterval(interval);
    });
  }, 1000);
}

  const pluginInstalledRef = useRef<PluginInstalledComponentRef>(null);
  const mcpComponentRef = useRef<MCPComponentRef>(null);
  const [mcpTesting, setMcpTesting] = useState(false);
  const [editingServerName, setEditingServerName] = useState<string | null>(
    null,
  );
  const [isEditMode, setIsEditMode] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // MCP测试结果状态
  const [mcpTestStatus, setMcpTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [mcpToolNames, setMcpToolNames] = useState<string[]>([]);
  const [mcpTestError, setMcpTestError] = useState<string>('');

  // 缓存每个服务器测试后的工具数量
  const [serverToolsCache, setServerToolsCache] = useState<Record<string, number>>({});

  // 强制清理 body 样式以修复 Dialog 关闭后点击失效的问题
  useEffect(() => {
    console.log('[Dialog Debug] States:', {
      mcpSSEModalOpen,
      modalOpen,
      showDeleteConfirmModal,
    });

    if (!mcpSSEModalOpen && !modalOpen && !showDeleteConfirmModal) {
      const cleanup = () => {
        
        document.body.style.removeProperty('pointer-events');
        document.body.style.removeProperty('overflow');

        
        if (document.body.style.pointerEvents === 'none') {
          document.body.style.pointerEvents = '';
        }
        if (document.body.style.overflow === 'hidden') {
          document.body.style.overflow = '';
        }

        console.log(
          '[Dialog Debug] After cleanup - body.style.pointerEvents:',
          document.body.style.pointerEvents,
        );
        console.log(
          '[Dialog Debug] After cleanup - body.style.overflow:',
          document.body.style.overflow,
        );

        // 检查计算后的样式
        const computedStyle = window.getComputedStyle(document.body);
        console.log(
          '[Dialog Debug] Computed pointerEvents:',
          computedStyle.pointerEvents,
        );
      };

      // 多次清理以确保覆盖 Radix 的设置
      cleanup();
      const timer1 = setTimeout(cleanup, 0);
      const timer2 = setTimeout(cleanup, 50);
      const timer3 = setTimeout(cleanup, 100);
      const timer4 = setTimeout(cleanup, 200);
      const timer5 = setTimeout(cleanup, 300);

      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
        clearTimeout(timer4);
        clearTimeout(timer5);
      };
    }
  }, [mcpSSEModalOpen, modalOpen, showDeleteConfirmModal]);

  
  useEffect(() => {
    const interval = setInterval(() => {
      if (!mcpSSEModalOpen && !modalOpen && !showDeleteConfirmModal) {
        if (document.body.style.pointerEvents === 'none') {
          console.log(
            '[Global Cleanup] Found stale pointer-events, cleaning...',
          );
          document.body.style.removeProperty('pointer-events');
          document.body.style.pointerEvents = '';
        }
      }
    }, 500);

    return () => clearInterval(interval);
  }, [mcpSSEModalOpen, modalOpen, showDeleteConfirmModal]);

  // MutationObserver：监视 body 的 style 变化
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (
          mutation.type === 'attributes' &&
          mutation.attributeName === 'style'
        ) {
          if (!mcpSSEModalOpen && !modalOpen && !showDeleteConfirmModal) {
            if (document.body.style.pointerEvents === 'none') {
              console.log(
                '[MutationObserver] Detected pointer-events being set to none, reverting...',
              );
              document.body.style.removeProperty('pointer-events');
              document.body.style.pointerEvents = '';
            }
          }
        }
      });
    });

    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['style'],
    });

    return () => observer.disconnect();
  }, [mcpSSEModalOpen, modalOpen, showDeleteConfirmModal]);

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

  async function deleteMCPServer() {
    if (!editingServerName) return;

    try {
      await httpClient.deleteMCPServer(editingServerName);
      toast.success(t('mcp.deleteSuccess'));

      // 关闭所有对话框
      setShowDeleteConfirmModal(false);
      setMcpSSEModalOpen(false);

      // 重置状态
      form.reset();
      setExtraArgs([]);
      setEditingServerName(null);
      setIsEditMode(false);

      // 刷新服务器列表
      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error('Failed to delete server:', error);
      toast.error(t('mcp.deleteFailed'));
    }
  }

  async function loadServerForEdit(serverName: string) {
    try {
      const resp = await httpClient.getMCPServer(serverName);
      const server = resp.server ?? resp; 
      console.log('Loaded server for edit:', server);

      
      form.setValue('name', server.name);
      form.setValue('url', server.extra_args?.url || '');
      form.setValue('timeout', server.extra_args?.timeout || 30);
      form.setValue('ssereadtimeout', server.extra_args?.ssereadtimeout || 300);

      
      if (server.extra_args?.headers) {
        const headers = Object.entries(server.extra_args.headers).map(
          ([key, value]) => ({
            key,
            type: 'string' as const,
            value: String(value),
          }),
        );
        setExtraArgs(headers);
        form.setValue('extra_args', headers);
      }

      
      setMcpTestStatus('testing');
      setMcpToolNames([]);
      setMcpTestError('');

      
      setEditingServerName(serverName);
      setIsEditMode(true);
      setMcpSSEModalOpen(true);

      
      try {
        const res = await httpClient.testMCPServer(server.name);
        if (res.task_id) {
          const taskId = res.task_id;

          
          const interval = setInterval(() => {
            httpClient.getAsyncTask(taskId).then((taskResp) => {
              console.log('Task response:', taskResp);

              if (taskResp.runtime && taskResp.runtime.done) {
                clearInterval(interval);

                console.log('Task completed. Runtime:', taskResp.runtime);
                console.log('Result:', taskResp.runtime.result);
                console.log('Exception:', taskResp.runtime.exception);

                if (taskResp.runtime.exception) {
                  
                  console.log('Test failed with exception');
                  setMcpTestStatus('failed');
                  setMcpToolNames([]);
                  setMcpTestError(taskResp.runtime.exception || '未知错误');
                } else if (taskResp.runtime.result) {
                  
                  try {
                    let result: {
                      status?: string;
                      tools_count?: number;
                      tools_names_lists?: string[];
                      error?: string;
                    };

                    
                    const rawResult: any = taskResp.runtime.result;
                    if (typeof rawResult === 'string') {
                      console.log('Result is string, parsing...');
                      result = JSON.parse(rawResult.replace(/'/g, '"'));
                    } else {
                      result = rawResult as typeof result;
                    }

                    console.log('Parsed result:', result);
                    console.log('tools_names_lists:', result.tools_names_lists);
                    console.log('tools_names_lists length:', result.tools_names_lists?.length);

                    if (result.tools_names_lists && result.tools_names_lists.length > 0) {
                      console.log('Test success with', result.tools_names_lists.length, 'tools');
                      setMcpTestStatus('success');
                      setMcpToolNames(result.tools_names_lists);
                      // 保存工具数量到缓存
                      setServerToolsCache(prev => ({
                        ...prev,
                        [server.name]: result.tools_names_lists!.length
                      }));
                    } else {
                      console.log('Test failed: no tools found');
                      setMcpTestStatus('failed');
                      setMcpToolNames([]);
                      setMcpTestError('未找到任何工具');
                    }
                  } catch (parseError) {
                    console.error('Failed to parse result:', parseError);
                    setMcpTestStatus('failed');
                    setMcpToolNames([]);
                    setMcpTestError('解析测试结果失败');
                  }
                } else {
                  // 没结果
                  console.log('Test failed: no result');
                  setMcpTestStatus('failed');
                  setMcpToolNames([]);
                  setMcpTestError('测试未返回结果');
                }
              }
            }).catch((err) => {
              console.error('获取任务状态失败:', err);
              clearInterval(interval);
              setMcpTestStatus('failed');
              setMcpToolNames([]);
              setMcpTestError(err.message || '获取任务状态失败');
            });
          }, 1000);
        } else {
          setMcpTestStatus('failed');
          setMcpToolNames([]);
          setMcpTestError('未获取到任务ID');
        }
      } catch (error) {
        console.error('Failed to test server:', error);
        setMcpTestStatus('failed');
        setMcpToolNames([]);
        setMcpTestError((error as Error).message || '测试连接时发生错误');
      }
    } catch (error) {
      console.error('Failed to load server:', error);
      toast.error(t('mcp.loadFailed'));
    }
  }

  async function handleFormSubmit(value: z.infer<typeof formSchema>) {
    const extraArgsObj: Record<string, string | number | boolean> = {};
    value.extra_args?.forEach(
      (arg: { key: string; type: string; value: string }) => {
        if (arg.type === 'number') {
          extraArgsObj[arg.key] = Number(arg.value);
        } else if (arg.type === 'boolean') {
          extraArgsObj[arg.key] = arg.value === 'true';
        } else {
          extraArgsObj[arg.key] = arg.value;
        }
      },
    );

    try {
      // 构造符合 MCPServerConfig 类型的数据
      const serverConfig = {
        name: value.name,
        mode: 'sse' as const,
        enable: true,
        url: value.url,
        headers: extraArgsObj as Record<string, string>,
        timeout: value.timeout,
        ssereadtimeout: value.ssereadtimeout,
      };

      if (isEditMode && editingServerName) {
        
        await httpClient.updateMCPServer(editingServerName, serverConfig);
        toast.success(t('mcp.updateSuccess'));
      } else {
        await httpClient.createMCPServer(serverConfig);
        toast.success(t('mcp.createSuccess'));
      }

      setMcpSSEModalOpen(false);

      form.reset();
      setExtraArgs([]);
      setEditingServerName(null);
      setIsEditMode(false);

      setRefreshKey((prev) => prev + 1);
    } catch (error) {
      console.error('Failed to save MCP server:', error);
      toast.error(isEditMode ? t('mcp.updateFailed') : t('mcp.createFailed'));
    }
  }

  function testMcp() {
    setMcpTesting(true);
    const extraArgsObj: Record<string, string | number | boolean> = {};
    form
      .getValues('extra_args')
      ?.forEach((arg: { key: string; type: string; value: string }) => {
        if (arg.type === 'number') {
          extraArgsObj[arg.key] = Number(arg.value);
        } else if (arg.type === 'boolean') {
          extraArgsObj[arg.key] = arg.value === 'true';
        } else {
          extraArgsObj[arg.key] = arg.value;
        }
      });
    httpClient
      .testMCPServer(form.getValues('name'))
      .then((res) => {
        console.log(res);
        toast.success(t('models.testSuccess'));
      })
      .catch(() => {
        toast.error(t('models.testError'));
      })
      .finally(() => {
        setMcpTesting(false);
      });
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

  const renderLoadingState = () => (
    <div className="flex flex-col items-center justify-center h-[60vh] pt-[10vh]">
      <p className="text-gray-500 dark:text-gray-400">
        {t('plugins.loadingStatus')}
      </p>
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
            <TabsTrigger
              value="mcp-servers"
              className="px-6 py-4 cursor-pointer"
            >
              {t('mcp.title')}
            </TabsTrigger>
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
                  {activeTab === 'mcp-servers'
                    ? t('mcp.add')
                    : t('plugins.install')}
                  <ChevronDownIcon className="ml-2 w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {activeTab === 'mcp-servers' ? (
                  <>
                    {/* <DropdownMenuItem
                      onClick={() => {
                        setActiveTab('mcp-market');
                        setMcpMarketInstallModalOpen(true);
                        setMcpInstallStatus(PluginInstallStatus.WAIT_INPUT);
                        setMcpInstallError(null);
                        setMcpGithubURL('');
                      }}
                    >
                      <PlusIcon className="w-4 h-4" />
                      {t('mcp.installFromGithub')}
                    </DropdownMenuItem> */}
                    <DropdownMenuItem
                      onClick={() => {
                        setActiveTab('mcp-servers');
                        setIsEditMode(false);
                        setEditingServerName(null);
                        form.reset();
                        setExtraArgs([]);
                        setMcpSSEModalOpen(true);
                      }}
                    >
                      <PlusIcon className="w-4 h-4" />
                      {t('mcp.createServer')}
                    </DropdownMenuItem>
                  </>
                ) : (
                  <>
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
                  </>
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
        <TabsContent value="mcp">
          <MCPComponent ref={mcpComponentRef} />
        </TabsContent>
        <TabsContent value="mcp-servers">
          <MCPServerComponent
            key={refreshKey}
            onEditServer={(serverName) => {
              loadServerForEdit(serverName);
            }}
            toolsCountCache={serverToolsCache}
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

      <div>
        <Dialog
          open={showDeleteConfirmModal}
          onOpenChange={setShowDeleteConfirmModal}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('mcp.confirmDeleteTitle')}</DialogTitle>
            </DialogHeader>
            <DialogDescription>
              {t('mcp.confirmDeleteServer')}
            </DialogDescription>
            <DialogFooter>
              <Button
                variant="destructive"
                onClick={() => {
                  deleteMCPServer();
                  setShowDeleteConfirmModal(false);
                }}
              >
                {t('common.confirm')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={mcpSSEModalOpen}
          onOpenChange={(open) => {
            setMcpSSEModalOpen(open);
            if (!open) {
              // 关闭对话框时重置编辑状态
              setIsEditMode(false);
              setEditingServerName(null);
              form.reset();
              setExtraArgs([]);
            }
          }}
        >
          
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                {isEditMode ? t('mcp.editServer') : t('mcp.createServer')}
              </DialogTitle>
            </DialogHeader>

            {/* 测试结果显示区域 - 仅在编辑模式显示 */}
            {isEditMode && (
              <div className="mb-4 p-3 rounded-lg border">
                {mcpTestStatus === 'testing' && (
                  <div className="flex items-center gap-2 text-blue-600">
                    <svg
                      className="w-5 h-5 animate-spin"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    <span className="font-medium">{t('mcp.testing')}</span>
                  </div>
                )}

                {mcpTestStatus === 'success' && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-green-600">
                      <svg
                        className="w-5 h-5"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <span className="font-medium">
                        {t('mcp.connectionSuccess')} - {mcpToolNames.length} {t('mcp.toolsFound')}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {mcpToolNames.map((toolName, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 text-xs rounded-md"
                        >
                          {toolName}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {mcpTestStatus === 'failed' && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-red-600">
                      <svg
                        className="w-5 h-5"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                      <span className="font-medium">{t('mcp.connectionFailed')}</span>
                    </div>
                    {mcpTestError && (
                      <div className="text-sm text-red-500 pl-7">
                        {mcpTestError}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(handleFormSubmit)}
                className="space-y-4"
              >
                <div className="space-y-4">
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('mcp.name')}</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="url"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('mcp.url')}</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="timeout"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('mcp.timeout')}</FormLabel>
                        <FormControl>
                          <Input {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="ssereadtimeout"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{t('mcp.sseTimeout')}</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            placeholder={t('mcp.sseTimeoutDescription')}
                            {...field}
                            onChange={(e) => field.onChange(Number(e.target.value))}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />


                  <FormItem>
                    <FormLabel>{t('models.extraParameters')}</FormLabel>
                    <div className="space-y-2">
                      {extraArgs.map((arg, index) => (
                        <div key={index} className="flex gap-2">
                          <Input
                            placeholder={t('models.keyName')}
                            value={arg.key}
                            onChange={(e) =>
                              updateExtraArg(index, 'key', e.target.value)
                            }
                          />
                          <Select
                            value={arg.type}
                            onValueChange={(value) =>
                              updateExtraArg(index, 'type', value)
                            }
                          >
                            <SelectTrigger className="w-[120px] bg-[#ffffff] dark:bg-[#2a2a2e]">
                              <SelectValue placeholder={t('models.type')} />
                            </SelectTrigger>
                            <SelectContent className="bg-[#ffffff] dark:bg-[#2a2a2e]">
                              <SelectItem value="string">
                                {t('models.string')}
                              </SelectItem>
                              <SelectItem value="number">
                                {t('models.number')}
                              </SelectItem>
                              <SelectItem value="boolean">
                                {t('models.boolean')}
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <Input
                            placeholder={t('models.value')}
                            value={arg.value}
                            onChange={(e) =>
                              updateExtraArg(index, 'value', e.target.value)
                            }
                          />
                          <button
                            type="button"
                            className="p-2 hover:bg-gray-100 rounded"
                            onClick={() => removeExtraArg(index)}
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              viewBox="0 0 24 24"
                              fill="currentColor"
                              className="w-5 h-5 text-red-500"
                            >
                              <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z"></path>
                            </svg>
                          </button>
                        </div>
                      ))}
                      <Button
                        type="button"
                        variant="outline"
                        onClick={addExtraArg}
                      >
                        {t('models.addParameter')}
                      </Button>
                    </div>
                    <FormDescription>
                      {t('mcp.extraParametersDescription')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>

                  <DialogFooter>
                    {isEditMode && (
                      <Button
                        type="button"
                        variant="destructive"
                        onClick={() => setShowDeleteConfirmModal(true)}
                      >
                        {t('common.delete')}
                      </Button>
                    )}

                    <Button type="submit">
                      {isEditMode ? t('common.save') : t('common.submit')}
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => testMcp()}
                      disabled={mcpTesting}
                    >
                      {t('common.test')}
                    </Button>

                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setMcpSSEModalOpen(false);
                        form.reset();
                        setExtraArgs([]);
                        setIsEditMode(false);
                        setEditingServerName(null);
                      }}
                    >
                      {t('common.cancel')}
                    </Button>
                  </DialogFooter>
                </div>
              </form>
            </Form>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
