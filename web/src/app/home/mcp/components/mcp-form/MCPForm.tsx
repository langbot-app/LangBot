import React, {
  type ReactNode,
  useState,
  useEffect,
  useRef,
  forwardRef,
  useImperativeHandle,
} from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Braces, Loader2, Trash2, Wrench, XCircle } from 'lucide-react';
import { Resolver, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
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
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import MCPReadme from '@/app/home/mcp/components/mcp-form/MCPReadme';
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
import { BoxUnavailableNotice } from '@/app/home/components/BoxUnavailableNotice';
import { useBoxStatus } from '@/app/infra/hooks/useBoxStatus';

function StatusDisplay({
  testing,
  runtimeInfo,
  t,
}: {
  testing: boolean;
  runtimeInfo: MCPServerRuntimeInfo;
  t: TFunction;
}) {
  if (testing) {
    return (
      <div className="flex items-center gap-2 text-blue-600">
        <Loader2 className="size-5 animate-spin" />
        <span className="font-medium">{t('mcp.testing')}</span>
      </div>
    );
  }

  // CONNECTING, or any not-yet-resolved status (initial/null while the box is
  // still bringing the session up) — show "connecting" rather than failing.
  if (
    runtimeInfo.status === MCPSessionStatus.CONNECTING ||
    (runtimeInfo.status !== MCPSessionStatus.ERROR &&
      runtimeInfo.error_phase !== 'box_unavailable')
  ) {
    return (
      <div className="flex items-center gap-2 text-blue-600">
        <Loader2 className="size-5 animate-spin" />
        <span className="font-medium">{t('mcp.connecting')}</span>
      </div>
    );
  }

  // Stdio MCP refused because Box is disabled / unreachable. The backend
  // marks the phase so we can show a localized, actionable message instead
  // of the raw "box_disabled_in_config" / "box_unavailable" marker.
  if (runtimeInfo.error_phase === 'box_unavailable') {
    const isDisabledByConfig =
      runtimeInfo.error_message === 'box_disabled_in_config';
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-red-600">
          <XCircle className="size-5" />
          <span className="font-medium">{t('mcp.connectionFailed')}</span>
        </div>
        <div className="pl-7 text-sm text-red-500 space-y-0.5">
          <div>
            {isDisabledByConfig
              ? t('mcp.boxDisabledStdioRefused')
              : t('mcp.boxUnavailableStdioRefused')}
          </div>
          <div className="text-muted-foreground">
            {t('mcp.boxStdioRefusedSuggestion')}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 text-red-600">
        <XCircle className="size-5" />
        <span className="font-medium">{t('mcp.connectionFailed')}</span>
      </div>
      {runtimeInfo.error_message && (
        <div className="pl-7 text-sm text-red-500">
          {runtimeInfo.error_message}
        </div>
      )}
    </div>
  );
}

type ToolParameter = {
  name: string;
  type?: string;
  description?: string;
  required?: boolean;
};

function getToolParameters(parameters?: object): ToolParameter[] {
  if (!parameters || typeof parameters !== 'object') return [];

  const schema = parameters as {
    properties?: Record<
      string,
      { type?: string; description?: string; title?: string }
    >;
    required?: string[];
  };

  if (schema.properties && typeof schema.properties === 'object') {
    const required = new Set(schema.required ?? []);
    return Object.entries(schema.properties).map(([name, parameter]) => ({
      name,
      type: parameter?.type,
      description: parameter?.description || parameter?.title,
      required: required.has(name),
    }));
  }

  return Object.keys(parameters).map((name) => ({ name }));
}

function ToolsList({ tools, t }: { tools: MCPTool[]; t: TFunction }) {
  return (
    <div className="grid gap-3 pb-6 xl:grid-cols-2">
      {tools.map((tool, index) => {
        const parameters = getToolParameters(tool.parameters);
        const visibleParameters = parameters.slice(0, 4);
        const hiddenParameterCount =
          parameters.length - visibleParameters.length;

        return (
          <div
            key={`${tool.name}-${index}`}
            className="rounded-lg border bg-background p-4 transition-colors hover:border-primary/40 hover:bg-muted/20"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Wrench className="size-4" />
              </div>
              <div className="min-w-0 flex-1 space-y-3">
                <div className="min-w-0 space-y-1">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="truncate font-mono text-sm font-semibold">
                      {tool.name}
                    </span>
                    <Badge variant="secondary" className="h-5 shrink-0 px-1.5">
                      #{index + 1}
                    </Badge>
                  </div>
                  <p className="line-clamp-4 text-xs leading-relaxed text-muted-foreground">
                    {tool.description || t('market.noDescription')}
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                    <Braces className="size-3.5" />
                    <span>
                      {t('mcp.parameterCount', {
                        count: parameters.length,
                      })}
                    </span>
                  </div>

                  {visibleParameters.length > 0 ? (
                    <div className="flex flex-wrap gap-1.5">
                      {visibleParameters.map((parameter) => (
                        <span
                          key={parameter.name}
                          title={parameter.description || parameter.name}
                          className="inline-flex max-w-full items-center gap-1 rounded-md border bg-muted/40 px-2 py-1 text-xs"
                        >
                          <span className="truncate font-mono">
                            {parameter.name}
                          </span>
                          {parameter.type && (
                            <span className="shrink-0 text-muted-foreground">
                              {parameter.type}
                            </span>
                          )}
                          {parameter.required && (
                            <span className="shrink-0 text-destructive">*</span>
                          )}
                        </span>
                      ))}
                      {hiddenParameterCount > 0 && (
                        <span className="inline-flex items-center rounded-md border bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
                          +{hiddenParameterCount}
                        </span>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      {t('mcp.noParameters')}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RuntimePanel({
  isEditMode,
  mcpTesting,
  runtimeInfo,
  t,
}: {
  isEditMode: boolean;
  mcpTesting: boolean;
  runtimeInfo: MCPServerRuntimeInfo | null;
  t: TFunction;
}) {
  if (!isEditMode || !runtimeInfo) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
        {t('mcp.noToolsFound')}
      </div>
    );
  }

  const isConnected =
    !mcpTesting && runtimeInfo.status === MCPSessionStatus.CONNECTED;
  const tools = runtimeInfo.tools || [];

  return (
    <section className="space-y-4">
      {!isConnected && (
        <div className="rounded-md bg-muted/40 p-3">
          <StatusDisplay testing={mcpTesting} runtimeInfo={runtimeInfo} t={t} />
        </div>
      )}

      {isConnected && tools.length > 0 && <ToolsList tools={tools} t={t} />}

      {isConnected && tools.length === 0 && (
        <div className="flex min-h-[220px] items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
          {t('mcp.noToolsFound')}
        </div>
      )}
    </section>
  );
}

const getFormSchema = (t: TFunction) =>
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

export type MCPFormDraft = Partial<FormValues>;

interface MCPFormProps {
  initServerName?: string;
  initialDraft?: MCPFormDraft;
  onFormSubmit: () => void;
  onNewServerCreated: (serverName: string) => void;
  onDraftChange?: (draft: MCPFormDraft) => void;
  onDirtyChange?: (dirty: boolean) => void;
  onTestingChange?: (testing: boolean) => void;
  onRuntimeInfoChange?: (runtimeInfo: MCPServerRuntimeInfo | null) => void;
  /** Reported when the form cannot be saved because the current mode is
   * ``stdio`` and the Box sandbox is disabled/unavailable. Parents that
   * render the Save button outside this component should disable it. */
  onSaveBlockedChange?: (blocked: boolean) => void;
  layout?: 'stacked' | 'split';
  sideHeader?: ReactNode;
  sideFooter?: ReactNode;
}

export interface MCPFormHandle {
  testMcp: () => void;
  isTesting: boolean;
}

const MCPForm = forwardRef<MCPFormHandle, MCPFormProps>(function MCPForm(
  {
    initServerName,
    initialDraft,
    onFormSubmit,
    onNewServerCreated,
    onDraftChange,
    onDirtyChange,
    onTestingChange,
    onRuntimeInfoChange,
    onSaveBlockedChange,
    layout = 'stacked',
    sideHeader,
    sideFooter,
  },
  ref,
) {
  const { t } = useTranslation();
  const formSchema = getFormSchema(t);
  const isEditMode = !!initServerName;
  const initialDraftRef = useRef(initialDraft);

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
      ...initialDraftRef.current,
    },
  });

  const isInitializing = useRef(true);
  const [extraArgs, setExtraArgs] = useState<
    { key: string; type: 'string' | 'number' | 'boolean'; value: string }[]
  >([]);
  const [stdioArgs, setStdioArgs] = useState<{ value: string }[]>([]);
  const [mcpTesting, setMcpTesting] = useState(false);
  const [runtimeInfo, setRuntimeInfo] = useState<MCPServerRuntimeInfo | null>(
    null,
  );
  // README markdown captured from LangBot Space at install time, surfaced in
  // the Docs tab of the detail panel. Empty for manually-created servers.
  const [readme, setReadme] = useState<string>('');
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const watchMode = form.watch('mode');
  const {
    available: boxAvailable,
    hint: boxHint,
    reason: boxReason,
  } = useBoxStatus();
  // stdio mode requires the Box sandbox at runtime. If the user picks
  // stdio while Box is disabled / unreachable, the server would refuse
  // to start anyway — block creation upfront so they aren't surprised
  // by an immediate "Connection failed" on the detail page.
  const stdioBlockedByBox = watchMode === 'stdio' && !boxAvailable;

  const { isDirty } = form.formState;
  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  useEffect(() => {
    onSaveBlockedChange?.(stdioBlockedByBox);
  }, [stdioBlockedByBox, onSaveBlockedChange]);

  useEffect(() => {
    onTestingChange?.(mcpTesting);
  }, [mcpTesting, onTestingChange]);

  useEffect(() => {
    onRuntimeInfoChange?.(runtimeInfo);
  }, [onRuntimeInfoChange, runtimeInfo]);

  useImperativeHandle(
    ref,
    () => ({
      testMcp: () => testMcp(),
      isTesting: mcpTesting,
    }),
    // testMcp now reads everything via form.getValues(), so it does not need
    // the latest stdioArgs/extraArgs closure — but keep mcpTesting so the
    // exposed isTesting flag stays accurate.
    [mcpTesting],
  );

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
        ...initialDraftRef.current,
      });
      setExtraArgs(initialDraftRef.current?.extra_args ?? []);
      setStdioArgs(initialDraftRef.current?.args ?? []);
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

  useEffect(() => {
    if (!onDraftChange || isEditMode) return;

    const subscription = form.watch((values) => {
      onDraftChange({
        ...values,
        extra_args: extraArgs,
        args: stdioArgs,
      } as MCPFormDraft);
    });

    return () => subscription.unsubscribe();
  }, [form, isEditMode, onDraftChange, extraArgs, stdioArgs]);

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
        name: server.name.replace(/__/g, '/'),
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
      form.reset(formValues);
      setRuntimeInfo(server.runtime_info ?? null);
      setReadme(server.readme ?? '');
    } catch (error) {
      console.error('Failed to load server:', error);
      toast.error(t('mcp.loadFailed'));
    }
  }

  async function handleFormSubmit(value: z.infer<typeof formSchema>) {
    // Belt-and-suspenders: even though the Save button is disabled when
    // stdio is unselectable, intercept programmatic submits too.
    if (value.mode === 'stdio' && !boxAvailable) {
      toast.error(t('mcp.stdioBlockedByBoxToast'));
      return;
    }
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
              headers,
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
              headers,
              timeout: value.timeout,
            },
          };
        }
      } else {
        const env: Record<string, string> = {};
        value.extra_args?.forEach((arg) => {
          env[arg.key] = String(arg.value);
        });

        serverConfig = {
          name: value.name,
          mode: 'stdio',
          enable: true,
          extra_args: {
            command: value.command!,
            args: value.args?.map((arg) => arg.value) || [],
            env,
          },
        };
      }

      if (isEditMode && initServerName) {
        await httpClient.updateMCPServer(initServerName, serverConfig);
        toast.success(t('mcp.updateSuccess'));
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
      // Read every field via form.getValues() rather than the captured
      // `stdioArgs` / `extraArgs` state. testMcp() is invoked through an
      // imperative handle (formRef.current.testMcp()) whose closure is only
      // refreshed when [mcpTesting] changes, so reading the React state here
      // would use a stale snapshot — on the detail page that snapshot is the
      // empty initial [], which dropped stdio args entirely and launched
      // `uvx` with no package (exit 2 / "Connection closed", no detail).
      // The form values are kept in sync on every edit and on load, so they
      // are always current.
      const formExtraArgs = form.getValues('extra_args') ?? [];
      const formStdioArgs = form.getValues('args') ?? [];
      let extraArgsData:
        | MCPServerExtraArgsSSE
        | MCPServerExtraArgsHttp
        | MCPServerExtraArgsStdio;

      if (mode === 'sse') {
        extraArgsData = {
          url: form.getValues('url')!,
          timeout: form.getValues('timeout'),
          headers: Object.fromEntries(
            formExtraArgs.map((arg) => [arg.key, arg.value]),
          ),
          ssereadtimeout: form.getValues('ssereadtimeout'),
        };
      } else if (mode === 'http') {
        extraArgsData = {
          url: form.getValues('url')!,
          timeout: form.getValues('timeout'),
          headers: Object.fromEntries(
            formExtraArgs.map((arg) => [arg.key, arg.value]),
          ),
        };
      } else {
        extraArgsData = {
          command: form.getValues('command')!,
          args: formStdioArgs.map((arg) => arg.value),
          env: Object.fromEntries(
            formExtraArgs.map((arg) => [arg.key, arg.value]),
          ),
        };
      }

      const { task_id } = await httpClient.testMCPServer('_', {
        name: form.getValues('name'),
        mode,
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

  const configSection = (
    <Card>
      <CardHeader>
        <CardTitle>
          {isEditMode ? t('mcp.editServer') : t('mcp.createServer')}
        </CardTitle>
        <CardDescription>{t('mcp.extraParametersDescription')}</CardDescription>
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
                  <SelectItem value="stdio" disabled={!boxAvailable}>
                    {t('mcp.stdio')}
                    {!boxAvailable && (
                      <span className="ml-2 text-xs text-muted-foreground">
                        ({t('mcp.boxRequired')})
                      </span>
                    )}
                  </SelectItem>
                  <SelectItem value="sse">{t('mcp.sse')}</SelectItem>
                </SelectContent>
              </Select>
              {stdioBlockedByBox && (
                <BoxUnavailableNotice
                  hint={boxHint}
                  reason={boxReason}
                  className="mt-2"
                />
              )}
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
                      onChange={(e) => field.onChange(Number(e.target.value))}
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
                        onChange={(e) => field.onChange(Number(e.target.value))}
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
                      onChange={(e) => updateStdioArg(index, e.target.value)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-red-500 hover:text-red-600"
                      onClick={() => removeStdioArg(index)}
                    >
                      <Trash2 className="size-5" />
                    </Button>
                  </div>
                ))}
                <Button type="button" variant="outline" onClick={addStdioArg}>
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
                  onChange={(e) => updateExtraArg(index, 'key', e.target.value)}
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
                  <Trash2 className="size-5" />
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
  );

  const runtimePanel = (
    <RuntimePanel
      isEditMode={isEditMode}
      mcpTesting={mcpTesting}
      runtimeInfo={runtimeInfo}
      t={t}
    />
  );

  // In edit mode the right side shows a tablist switching between the live
  // Tools list and the Docs (README captured from LangBot Space at install).
  // Create mode has neither, so it falls back to the bare runtime placeholder.
  // The tool count lives in the tab label (only when connected); the panel
  // body itself no longer repeats a title/subtitle.
  const toolsConnected =
    !mcpTesting && runtimeInfo?.status === MCPSessionStatus.CONNECTED;
  const toolsCount = runtimeInfo?.tools?.length ?? 0;
  const toolsTabLabel = toolsConnected
    ? `${t('mcp.tabTools')} ${toolsCount}`
    : t('mcp.tabTools');

  const detailPanel = isEditMode ? (
    <Tabs defaultValue="tools" className="flex h-full min-h-0 flex-col">
      <TabsList>
        <TabsTrigger value="docs" className="flex-none px-4">
          {t('mcp.tabDocs')}
        </TabsTrigger>
        <TabsTrigger value="tools" className="flex-none px-4">
          {toolsTabLabel}
        </TabsTrigger>
      </TabsList>
      <TabsContent value="docs" className="mt-4 min-h-0 flex-1 overflow-y-auto">
        <MCPReadme readme={readme} />
      </TabsContent>
      <TabsContent
        value="tools"
        className="mt-4 min-h-0 flex-1 overflow-y-auto"
      >
        {runtimePanel}
      </TabsContent>
    </Tabs>
  ) : (
    runtimePanel
  );

  if (layout === 'split') {
    return (
      <Form {...form}>
        <form
          id="mcp-form"
          onSubmit={form.handleSubmit(handleFormSubmit)}
          className="flex h-full min-h-0 max-w-full flex-col gap-6 overflow-y-auto lg:flex-row lg:overflow-hidden"
        >
          <div className="space-y-5 pb-6 lg:min-h-0 lg:w-[360px] lg:flex-shrink-0 lg:overflow-y-auto lg:overflow-x-hidden xl:w-[400px]">
            {sideHeader}
            {configSection}
            {sideFooter}
          </div>
          <div className="hidden w-px shrink-0 bg-border lg:block" />
          <div className="min-w-0 flex-1 pb-6 lg:min-h-0 lg:overflow-y-auto lg:overflow-x-hidden">
            {detailPanel}
          </div>
        </form>
      </Form>
    );
  }

  return (
    <Form {...form}>
      <form
        id="mcp-form"
        onSubmit={form.handleSubmit(handleFormSubmit)}
        className="space-y-5"
      >
        {sideHeader}
        {detailPanel}
        {configSection}
        {sideFooter}
      </form>
    </Form>
  );
});

export default MCPForm;
