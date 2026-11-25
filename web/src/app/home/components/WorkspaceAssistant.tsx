import {
  useEffect,
  useRef,
  useState,
  useId,
  Fragment,
  type ReactNode,
} from 'react';
import { createPortal } from 'react-dom';
import {
  Plus,
  Send,
  ChevronDown,
  LoaderCircle,
  Square,
  CircleAlert,
  QrCode,
} from 'lucide-react';
import QrCodeLoginDialog, {
  QrLoginPlatform,
} from './qrcode-login/QrCodeLoginDialog';
import {
  RiSparkling2Line,
  RiArrowUpSLine,
  RiCompass3Line,
  RiMagicLine,
  RiArrowRightUpLine,
} from '@remixicon/react';
import styles from './workspace-assistant.module.css';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import '@/styles/github-markdown.css';
import {
  backendClient,
  systemInfo,
  useCurrentWorkspace,
  userInfo,
} from '@/app/infra/http';
import { toast } from 'sonner';
import { httpClient } from '@/app/infra/http/HttpClient';
import { MODEL_CONFIGURATION_CHANGED } from '@/app/infra/http/modelConfigEvents';
import SettingsDialog, {
  SettingsSection,
} from './settings-dialog/SettingsDialog';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import DynamicFormItemComponent from './dynamic-form/DynamicFormItemComponent';
import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import AssistantToolResult, { AssistantTool } from './AssistantToolResult';
import { LANGBOT_MODELS_PROVIDER_REQUESTER } from './models-dialog/types';

type PendingCall = {
  name: string;
  arguments: Record<string, unknown>;
  operation?: {
    id: string;
    label?: Record<string, string>;
    risk?: 'read' | 'write' | 'dangerous';
    summary?: string;
  };
};

type SetupPlan = {
  summary: string;
  fields: {
    key:
      | 'bot'
      | 'model'
      | 'knowledge'
      | 'events'
      | 'plugins'
      | 'engine'
      | string;
    label: string;
    control: 'radio' | 'select';
    selected: string;
    options: { id: string; label: string; description: string }[];
  }[];
};

type Conversation = {
  uuid: string;
  revision: number;
  status: 'ready' | 'running' | 'approval' | 'choice' | 'paused' | 'failed';
  messages: { role: string; content: string; tool?: AssistantTool }[];
  pending: PendingCall[];
  choice_plan: SetupPlan | null;
  error: string | null;
  model_name: string | null;
  model_uuid: string | null;
  progress?: {
    text?: string;
    phase?: 'thinking' | 'tool';
    round?: number;
    tool?: Omit<AssistantTool, 'result'>;
  };
};

