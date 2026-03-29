'use client';

import React, {
  useState,
  useEffect,
  useRef,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { useTranslation } from 'react-i18next';
import { Resolver, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import {
  MCPServerRuntimeInfo,
  MCPTool,
  MCPServer,
  MCPSessionStatus,
  MCPServerExtraArgsSSE,
  MCPServerExtraArgsHttp,
  MCPServerExtraArgsStdio,
} from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';

// Status display for test / connecting / error states
function StatusDisplay({
  testing,
  runtimeInfo,
  t,
}: {
  testing: boolean;
  runtimeInfo: MCPServerRuntimeInfo;
  t: (key: string) => string;
}) {
  if (testing) {
    return (
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
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
        <span className="font-medium">{t('mcp.testing')}</span>
      </div>
    );
  }

  if (runtimeInfo.status === MCPSessionStatus.CONNECTING) {
    return (
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
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
        <span className="font-medium">{t('mcp.connecting')}</span>
      </div>
    );
  }

  return (
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
      {runtimeInfo.error_message && (
        <div className="text-sm text-red-500 pl-7">
          {runtimeInfo.error_message}
        </div>
      )}
    </div>
  );
}

// Tools list component
function ToolsList({ tools }: { tools: MCPTool[] }) {
  return (
    <div className="space-y-2 max-h-[300px] overflow-y-auto">
      {tools.map((tool, index) => (
        <Card key={index} className="py-3 shadow-none">
          <CardHeader>
            <CardTitle className="text-sm">{tool.name}</CardTitle>
            {tool.description && (
              <CardDescription className="text-xs">
                {tool.description}
              </CardDescription>
            )}
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

const getFormSchema = (t: (key: string) => string) =>
  z
    .object({
      name: z
        .string({ required_error: t('mcp.nameRequired') })
        .min(1, { message: t('mcp.nameRequired') }),
      mode: z.enum(['sse', 'stdio', 'http']),
      timeout: z
        .number({ invalid_type_error: t('mcp.timeoutMustBeNumber') })
        .positive({ message: t('mcp.timeoutMustBePositive') })
        .default(30),
      ssereadtimeout: z
        .number({ invalid_type_error: t('mcp.sseTimeoutMustBeNumber') })
        .positive({ message: t('mcp.timeoutMustBePositive') })
        .default(300),
      url: z.string().optional(),
      command: z.string().optional(),
      args: z.array(z.object({ value: z.string() })).optional(),
      extra_args: z
        .array(
          z.object({
            key: z.string(),
            type: z.enum(['string', 'number', 'boolean']),
            value: z.string(),
          }),
        )
        .optional(),
    })
    .superRefine((data, ctx) => {
      if (data.mode === 'sse' || data.mode === 'http') {
        if (!data.url || data.url.length === 0) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: t('mcp.urlRequired'),
            path: ['url'],
          });
        }
      } else if (data.mode === 'stdio') {
        if (!data.command || data.command.length === 0) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: t('mcp.commandRequired'),
            path: ['command'],
          });
        }
      }
    });

type FormValues = z.infer<ReturnType<typeof getFormSchema>> & {
  timeout: number;
  ssereadtimeout: number;
};

interface MCPFormProps {
  initServerName?: string;
  onFormSubmit: () => void;
  onNewServerCreated: (serverName: string) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onTestingChange?: (testing: boolean) => void;
}

// Handle exposed to parent via ref
export interface MCPFormHandle {
  testMcp: () => void;
  isTesting: boolean;
}

const MCPForm = forwardRef<MCPFormHandle, MCPFormProps>(function MCPForm(
  {
    initServerName,
    onFormSubmit,
    onNewServerCreated,
    onDirtyChange,
    onTestingChange,
  },
  ref,
) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);
  const isEditMode = !!initServerName;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema) as unknown as Resolver<FormValues>,
    defaultValues: {
      name: '',
      mode: 'sse',
      url: '',
      command: '',
      args: [],
      timeout: 30,
      ssereadtimeout: 300,
      extra_args: [],
    },
  });

  // Track whether initial data loading is complete (to avoid marking form dirty)
  const isInitializing = useRef(true);

  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);
  const [stdioArgs, setStdioArgs] = useState<{ value: string }[]>([]);
  const [mcpTesting, setMcpTesting] = useState(false);
  const [runtimeInfo, setRuntimeInfo] = useState<MCPServerRuntimeInfo | null>(
    null,
  );
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const watchMode = form.watch('mode');

  // Notify parent when dirty state changes
  const { isDirty } = form.formState;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  // Notify parent when testing state changes
  useEffect(() => {
    onTestingChange?.(mcpTesting);
  }, [mcpTesting, onTestingChange]);

  // Expose test action and testing state to parent
  useImperativeHandle(
    ref,
    () => ({
      testMcp: () => testMcp(),
      isTesting: mcpTesting,
    }),
    [mcpTesting],
  );

  // Load server data
  useEffect(() => {
    isInitializing.current = true;
    if (isEditMode && initServerName) {
      loadServerForEdit(initServerName).finally(() => {
        isInitializing.current = false;
      });
    } else {
      form.reset({
        name: '',
        mode: 'sse',
        url: '',
        command: '',
        args: [],
        timeout: 30,
        ssereadtimeout: 300,
        extra_args: [],
      });
      setExtraArgs([]);
      setStdioArgs([]);
      setRuntimeInfo(null);
      isInitializing.current = false;
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [initServerName]);

  // Poll for updates when runtime_info status is CONNECTING
  useEffect(() => {
    if (
      !isEditMode ||
      !initServerName ||
      !runtimeInfo ||
      runtimeInfo.status !== MCPSessionStatus.CONNECTING
    ) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    if (!pollingIntervalRef.current) {
      pollingIntervalRef.current = setInterval(() => {
        loadServerForEdit(initServerName);
      }, 3000);
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [isEditMode, initServerName, runtimeInfo?.status]);

  async function loadServerForEdit(serverName: string) {
    try {
      const resp = await httpClient.getMCPServer(serverName);
      const server = resp.server ?? resp;

      const formValues: FormValues = {
        name: server.name,
        mode: server.mode,
        url: '',
        command: '',
        args: [],
        timeout: 30,
        ssereadtimeout: 300,
        extra_args: [],
      };

      let newExtraArgs: {
        key: string;
        type: 'string' | 'number' | 'boolean';
        value: string;
      }[] = [];
      let newStdioArgs: { value: string }[] = [];

      if (server.mode === 'sse' || server.mode === 'http') {
        formValues.url = server.extra_args.url;
        formValues.timeout = server.extra_args.timeout;

        if (server.mode === 'sse') {
          formValues.ssereadtimeout = server.extra_args.ssereadtimeout;
        }

        if (server.extra_args.headers) {
          newExtraArgs = Object.entries(server.extra_args.headers).map(
            ([key, value]) => ({
              key,
              type: 'string' as const,
              value: String(value),
            }),
          );
          formValues.extra_args = newExtraArgs;
        }
      } else if (server.mode === 'stdio') {
        formValues.command = server.extra_args.command;
        newStdioArgs = (server.extra_args.args || []).map((arg: string) => ({
          value: arg,
        }));
        formValues.args = newStdioArgs;

        if (server.extra_args.env) {
          newExtraArgs = Object.entries(server.extra_args.env).map(
            ([key, value]) => ({
              key,
              type: 'string' as const,
              value: String(value),
            }),
          );
          formValues.extra_args = newExtraArgs;
        }
      }

      setExtraArgs(newExtraArgs);
      setStdioArgs(newStdioArgs);

      // Use form.reset so isDirty stays false after initial load
      form.reset(formValues);

      if (server.runtime_info) {
        setRuntimeInfo(server.runtime_info);
      } else {
        setRuntimeInfo(null);
      }
    } catch (error) {
      console.error('Failed to load server:', error);
      toast.error(t('mcp.loadFailed'));
    }
  }

  async function handleFormSubmit(value: z.infer<typeof formSchema>) {
    try {
      let serverConfig: MCPServer;

      if (value.mode === 'sse' || value.mode === 'http') {
        const headers: Record<string, string> = {};
        value.extra_args?.forEach((arg) => {
          headers[arg.key] = String(arg.value);
        });

        if (value.mode === 'sse') {
          serverConfig = {
            name: value.name,
            mode: 'sse',
            enable: true,
            extra_args: {
              url: value.url!,
              headers: headers,
              timeout: value.timeout,
              ssereadtimeout: value.ssereadtimeout,
            },
          };
        } else {
          serverConfig = {
            name: value.name,
            mode: 'http',
            enable: true,
            extra_args: {
              url: value.url!,
              headers: headers,
              timeout: value.timeout,
            },
          };
        }
      } else {
        const env: Record<string, string> = {};
        value.extra_args?.forEach((arg) => {
          env[arg.key] = String(arg.value);
        });
        const args = value.args?.map((arg) => arg.value) || [];

        serverConfig = {
          name: value.name,
          mode: 'stdio',
          enable: true,
          extra_args: {
            command: value.command!,
            args: args,
            env: env,
          },
        };
      }

      if (isEditMode && initServerName) {
        await httpClient.updateMCPServer(initServerName, serverConfig);
        toast.success(t('mcp.updateSuccess'));
        // Reset dirty baseline to current values
        form.reset(form.getValues());
        onFormSubmit();
      } else {
        await httpClient.createMCPServer(serverConfig);
        toast.success(t('mcp.createSuccess'));
        onNewServerCreated(value.name);
      }
    } catch (error) {
      console.error('Failed to save MCP server:', error);
      const errMsg = (error as CustomApiError).msg || '';
      toast.error(
        (isEditMode ? t('mcp.updateFailed') : t('mcp.createFailed')) + errMsg,
      );
    }
  }

  async function testMcp() {
    setMcpTesting(true);

    try {
      const mode = form.getValues('mode');
      let extraArgsData:
        | MCPServerExtraArgsSSE
        | MCPServerExtraArgsHttp
        | MCPServerExtraArgsStdio;

      if (mode === 'sse') {
        extraArgsData = {
          url: form.getValues('url')!,
          timeout: form.getValues('timeout'),
          headers: Object.fromEntries(
            extraArgs.map((arg) => [arg.key, arg.value]),
          ),
          ssereadtimeout: form.getValues('ssereadtimeout'),
        };
      } else if (mode === 'http') {
        extraArgsData = {
          url: form.getValues('url')!,
          timeout: form.getValues('timeout'),
          headers: Object.fromEntries(
            extraArgs.map((arg) => [arg.key, arg.value]),
          ),
        };
      } else {
        extraArgsData = {
          command: form.getValues('command')!,
          args: stdioArgs.map((arg) => arg.value),
          env: Object.fromEntries(extraArgs.map((arg) => [arg.key, arg.value])),
        };
      }

      const { task_id } = await httpClient.testMCPServer('_', {
        name: form.getValues('name'),
        mode: mode,
        enable: true,
        extra_args: extraArgsData,
      } as MCPServer);

      if (!task_id) {
        throw new Error(t('mcp.noTaskId'));
      }

      const interval = setInterval(async () => {
        try {
          const taskResp = await httpClient.getAsyncTask(task_id);

          if (taskResp.runtime?.done) {
            clearInterval(interval);
            setMcpTesting(false);

            if (taskResp.runtime.exception) {
              const errorMsg =
                taskResp.runtime.exception || t('mcp.unknownError');
              toast.error(`${t('mcp.testError')}: ${errorMsg}`);
              setRuntimeInfo({
                status: MCPSessionStatus.ERROR,
                error_message: errorMsg,
                tool_count: 0,
                tools: [],
              });
            } else {
              if (isEditMode) {
                await loadServerForEdit(form.getValues('name'));
              }
              toast.success(t('mcp.testSuccess'));
            }
          }
        } catch (err) {
          clearInterval(interval);
          setMcpTesting(false);
          const errorMsg =
            (err as CustomApiError).msg || t('mcp.getTaskFailed');
          toast.error(`${t('mcp.testError')}: ${errorMsg}`);
        }
      }, 1000);
    } catch (err) {
      setMcpTesting(false);
      const errorMsg = (err as Error).message || t('mcp.unknownError');
      toast.error(`${t('mcp.testError')}: ${errorMsg}`);
    }
  }

  const addExtraArg = () => {
    const newArgs = [
      ...extraArgs,
      { key: '', type: 'string' as const, value: '' },
    ];
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs, {
      shouldDirty: !isInitializing.current,
    });
  };

  const removeExtraArg = (index: number) => {
    const newArgs = extraArgs.filter((_, i) => i !== index);
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs, {
      shouldDirty: !isInitializing.current,
    });
  };

  const updateExtraArg = (
    index: number,
    field: 'key' | 'type' | 'value',
    value: string,
  ) => {
    const newArgs = [...extraArgs];
    newArgs[index] = { ...newArgs[index], [field]: value };
    setExtraArgs(newArgs);
    form.setValue('extra_args', newArgs, {
      shouldDirty: !isInitializing.current,
    });
  };

  const addStdioArg = () => {
    const newArgs = [...stdioArgs, { value: '' }];
    setStdioArgs(newArgs);
    form.setValue('args', newArgs, { shouldDirty: !isInitializing.current });
  };

  const removeStdioArg = (index: number) => {
    const newArgs = stdioArgs.filter((_, i) => i !== index);
    setStdioArgs(newArgs);
    form.setValue('args', newArgs, { shouldDirty: !isInitializing.current });
  };

  const updateStdioArg = (index: number, value: string) => {
    const newArgs = [...stdioArgs];
    newArgs[index] = { value };
    setStdioArgs(newArgs);
    form.setValue('args', newArgs, { shouldDirty: !isInitializing.current });
  };

  return (
    <Form {...form}>
      <form
        id="mcp-form"
        onSubmit={form.handleSubmit(handleFormSubmit)}
        className="space-y-6"
      >
        {/* Runtime info: status + tools (edit mode only) */}
        {isEditMode && runtimeInfo && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{t('mcp.title')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {(mcpTesting ||
                runtimeInfo.status !== MCPSessionStatus.CONNECTED) && (
                <div className="p-3 rounded-lg border">
                  <StatusDisplay
                    testing={mcpTesting}
                    runtimeInfo={runtimeInfo}
                    t={t}
                  />
                </div>
              )}

              {!mcpTesting &&
                runtimeInfo.status === MCPSessionStatus.CONNECTED &&
                runtimeInfo.tools?.length > 0 && (
                  <>
                    <div className="text-sm font-medium">
                      {t('mcp.toolCount', {
                        count: runtimeInfo.tools?.length || 0,
                      })}
                    </div>
                    <ToolsList tools={runtimeInfo.tools} />
                  </>
                )}
            </CardContent>
          </Card>
        )}

        {/* Server configuration */}
        <Card>
          <CardHeader>
            <CardTitle>
              {isEditMode ? t('mcp.editServer') : t('mcp.createServer')}
            </CardTitle>
            <CardDescription>
              {t('mcp.extraParametersDescription')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {t('mcp.name')}
                    <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Input {...field} disabled={isEditMode} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="mode"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t('mcp.serverMode')}</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={t('mcp.selectMode')} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="http">{t('mcp.http')}</SelectItem>
                      <SelectItem value="stdio">{t('mcp.stdio')}</SelectItem>
                      <SelectItem value="sse">{t('mcp.sse')}</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {(watchMode === 'sse' || watchMode === 'http') && (
              <>
                <FormField
                  control={form.control}
                  name="url"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {t('mcp.url')}
                        <span className="text-destructive">*</span>
                      </FormLabel>
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
                        <Input
                          type="number"
                          placeholder={t('mcp.timeout')}
                          {...field}
                          onChange={(e) =>
                            field.onChange(Number(e.target.value))
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {watchMode === 'sse' && (
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
                            onChange={(e) =>
                              field.onChange(Number(e.target.value))
                            }
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </>
            )}

            {watchMode === 'stdio' && (
              <>
                <FormField
                  control={form.control}
                  name="command"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        {t('mcp.command')}
                        <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormItem>
                  <FormLabel>{t('mcp.args')}</FormLabel>
                  <div className="space-y-2">
                    {stdioArgs.map((arg, index) => (
                      <div key={index} className="flex gap-2">
                        <Input
                          placeholder={t('mcp.args')}
                          value={arg.value}
                          onChange={(e) =>
                            updateStdioArg(index, e.target.value)
                          }
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="shrink-0 text-red-500 hover:text-red-600"
                          onClick={() => removeStdioArg(index)}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 24 24"
                            fill="currentColor"
                            className="w-5 h-5"
                          >
                            <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z" />
                          </svg>
                        </Button>
                      </div>
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={addStdioArg}
                    >
                      {t('mcp.addArgument')}
                    </Button>
                  </div>
                </FormItem>
              </>
            )}

            <FormItem>
              <FormLabel>
                {watchMode === 'sse' || watchMode === 'http'
                  ? t('mcp.headers')
                  : t('mcp.env')}
              </FormLabel>
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
                    <Input
                      placeholder={t('models.value')}
                      value={arg.value}
                      onChange={(e) =>
                        updateExtraArg(index, 'value', e.target.value)
                      }
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-red-500 hover:text-red-600"
                      onClick={() => removeExtraArg(index)}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                        className="w-5 h-5"
                      >
                        <path d="M7 4V2H17V4H22V6H20V21C20 21.5523 19.5523 22 19 22H5C4.44772 22 4 21.5523 4 21V6H2V4H7ZM6 6V20H18V6H6ZM9 9H11V17H9V9ZM13 9H15V17H13V9Z" />
                      </svg>
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" onClick={addExtraArg}>
                  {watchMode === 'sse' || watchMode === 'http'
                    ? t('mcp.addHeader')
                    : t('mcp.addEnvVar')}
                </Button>
              </div>
              <FormDescription>
                {t('mcp.extraParametersDescription')}
              </FormDescription>
              <FormMessage />
            </FormItem>
          </CardContent>
        </Card>
      </form>
    </Form>
  );
});

export default MCPForm;
