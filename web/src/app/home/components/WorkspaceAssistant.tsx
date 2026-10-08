import { useEffect, useRef, useState, useId, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Plus, Send, ChevronDown, LoaderCircle, Square } from 'lucide-react';
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

type Conversation = {
  uuid: string;
  revision: number;
  status: 'ready' | 'running' | 'approval' | 'failed';
  messages: { role: string; content: string; tool?: AssistantTool }[];
  pending: { name: string; arguments: Record<string, unknown> }[];
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
  const [open, setOpen] = useState(true);
  const [closing, setClosing] = useState(false);
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
  const [round, setRound] = useState(1);
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
            setRound(latest.progress?.round ?? 1);
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

  async function submit(approved?: boolean) {
    if (
      !canUseModels ||
      busy ||
      (approved === undefined &&
        (!text.trim() ||
          !modelUuid ||
          (conversation && conversation.status !== 'ready')))
    )
      return;
    const sentText = approved === undefined ? text.trim() : null;
    const sentRevision = conversation?.revision ?? 0;
    if (sentText) {
      setPendingText(sentText);
      setText('');
    }
    setBusy(true);
    setError(false);
    setRound(1);
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
          ...(approved === undefined
            ? { text: sentText!, model_uuid: modelUuid }
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
            if (state.round) setRound(state.round);
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
                              a: ({ href, children }) => (
                                <a
                                  href={href}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  {children}
                                </a>
                              ),
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
                  {conversation.pending.map((call, index) => (
                    <div key={index}>
                      <p className="text-sm font-medium">{call.name}</p>
                      <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs">
                        {JSON.stringify(call.arguments, null, 2)}
                      </pre>
                    </div>
                  ))}
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
              {busy && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <LoaderCircle className="size-4 animate-spin" />
                  {loading
                    ? t('assistant.preparing')
                    : t(
                        phase === 'tool'
                          ? 'assistant.executing'
                          : 'assistant.thinking',
                        { round },
                      )}
                </p>
              )}
              {canUseModels && modelError && !modelUuid && (
                <p role="alert" className="text-xs text-destructive">
                  {t('assistant.recommendationFailed')}
                </p>
              )}
              {(error || conversation?.status === 'failed') && (
                <p role="alert" className="text-sm text-destructive">
                  {conversation?.error === 'stopped'
                    ? t('assistant.stopped')
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
                            (!!conversation && conversation.status !== 'ready'),
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
                        (!!conversation && conversation.status !== 'ready')
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
    </div>,
    document.body,
  );
}