function HumanReadableArgs({ args }: { args: unknown }) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) {
    return null;
  }
  const ignoredKeys = new Set([
    'auto_confirm_permissions',
    'confirm',
    'operation_id',
  ]);
  const entries = Object.entries(args as Record<string, unknown>).filter(
    ([key, value]) =>
      !ignoredKeys.has(key) &&
      value !== null &&
      value !== undefined &&
      value !== '',
  );
  if (entries.length === 0) return null;

  const keyLabels: Record<string, string> = {
    plugin_name: '插件名称',
    plugin_author: '插件作者',
    plugin_version: '版本',
    name: '名称',
    description: '描述',
    adapter: '平台适配器',
    model_uuid: '模型',
    pipeline_uuid: '流水线',
    bot_uuid: '机器人',
    target_type: '目标类型',
    system_prompt: '人设提示词',
    plugin_id: '插件标识',
    enable: '是否启用',
    enabled: '是否启用',
  };

  const formatVal = (val: unknown): string => {
    if (typeof val === 'boolean') return val ? '是' : '否';
    if (typeof val === 'object') {
      try {
        return JSON.stringify(val);
      } catch {
        return String(val);
      }
    }
    return String(val);
  };

  return (
    <div className="space-y-1 rounded-md bg-background/80 p-2.5 text-xs border border-border/50">
      <div className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-1">
        {entries.map(([key, val]) => (
          <Fragment key={key}>
            <span className="text-muted-foreground font-medium shrink-0">
              {keyLabels[key] || key.replace(/_/g, ' ')}:
            </span>
            <span className="text-foreground break-all">{formatVal(val)}</span>
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function SetupPlanPanel({
  plan,
  busy,
  onContinue,
  onRevise,
}: {
  plan: SetupPlan;
  busy: boolean;
  onContinue: (choices: Record<string, string>) => void;
  onRevise: () => void;
}) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Record<string, string>>(() =>
    Object.fromEntries(plan.fields.map((field) => [field.key, field.selected])),
  );

  return (
    <div className="space-y-3 rounded-lg border bg-background p-3 text-sm">
      <div>
        <p className="font-medium">{t('assistant.planTitle')}</p>
        <p className="mt-1 break-words text-muted-foreground">{plan.summary}</p>
      </div>
      {plan.fields.map((field) => (
        <div key={field.key} className="space-y-1.5 border-t pt-3">
          <p className="font-medium">{field.label}</p>
          {field.control === 'select' ? (
            <Select
              value={selected[field.key]}
              onValueChange={(value) =>
                setSelected((current) => ({ ...current, [field.key]: value }))
              }
              disabled={busy}
            >
              <SelectTrigger className="w-full min-w-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {field.options.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <div
              role="radiogroup"
              aria-label={field.label}
              className="space-y-1"
            >
              {field.options.map((option) => (
                <label
                  key={option.id}
                  className="flex min-w-0 cursor-pointer gap-2 py-1"
                >
                  <input
                    type="radio"
                    name={`setup-${field.key}`}
                    value={option.id}
                    checked={selected[field.key] === option.id}
                    disabled={busy}
                    onChange={() =>
                      setSelected((current) => ({
                        ...current,
                        [field.key]: option.id,
                      }))
                    }
                    className="mt-1 shrink-0 accent-primary"
                  />
                  <span className="min-w-0 break-words">
                    <span className="block font-medium">{option.label}</span>
                    {option.description && (
                      <span className="block text-xs text-muted-foreground">
                        {option.description}
                      </span>
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}
          {field.control === 'select' &&
            field.options.find((option) => option.id === selected[field.key])
              ?.description && (
              <p className="text-xs text-muted-foreground">
                {
                  field.options.find(
                    (option) => option.id === selected[field.key],
                  )?.description
                }
              </p>
            )}
        </div>
      ))}
      <div className="flex flex-wrap gap-2 border-t pt-3">
        <Button size="sm" disabled={busy} onClick={() => onContinue(selected)}>
          {t('assistant.continuePlan')}
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={onRevise}>
          {t('assistant.revisePlan')}
        </Button>
      </div>
    </div>
  );
}

export default function WorkspaceAssistant() {
  const workspace = useCurrentWorkspace();
  if (
    !workspace?.permissions.includes('runtime.operate') ||
    !userInfo?.account_uuid
  )
    return null;
  const identity = `${workspace.workspace.uuid}:${userInfo.account_uuid}`;
  return (
    <AssistantEntry
      key={identity}
      storageKey={`langbot-assistant:${identity}`}
    />
  );
}

function AssistantEntry({ storageKey }: { storageKey: string }) {
  const { t } = useTranslation();
  const [available, setAvailable] = useState<boolean | null>(null);
  const [localModel, setLocalModel] = useState<
    { uuid: string; name: string } | undefined
  >();
  const [failed, setFailed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [section, setSection] = useState<SettingsSection>('models');
  const [loginBusy, setLoginBusy] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    let latestCheck = 0;
    async function check() {
      const currentCheck = ++latestCheck;
      try {
        const { models } = await backendClient.getProviderLLMModels();
        if (active && currentCheck === latestCheck) {
          const usableModels = models.filter(
            (model) =>
              !!model.uuid?.trim() &&
              model.abilities?.includes('func_call') &&
              (model.provider?.requester !==
                LANGBOT_MODELS_PROVIDER_REQUESTER ||
                (userInfo?.account_type === 'space' &&
                  !systemInfo.disable_models_service)),
          );
          setAvailable(usableModels.length > 0);
          const firstLocalModel =
            userInfo?.account_type !== 'space' ? usableModels[0] : undefined;
          setLocalModel(
            firstLocalModel
              ? { uuid: firstLocalModel.uuid, name: firstLocalModel.name }
              : undefined,
          );
          setFailed(false);
        }
      } catch {
        if (active && currentCheck === latestCheck) setFailed(true);
      }
    }
    if (!settingsOpen) void check();
    window.addEventListener('focus', check);
    window.addEventListener(MODEL_CONFIGURATION_CHANGED, check);
    return () => {
      active = false;
      window.removeEventListener('focus', check);
      window.removeEventListener(MODEL_CONFIGURATION_CHANGED, check);
    };
  }, [settingsOpen, retry]);

  async function login() {
    setLoginBusy(true);
    try {
      const response = await httpClient.getSpaceBindAuthorizeUrl(
        `${window.location.origin}/auth/space/callback?mode=bind`,
      );
      window.location.href = response.authorize_url;
    } catch {
      toast.error(t('common.spaceLoginFailed'));
      setLoginBusy(false);
    }
  }

  return (
    <>
      <AssistantSessions
        storageKey={storageKey}
        canUseModels={available === true && !failed}
        initialModel={localModel}
        setup={
          <div className="mx-3 mb-[max(0.75rem,env(safe-area-inset-bottom))] shrink-0 border-t pt-3">
            <p
              className="text-[13px] leading-relaxed text-muted-foreground"
              role={failed ? 'alert' : undefined}
            >
              {t(
                failed
                  ? 'assistant.providerCheckFailed'
                  : available === null
                    ? 'assistant.preparing'
                    : 'assistant.setupRequired',
              )}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {failed ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setRetry((value) => value + 1)}
                >
                  {t('assistant.retrySetup')}
                </Button>
              ) : available === false ? (
                <>
                  <Button
                    size="sm"
                    disabled={loginBusy}
                    onClick={() => void login()}
                  >
                    {t('assistant.loginAccount')}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSection('models');
                      setSettingsOpen(true);
                    }}
                  >
                    {t('assistant.configureModels')}
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        }
      />
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        section={section}
        onSectionChange={setSection}
      />
    </>
  );
}

type AssistantPanelProps = {
  storageKey: string;
  canUseModels: boolean;
  initialModel?: { uuid: string; name: string };
  setup: ReactNode;
};

function AssistantSessions(props: AssistantPanelProps) {
  const { storageKey } = props;
  const [version, setVersion] = useState(0);
  function select(id: string | null) {
    if (id) localStorage.setItem(storageKey, id);
    else localStorage.removeItem(storageKey);
    setVersion((value) => value + 1);
  }
  return <AssistantPanel key={version} {...props} onSelect={select} />;
}

const ASSISTANT_HEIGHT_STORAGE_KEY = 'langbot-assistant-panel-height';
const ASSISTANT_POSITION_STORAGE_KEY = 'langbot-assistant-panel-position';
const ASSISTANT_OPEN_STORAGE_KEY = 'langbot-assistant-panel-open';

const ADAPTER_TO_QR_PLATFORM: Record<string, QrLoginPlatform> = {
  qqofficial: 'qqofficial',
  'qqofficial-omni': 'qqofficial',
  feishu: 'feishu',
  lark: 'feishu',
  dingtalk: 'dingtalk',
  weixin: 'weixin',
  openclaw_weixin: 'weixin',
  wecombot: 'wecombot',
};

function resolveQrPlatform(adapter?: string): QrLoginPlatform | undefined {
  if (!adapter) return undefined;
  if (adapter in ADAPTER_TO_QR_PLATFORM) return ADAPTER_TO_QR_PLATFORM[adapter];
  const lower = adapter.toLowerCase();
  if (lower.includes('qqofficial') || lower.includes('qq')) return 'qqofficial';
  if (lower.includes('feishu') || lower.includes('lark')) return 'feishu';
  if (lower.includes('dingtalk') || lower.includes('ding')) return 'dingtalk';
  if (lower.includes('weixin') || lower.includes('wechat')) return 'weixin';
  if (lower.includes('wecom')) return 'wecombot';
  return undefined;
}

function AssistantPanel({
  storageKey,
  canUseModels,
  initialModel,
  setup,
  onSelect,
}: AssistantPanelProps & {
  onSelect: (id: string | null) => void;
}) {
  const { t } = useTranslation();
  const initialModelUuid = initialModel?.uuid;
  const initialModelName = initialModel?.name;
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(ASSISTANT_OPEN_STORAGE_KEY) !== 'false';
    } catch {
      return true;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(ASSISTANT_OPEN_STORAGE_KEY, String(open));
    } catch {
      // The panel remains usable when browser storage is unavailable.
    }
  }, [open]);
  const [closing, setClosing] = useState(false);

  const [qrDialogOpen, setQrDialogOpen] = useState(false);
  const [qrDialogPlatform, setQrDialogPlatform] =
    useState<QrLoginPlatform>('qqofficial');
  const [qrTargetBotId, setQrTargetBotId] = useState<string | null>(null);
  const [qrLoadingBotId, setQrLoadingBotId] = useState<string | null>(null);

  const handleStartQrLogin = async (botId: string) => {
    try {
      setQrLoadingBotId(botId);
      const res = await backendClient.getBot(botId);
      const adapter = res?.bot?.adapter;
      const platform = resolveQrPlatform(adapter);
      if (platform) {
        setQrDialogPlatform(platform);
        setQrTargetBotId(botId);
        setQrDialogOpen(true);
      } else {
        toast.info(
          t('assistant.openBotConfig', {
            defaultValue: '该机器人类型暂不支持直接扫码，正在打开配置页...',
          }),
        );
        window.open(`/home/bots?id=${botId}`, '_blank');
      }
    } catch {
      window.open(`/home/bots?id=${botId}`, '_blank');
    } finally {
      setQrLoadingBotId(null);
    }
  };

  const handleQrLoginSuccess = async (credentials: Record<string, string>) => {
    if (!qrTargetBotId) return;
    try {
      const res = await backendClient.getBot(qrTargetBotId);
      const existing =
        (res?.bot?.adapter_config as Record<string, unknown>) || {};
      await backendClient.updateBot(qrTargetBotId, {
        adapter_config: { ...existing, ...credentials },
        enable: true,
      });
      toast.success(
        t('assistant.botBindSuccess', {
          defaultValue: '机器人已成功扫码绑定并启用！',
        }),
      );
    } catch (err) {
      console.error('Failed to update bot config after QR login', err);
      toast.error(
        t('assistant.botBindFailed', {
          defaultValue: '更新机器人配置失败，请在机器人页面手动确认。',
        }),
      );
    }
  };
  const [horizontalPosition, setHorizontalPosition] = useState(() => {
    try {
      const saved = Number(
        localStorage.getItem(ASSISTANT_POSITION_STORAGE_KEY),
      );
      return Number.isFinite(saved) ? Math.max(-1, Math.min(1, saved)) : 0;
    } catch {
      return 0;
    }
  });
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  useEffect(() => {
    const updateWidth = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(
        ASSISTANT_POSITION_STORAGE_KEY,
        String(horizontalPosition),
      );
    } catch {
      // Positioning remains available when storage is blocked.
    }
  }, [horizontalPosition]);
  // Store a relative position so it follows screen changes while keeping a
  // 12px margin. The collapsed dock remains aligned with the expanded panel.
  const horizontalRange = Math.max(0, (viewportWidth - 480 - 24) / 2);
  const moveStart = useRef<{ x: number; offset: number } | null>(null);
  const dockWasDragged = useRef(false);
  const [panelHeight, setPanelHeight] = useState<number | undefined>(() => {
    try {
      const saved = Number(localStorage.getItem(ASSISTANT_HEIGHT_STORAGE_KEY));
      return Number.isFinite(saved) && saved > 0
        ? Math.max(280, saved)
        : undefined;
    } catch {
      return undefined;
    }
  });
  useEffect(() => {
    if (panelHeight === undefined) return;
    try {
      localStorage.setItem(ASSISTANT_HEIGHT_STORAGE_KEY, String(panelHeight));
    } catch {
      // Resizing still works when browser storage is unavailable.
    }
  }, [panelHeight]);
  const panelRef = useRef<HTMLElement>(null);
  const resizeStart = useRef<{ y: number; height: number } | null>(null);
  const resizeHeight = (height: number) => {
    const maximum = Math.max(160, window.innerHeight - 48);
    setPanelHeight(Math.min(maximum, Math.max(Math.min(280, maximum), height)));
  };
  const closeTimer = useRef<number | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [text, setText] = useState('');
  const [sending, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const busy = sending || loading || conversation?.status === 'running';
  const resumable =
    (conversation?.error === 'round_limit' ||
      conversation?.error === 'no_progress' ||
      conversation?.error === 'time_budget' ||
      conversation?.error === 'model_quota_exceeded' ||
      conversation?.error === 'model_auth_failed' ||
      conversation?.error === 'model_permission_denied' ||
      conversation?.error === 'model_request_failed' ||
      conversation?.error === 'model_unavailable' ||
      conversation?.error === 'turn_failed' ||
      conversation?.error === 'tool_failed') &&
    (conversation.status === 'paused' || conversation.status === 'failed');
  const [stopping, setStopping] = useState(false);
  const [sessions, setSessions] = useState<
    { uuid: string; title: string; status: Conversation['status'] }[]
  >([]);
  const [error, setError] = useState(false);
  const [modelUuid, setModelUuid] = useState('');
  const [modelName, setModelName] = useState<string | undefined>();
  const manualModel = useRef(false);
  const [modelError, setModelError] = useState(false);
  const [liveText, setLiveText] = useState('');
  const [liveTool, setLiveTool] = useState<AssistantTool | null>(null);
  const [phase, setPhase] = useState<'thinking' | 'tool' | null>(null);
  const [pendingText, setPendingText] = useState<string | null>(null);
  const controller = useRef(new AbortController());
  const messageList = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const scrollPosition = useRef(0);

  const panelId = useId();
  const expandButton = useRef<HTMLButtonElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(
    () => () => {
      if (closeTimer.current !== null) window.clearTimeout(closeTimer.current);
    },
    [],
  );

  function collapse() {
    if (closeTimer.current !== null) return;
    const finish = () => {
      closeTimer.current = null;
      setOpen(false);
      setClosing(false);
      window.requestAnimationFrame(() => expandButton.current?.focus());
    };
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      finish();
      return;
    }
    setClosing(true);
    closeTimer.current = window.setTimeout(finish, 180);
  }

  function expand() {
    setOpen(true);
    window.requestAnimationFrame(() => input.current?.focus());
  }

  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    setLoading(true);
    async function initialize() {
      try {
        const id = localStorage.getItem(storageKey);
        let saved: Conversation | null = null;
        if (id) {
          saved = await backendClient.request<Conversation>({
            method: 'GET',
            url: `/api/v1/assistant/conversations/${encodeURIComponent(id)}`,
            signal: abort.signal,
          });
          if (abort.signal.aborted) return;
          setConversation(saved);
        }
        if (!canUseModels) return;
        const model = saved?.model_uuid
          ? { uuid: saved.model_uuid, name: saved.model_name ?? undefined }
          : initialModelUuid
            ? { uuid: initialModelUuid, name: initialModelName }
            : await backendClient.request<{ uuid: string; name: string }>({
                method: 'GET',
                url: '/api/v1/assistant/recommended-model',
                signal: abort.signal,
              });
        if (!abort.signal.aborted && !manualModel.current) {
          setModelUuid(model.uuid);
          setModelName(model.name);
        }
      } catch {
        if (!abort.signal.aborted) setModelError(true);
      } finally {
        if (!abort.signal.aborted) setLoading(false);
      }
    }
    void initialize();
    return () => abort.abort();
  }, [storageKey, canUseModels, initialModelUuid, initialModelName]);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await backendClient.request<{
          conversations: typeof sessions;
        }>({
          method: 'GET',
          url: '/api/v1/assistant/conversations',
          signal: controller.current.signal,
        });
        if (active) setSessions(result.conversations ?? []);
        if (!sending && conversation?.uuid) {
          const latest = await backendClient.request<Conversation>({
            method: 'GET',
            url: `/api/v1/assistant/conversations/${conversation.uuid}`,
            signal: controller.current.signal,
          });
          if (active) {
            setConversation(latest);
            setLiveText(latest.progress?.text ?? '');
            setPhase(latest.progress?.phase ?? null);
            setLiveTool(
              latest.progress?.tool
                ? { ...latest.progress.tool, result: { status: 'running' } }
                : null,
            );
          }
        }
      } catch {
        // Polling is read-only. A failed refresh never retries a turn.
      } finally {
        if (active) timer = setTimeout(refresh, 1500);
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [conversation?.uuid, sending]);

  async function stop() {
    if (!conversation || stopping) return;
    setStopping(true);
    try {
      const latest = await backendClient.request<Conversation>({
        method: 'POST',
        url: `/api/v1/assistant/conversations/${conversation.uuid}/stop`,
        data: { revision: conversation.revision },
        signal: controller.current.signal,
      });
      setConversation(latest);
      setLiveText('');
      setLiveTool(null);
      setPhase(null);
    } catch {
      setError(true);
    } finally {
      setStopping(false);
    }
  }

  // Restore the reading position when reopening; new conversations start at the bottom.
  useEffect(() => {
    if (open && messageList.current && !followLatest.current) {
      messageList.current.scrollTop = scrollPosition.current;
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => {
      const list = messageList.current;
      if (list && followLatest.current) {
        list.scrollTop = list.scrollHeight;
        scrollPosition.current = list.scrollTop;
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [open, conversation, busy, pendingText, liveText, liveTool, panelHeight]);

  async function submit(
    approved?: boolean,
    choices?: Record<string, string>,
    continueRun = false,
  ) {
    const sendingText =
      approved === undefined && choices === undefined && !continueRun;
    if (
      !canUseModels ||
      busy ||
      (continueRun && !resumable) ||
      (sendingText &&
        (!text.trim() ||
          !modelUuid ||
          (conversation &&
            !['ready', 'choice'].includes(conversation.status) &&
            !resumable)))
    )
      return;
    const sentText = sendingText ? text.trim() : null;
    const sentRevision = conversation?.revision ?? 0;
    if (sentText) {
      setPendingText(sentText);
      setText('');
    }
    setBusy(true);
    setError(false);
    setPhase('thinking');
    try {
      let current = conversation;
      if (!current) {
        current = await backendClient.request<Conversation>({
          method: 'POST',
          url: '/api/v1/assistant/conversations',
          signal: controller.current.signal,
        });
        localStorage.setItem(storageKey, current.uuid);
        setConversation(current);
      }
      const updated = await backendClient.streamAssistant<Conversation>(
        current.uuid,
        {
          revision: current.revision,
          ...(sendingText
            ? { text: sentText!, model_uuid: modelUuid }
            : continueRun
              ? {
                  continue_run: true,
                  ...(modelUuid && modelUuid !== conversation?.model_uuid
                    ? { model_uuid: modelUuid }
                    : {}),
                }
              : choices !== undefined
                ? { choices }
                : { approved }),
        },
        (event) => {
          if (event.kind === 'snapshot') {
            const snapshot = event.data as Conversation;
            setConversation(snapshot);
            setPendingText(null);
            setLiveText('');
            setLiveTool(null);
            if (snapshot.model_uuid) {
              setModelUuid(snapshot.model_uuid);
              setModelName(snapshot.model_name ?? undefined);
            }
          } else if (event.kind === 'text') {
            setLiveText((event.data as { text: string }).text);
          } else if (event.kind === 'phase') {
            const state = event.data as {
              phase: 'thinking' | 'tool';
              round?: number;
              tool?: Omit<AssistantTool, 'result'>;
            };
            setPhase(state.phase);
            setLiveTool(
              state.tool
                ? { ...state.tool, result: { status: 'running' } }
                : null,
            );
          }
        },
        controller.current.signal,
      );
      setConversation(updated);
      if (sentText) setPendingText(null);
    } catch {
      if (controller.current.signal.aborted) return;
      setError(true);
      // A lost response may already have executed a write. Refresh, never replay.
      const id = localStorage.getItem(storageKey);
      if (id && !controller.current.signal.aborted) {
        try {
          const latest = await backendClient.request<Conversation>({
            method: 'GET',
            url: `/api/v1/assistant/conversations/${encodeURIComponent(id)}`,
            signal: controller.current.signal,
          });
          setConversation(latest);
          if (
            sentText &&
            latest.revision > sentRevision &&
            latest.messages.some(
              (message) =>
                message.role === 'user' && message.content === sentText,
            )
          )
            setPendingText(null);
        } catch {
          /* Keep the error visible; do not retry a turn. */
        }
      }
    } finally {
      setBusy(false);
      setLiveText('');
      setLiveTool(null);
      setPhase(null);
    }
  }

  function reset() {
    onSelect(null);
  }

  // A user message starts a turn; its tool steps and replies share one bubble.
  const messageGroups: {
    key: number;
    role: 'user' | 'assistant';
    messages: Conversation['messages'];
  }[] = [];
  const visibleMessages: Conversation['messages'] = [
    ...(conversation?.messages ?? []),
  ];
  if (liveText) visibleMessages.push({ role: 'assistant', content: liveText });
  if (liveTool)
    visibleMessages.push({ role: 'tool', content: '', tool: liveTool });
  for (const [index, message] of visibleMessages.entries()) {
    const role = message.role === 'user' ? 'user' : 'assistant';
    const previous = messageGroups.at(-1);
    if (role === 'assistant' && previous?.role === 'assistant') {
      previous.messages.push(message);
    } else {
      messageGroups.push({ key: index, role, messages: [message] });
    }
  }

  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-3">
      <div
        className="flex w-full max-w-[480px] justify-center"
        style={{
          transform: `translateX(${horizontalPosition * horizontalRange}px)`,
        }}
      >
        {!open && (
          <Button
            ref={expandButton}
            className={`pointer-events-auto touch-none select-none active:cursor-grabbing h-[calc(21px+env(safe-area-inset-bottom))] min-h-0 w-24 gap-2 rounded-b-none rounded-t-md border-0 bg-[#2288ee] px-3 py-0 pb-[env(safe-area-inset-bottom)] text-white shadow-lg hover:bg-[#2277e0] ${styles.dock}`}
            title={t('assistant.expand')}
            aria-label={t('assistant.expand')}
            aria-expanded={false}
            aria-controls={panelId}
            onPointerDown={(event) => {
              if (event.button !== 0 || !event.isPrimary) return;
              dockWasDragged.current = false;
              moveStart.current = {
                x: event.clientX,
                offset: horizontalPosition * horizontalRange,
              };
              event.currentTarget.setPointerCapture(event.pointerId);
            }}
            onPointerMove={(event) => {
              if (!moveStart.current) return;
              const delta = event.clientX - moveStart.current.x;
              if (Math.abs(delta) >= 5) dockWasDragged.current = true;
              if (!dockWasDragged.current || horizontalRange === 0) return;
              setHorizontalPosition(
                Math.max(
                  -1,
                  Math.min(
                    1,
                    (moveStart.current.offset + delta) / horizontalRange,
                  ),
                ),
              );
            }}
            onPointerUp={(event) => {
              moveStart.current = null;
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId);
            }}
            onPointerCancel={() => {
              moveStart.current = null;
              dockWasDragged.current = true;
            }}
            onLostPointerCapture={() => {
              moveStart.current = null;
            }}
            onClick={(event) => {
              if (dockWasDragged.current && event.detail !== 0) {
                event.preventDefault();
                dockWasDragged.current = false;
                return;
              }
              expand();
            }}
          >
            <RiMagicLine
              aria-hidden="true"
              className={`size-3.5 ${styles.magic}`}
            />
            <RiSparkling2Line
              aria-hidden="true"
              className={`size-3 ${styles.sparkle}`}
            />
            <RiArrowUpSLine aria-hidden="true" className="size-3" />
          </Button>
        )}
        {open && (
          <section
            ref={panelRef}
            // CSS max-height adapts to the current viewport without overwriting
            // the saved preference, so a larger screen restores the chosen size.
            style={
              panelHeight === undefined ? undefined : { height: panelHeight }
            }
            id={panelId}
            inert={closing}
            role="dialog"
            aria-modal={false}
            aria-labelledby={`${panelId}-title`}
            className={`pointer-events-auto flex max-h-[calc(100dvh-48px)] w-full max-w-[480px] flex-col overflow-hidden rounded-t-2xl border border-b-0 bg-background ${styles.panel} ${closing ? styles.closing : ''} ${conversation?.messages.length || pendingText ? styles.conversationPanel : ''}`}
            onKeyDown={(event) => {
              if (event.key === 'Escape' && !event.defaultPrevented) {
                event.preventDefault();
                event.stopPropagation();
                collapse();
              }
            }}
          >
            <div
              role="separator"
              tabIndex={0}
              aria-label={t('assistant.resizeHeight')}
              aria-orientation="horizontal"
              aria-controls={panelId}
              className="group flex h-5 shrink-0 touch-none select-none items-center justify-center cursor-ns-resize focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              onPointerDown={(event) => {
                if (event.button !== 0 || !event.isPrimary) return;
                event.preventDefault();
                resizeStart.current = {
                  y: event.clientY,
                  height: panelRef.current!.getBoundingClientRect().height,
                };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (resizeStart.current)
                  resizeHeight(
                    resizeStart.current.height +
                      resizeStart.current.y -
                      event.clientY,
                  );
              }}
              onPointerUp={(event) => {
                resizeStart.current = null;
                if (event.currentTarget.hasPointerCapture(event.pointerId))
                  event.currentTarget.releasePointerCapture(event.pointerId);
              }}
              onLostPointerCapture={() => {
                resizeStart.current = null;
              }}
              onPointerCancel={() => {
                resizeStart.current = null;
              }}
              onKeyDown={(event) => {
                if (
                  !['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)
                )
                  return;
                event.preventDefault();
                const height = panelRef.current!.getBoundingClientRect().height;
                resizeHeight(
                  event.key === 'Home'
                    ? 280
                    : event.key === 'End'
                      ? window.innerHeight - 48
                      : height + (event.key === 'ArrowUp' ? 24 : -24),
                );
              }}
            >
              <span
                aria-hidden="true"
                className="h-1 w-9 rounded-full bg-muted-foreground/30 transition-colors group-hover:bg-muted-foreground/60 group-focus-visible:bg-muted-foreground/60"
              />
            </div>
            <header
              className={`flex shrink-0 items-center gap-2 px-3 pb-1 pt-2 ${styles.header}`}
            >
              <span className={styles.avatar} aria-hidden="true">
                <RiMagicLine className={`size-4 ${styles.magic}`} />
              </span>
              <div
                className="min-w-0 flex-1 cursor-grab touch-none select-none active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                role="slider"
                tabIndex={0}
                aria-label={t('assistant.movePosition')}
                aria-orientation="horizontal"
                aria-valuemin={-100}
                aria-valuemax={100}
                aria-valuenow={Math.round(horizontalPosition * 100)}
                onPointerDown={(event) => {
                  if (event.button !== 0 || !event.isPrimary) return;
                  event.preventDefault();
                  moveStart.current = {
                    x: event.clientX,
                    offset: horizontalPosition * horizontalRange,
                  };
                  event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                  if (!moveStart.current || horizontalRange === 0) return;
                  setHorizontalPosition(
                    Math.max(
                      -1,
                      Math.min(
                        1,
                        (moveStart.current.offset +
                          event.clientX -
                          moveStart.current.x) /
                          horizontalRange,
                      ),
                    ),
                  );
                }}
                onPointerUp={(event) => {
                  moveStart.current = null;
                  if (event.currentTarget.hasPointerCapture(event.pointerId))
                    event.currentTarget.releasePointerCapture(event.pointerId);
                }}
                onPointerCancel={() => {
                  moveStart.current = null;
                }}
                onLostPointerCapture={() => {
                  moveStart.current = null;
                }}
                onKeyDown={(event) => {
                  if (
                    !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(
                      event.key,
                    )
                  )
                    return;
                  event.preventDefault();
                  setHorizontalPosition(
                    event.key === 'Home'
                      ? -1
                      : event.key === 'End'
                        ? 1
                        : Math.max(
                            -1,
                            Math.min(
                              1,
                              horizontalPosition +
                                (event.key === 'ArrowLeft' ? -0.1 : 0.1),
                            ),
                          ),
                  );
                }}
              >
                <h2
                  id={`${panelId}-title`}
                  className="truncate text-sm font-medium"
                >
                  {t('assistant.title')}
                </h2>
              </div>
              <Select
                value={conversation?.uuid ?? 'new'}
                onValueChange={(value) =>
                  onSelect(value === 'new' ? null : value)
                }
              >
                <SelectTrigger
                  aria-label={t('assistant.sessions')}
                  className="w-32 min-w-0 bg-background px-2 text-xs data-[size=default]:h-7"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-w-[min(20rem,calc(100vw-24px))]">
                  <SelectItem value="new" className="text-xs">
                    {t('assistant.newChat')}
                  </SelectItem>
                  {conversation &&
                    !sessions.some(
                      (session) => session.uuid === conversation.uuid,
                    ) && (
                      <SelectItem value={conversation.uuid} className="text-xs">
                        {t('assistant.currentChat')}
                      </SelectItem>
                    )}
                  {sessions.map((session) => (
                    <SelectItem
                      key={session.uuid}
                      value={session.uuid}
                      className="text-xs [&_[data-slot=select-item-text]]:min-w-0"
                    >
                      <span className="block truncate">
                        {session.status === 'running'
                          ? '◌ '
                          : session.status === 'approval'
                            ? '… '
                            : ''}
                        {session.title || t('assistant.newChat')}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                className="size-7 shrink-0"
                onClick={reset}
                aria-label={t('assistant.newChat')}
              >
                <Plus />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-7 shrink-0"
                onClick={collapse}
                aria-label={t('assistant.collapse')}
                aria-expanded={true}
                aria-controls={panelId}
              >
                <ChevronDown />
              </Button>
            </header>
            <div
              ref={messageList}
              className="min-h-0 flex-1 space-y-3 overflow-y-auto overscroll-contain px-3 py-2"
              onWheel={(event) => {
                if (event.deltaY < 0) followLatest.current = false;
              }}
              onScroll={(event) => {
                const list = event.currentTarget;
                const delta = list.scrollTop - scrollPosition.current;
                if (delta < -1) followLatest.current = false;
                else if (delta > 1) {
                  followLatest.current =
                    list.scrollHeight - list.clientHeight - list.scrollTop < 32;
                }
                // Delayed events from our own scroll have zero delta. Content may
                // have grown since then, so they must not disable following.
                scrollPosition.current = list.scrollTop;
              }}
              aria-live="polite"
            >
              {!conversation?.messages.length && !pendingText && (
                <div className={styles.welcome}>
                  <h3 className="text-base font-medium tracking-tight">
                    {t('assistant.subtitle')}
                  </h3>
                  <p className="max-w-lg text-[13px] leading-relaxed text-muted-foreground">
                    {t('assistant.welcome')}
                  </p>
                  <div className="flex flex-wrap gap-2 pt-2">
                    {(['discover', 'build'] as const).map((key) => (
                      <button
                        key={key}
                        type="button"
                        disabled={busy || !canUseModels}
                        className={styles.prompt}
                        onClick={() => {
                          setText(t(`assistant.${key}`));
                          input.current?.focus();
                        }}
                      >
                        <span className={styles.promptIcon} aria-hidden="true">
                          {key === 'discover' ? (
                            <RiCompass3Line className="size-4" />
                          ) : (
                            <RiMagicLine className="size-4" />
                          )}
                        </span>
                        <span className="flex-1">{t(`assistant.${key}`)}</span>
                        <RiArrowRightUpLine
                          className="size-4 shrink-0 opacity-60"
                          aria-hidden="true"
                        />
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messageGroups.map((group) => (
                <div
                  key={group.key}
                  className={`flex min-w-0 ${group.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`min-w-0 max-w-[94%] space-y-2 rounded-2xl px-3 py-2 text-sm ${group.role === 'user' ? styles.userMessage : styles.assistantMessage}`}
                  >
                    {group.messages.map((message, index) =>
                      message.role === 'tool' ? (
                        <AssistantToolResult
                          key={index}
                          tool={message.tool}
                          content={message.content}
                          defaultCollapsed
                        />
                      ) : message.role === 'user' ? (
                        <p
                          key={index}
                          className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] leading-relaxed"
                        >
                          {message.content}
                        </p>
                      ) : (
                        <div
                          key={index}
                          className={`markdown-body ${styles.messageContent}`}
                        >
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeHighlight]}
                            components={{
                              ul: ({ children }) => (
                                <ul className="list-disc">{children}</ul>
                              ),
                              ol: ({ children }) => (
                                <ol className="list-decimal">{children}</ol>
                              ),
                              img: () => null,
                              a: ({ href, children }) => {
                                const match = href?.match(
                                  /\/home\/bots\?id=([a-f0-9-]+)/i,
                                );
                                const botId = match ? match[1] : null;
                                return (
                                  <span className="inline-flex items-center gap-1.5 flex-wrap my-0.5 align-middle">
                                    <a
                                      href={href}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                    >
                                      {children}
                                    </a>
                                    {botId && (
                                      <button
                                        type="button"
                                        onClick={(e) => {
                                          e.preventDefault();
                                          e.stopPropagation();
                                          void handleStartQrLogin(botId);
                                        }}
                                        disabled={qrLoadingBotId === botId}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-normal rounded-md border border-primary/30 bg-primary/10 text-primary hover:bg-primary/20 transition-colors cursor-pointer"
                                        title="在工作助手页面直接扫码授权"
                                      >
                                        <QrCode className="size-3" />
                                        <span>
                                          {qrLoadingBotId === botId
                                            ? '正在唤起...'
                                            : '在此扫码授权'}
                                        </span>
                                      </button>
                                    )}
                                  </span>
                                );
                              },
                            }}
                          >
                            {message.content}
                          </ReactMarkdown>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              ))}
              {pendingText && (
                <div
                  className={`ml-auto w-fit max-w-[94%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words [overflow-wrap:anywhere] ${styles.userMessage}`}
                >
                  {pendingText}
                  {error && (
                    <p className="mt-1 text-xs text-destructive">
                      {t('assistant.sendUnconfirmed')}
                    </p>
                  )}
                </div>
              )}
              {conversation?.status === 'approval' && (
                <div className="space-y-3 rounded-xl border border-primary/30 p-3">
                  <p className="text-sm font-medium">{t('assistant.review')}</p>
                  {conversation.pending.map((call, index) => {
                    const isWorkspaceCall = call.name === 'workspace_call';
                    const operation = call.operation;
                    const opId = isWorkspaceCall
                      ? operation?.id ||
                        (call.arguments?.operation_id as string)
                      : null;
                    const opArgs = isWorkspaceCall
                      ? (call.arguments?.arguments ?? call.arguments)
                      : call.arguments;
                    const opLabel =
                      operation?.label?.zh_Hans ||
                      operation?.label?.['zh-Hans'] ||
                      operation?.label?.en_US ||
                      opId;
                    const risk = operation?.risk;
                    const isDangerous = risk === 'dangerous';

                    return (
                      <div
                        key={index}
                        className={`space-y-2 rounded-lg border p-3 ${
                          isDangerous
                            ? 'border-destructive/40 bg-destructive/5'
                            : 'bg-muted/30'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            {isWorkspaceCall && opLabel ? (
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-sm font-semibold">
                                  {opLabel}
                                </span>
                                {opLabel === opId && (
                                  <span className="text-xs text-muted-foreground font-mono">
                                    ({opId})
                                  </span>
                                )}
                              </div>
                            ) : (
                              <p className="text-sm font-medium">{call.name}</p>
                            )}
                          </div>
                          {risk && (
                            <span
                              className={`shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
                                isDangerous
                                  ? 'bg-destructive/15 text-destructive font-bold ring-1 ring-destructive/30'
                                  : 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
                              }`}
                            >
                              {t(`agents.apiToolRisk.${risk}`, {
                                defaultValue: isDangerous ? '敏感' : '操作',
                              })}
                            </span>
                          )}
                        </div>
                        {isDangerous && (
                          <div className="flex items-center gap-1.5 rounded bg-destructive/10 px-2 py-1.5 text-xs text-destructive font-medium border border-destructive/20">
                            <CircleAlert className="size-4 shrink-0" />
                            <span>
                              {t('assistant.dangerousWarning', {
                                defaultValue:
                                  '敏感操作提示：该操作具有较高风险，执行后可能不可逆，请核对参数后确认。',
                              })}
                            </span>
                          </div>
                        )}
                        <HumanReadableArgs args={opArgs} />
                      </div>
                    );
                  })}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      disabled={busy}
                      onClick={() => submit(true)}
                    >
                      {t('assistant.confirm')}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => submit(false)}
                    >
                      {t('assistant.decline')}
                    </Button>
                  </div>
                </div>
              )}
              {conversation?.status === 'choice' &&
                conversation.choice_plan && (
                  <SetupPlanPanel
                    key={`${conversation.uuid}:${conversation.revision}`}
                    plan={conversation.choice_plan}
                    busy={busy}
                    onContinue={(choices) => void submit(undefined, choices)}
                    onRevise={() => input.current?.focus()}
                  />
                )}
              {resumable && (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">
                    {t(
                      conversation.error === 'time_budget'
                        ? 'assistant.timeBudget'
                        : conversation.error === 'model_quota_exceeded'
                          ? 'assistant.modelQuotaExceeded'
                          : conversation.error === 'model_auth_failed'
                            ? 'assistant.modelAuthFailed'
                            : conversation.error === 'model_permission_denied'
                              ? 'assistant.modelPermissionDenied'
                              : conversation.error === 'model_request_failed'
                                ? 'assistant.modelRequestFailed'
                                : conversation.error === 'model_unavailable'
                                  ? 'assistant.modelUnavailable'
                                  : 'assistant.roundLimit',
                    )}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void submit(undefined, undefined, true)}
                  >
                    {t(
                      [
                        'model_quota_exceeded',
                        'model_auth_failed',
                        'model_permission_denied',
                        'model_request_failed',
                        'model_unavailable',
                      ].includes(conversation.error ?? '')
                        ? 'assistant.retryRun'
                        : 'assistant.continueRun',
                    )}
                  </Button>
                </div>
              )}
              {busy && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <LoaderCircle className="size-4 animate-spin" />
                  {loading
                    ? t('assistant.preparing')
                    : t(
                        phase === 'tool'
                          ? 'assistant.executing'
                          : 'assistant.thinking',
                      )}
                </p>
              )}
              {canUseModels && modelError && !modelUuid && (
                <p role="alert" className="text-xs text-destructive">
                  {t('assistant.recommendationFailed')}
                </p>
              )}
              {(error || (conversation?.status === 'failed' && !resumable)) && (
                <p role="alert" className="text-sm text-destructive">
                  {conversation?.error === 'stopped'
                    ? t('assistant.stopped')
                    : conversation?.error === 'model_quota_exceeded'
                      ? t('assistant.modelQuotaExceeded')
                      : conversation?.error === 'model_auth_failed'
                        ? t('assistant.modelAuthFailed')
                        : conversation?.error === 'model_permission_denied'
                          ? t('assistant.modelPermissionDenied')
                          : conversation?.error === 'model_request_failed'
                            ? t('assistant.modelRequestFailed')
                            : conversation?.error === 'model_unavailable'
                              ? t('assistant.modelUnavailable')
                              : t('assistant.error')}
                </p>
              )}
              {!busy && conversation?.status === 'running' && (
                <p className="text-sm text-muted-foreground">
                  {t('assistant.running')}
                </p>
              )}
            </div>
            {canUseModels ? (
              <form
                className={`mx-2 mb-[max(0.5rem,env(safe-area-inset-bottom))] flex shrink-0 flex-col gap-1 rounded-xl p-1.5 ${styles.composer}`}
                onSubmit={(event) => {
                  event.preventDefault();
                  void submit();
                }}
              >
                <textarea
                  ref={input}
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  maxLength={8000}
                  rows={2}
                  aria-label={t('assistant.placeholder')}
                  placeholder={t(
                    busy
                      ? 'assistant.draftPlaceholder'
                      : 'assistant.placeholder',
                  )}
                  onKeyDown={(event) => {
                    if (
                      event.key === 'Enter' &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      void submit();
                    }
                  }}
                  className={`w-full min-w-0 resize-none rounded-lg bg-transparent px-2 py-1.5 text-sm outline-none focus-visible:outline-none ${styles.input}`}
                />
                <div className="flex w-full items-center justify-between gap-3">
                  {open && (
                    <div
                      className="w-28 min-w-0 shrink-0"
                      title={t('assistant.modelHint')}
                    >
                      <DynamicFormItemComponent
                        config={{
                          id: 'assistant-model',
                          name: 'assistant-model',
                          type: DynamicFormItemType.LLM_MODEL_SELECTOR,
                          default: '',
                          required: false,
                          label: {
                            en_US: 'Assistant model',
                            zh_Hans: '助手模型',
                          },
                        }}
                        field={{
                          name: 'assistant-model',
                          value: modelUuid,
                          onChange: (value: string) => {
                            // Radix's native form bridge can emit an empty value while
                            // async options mount. It is not a user model selection.
                            if (!value) return;
                            manualModel.current = true;
                            setModelUuid(value);
                            setModelName(undefined);
                            setModelError(false);
                          },
                          onBlur: () => {},
                          ref: () => {},
                          disabled:
                            sending ||
                            (!!conversation &&
                              conversation.status !== 'ready' &&
                              !resumable),
                        }}
                        requiredModelAbility="func_call"
                        compactModelSelector
                        selectedModelLabel={modelName}
                      />
                    </div>
                  )}
                  {conversation?.status === 'running' ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="outline"
                      className="size-7 rounded-lg"
                      aria-label={t('assistant.stop')}
                      disabled={stopping}
                      onClick={() => void stop()}
                    >
                      <Square className="size-3 fill-current" />
                    </Button>
                  ) : (
                    <Button
                      type="submit"
                      size="icon"
                      className={`size-7 rounded-lg ${styles.send}`}
                      aria-label={t('assistant.send')}
                      disabled={
                        busy ||
                        !text.trim() ||
                        !modelUuid ||
                        (!!conversation &&
                          !['ready', 'choice'].includes(conversation.status) &&
                          !resumable)
                      }
                    >
                      <Send className="size-4" />
                    </Button>
                  )}
                </div>
              </form>
            ) : (
              setup
            )}
          </section>
        )}
      </div>
      <QrCodeLoginDialog
        open={qrDialogOpen}
        onOpenChange={setQrDialogOpen}
        platform={qrDialogPlatform}
        onSuccess={handleQrLoginSuccess}
      />
    </div>,
    document.body,
  );
}
