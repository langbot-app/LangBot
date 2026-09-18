import { useEffect, useRef, useState } from 'react';
import { MessageCircle, Plus, Send, X, LoaderCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { backendClient, useCurrentWorkspace, userInfo } from '@/app/infra/http';
import { Button } from '@/components/ui/button';
import DynamicFormItemComponent from './dynamic-form/DynamicFormItemComponent';
import { DynamicFormItemType } from '@/app/infra/entities/form/dynamic';
import AssistantToolResult, { AssistantTool } from './AssistantToolResult';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

type Conversation = {
  uuid: string;
  revision: number;
  status: 'ready' | 'running' | 'approval' | 'failed';
  messages: { role: string; content: string; tool?: AssistantTool }[];
  pending: { name: string; arguments: Record<string, unknown> }[];
  error: string | null;
  model_name: string | null;
  model_uuid: string | null;
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
    <AssistantPanel
      key={identity}
      storageKey={`langbot-assistant:${identity}`}
    />
  );
}

function AssistantPanel({ storageKey }: { storageKey: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [text, setText] = useState('');
  const [sending, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const busy = sending || loading;
  const [error, setError] = useState(false);
  const [modelUuid, setModelUuid] = useState('');
  const [pendingText, setPendingText] = useState<string | null>(null);
  const controller = useRef(new AbortController());
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (conversation?.model_uuid) setModelUuid(conversation.model_uuid);
  }, [conversation?.model_uuid]);

  useEffect(() => {
    const abort = new AbortController();
    controller.current = abort;
    return () => abort.abort();
  }, []);

  useEffect(() => {
    if (!open || busy || (conversation && conversation.status !== 'running'))
      return;
    const id = localStorage.getItem(storageKey);
    if (!id) return;
    let active = true;
    setLoading(true);
    backendClient
      .request<Conversation>({
        method: 'GET',
        url: `/api/v1/assistant/conversations/${encodeURIComponent(id)}`,
        signal: controller.current.signal,
      })
      .then((value) => {
        if (active) setConversation(value);
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem(storageKey);
          setError(true);
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      setLoading(false);
    };
    // Load only when opening; turn requests own subsequent state updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, storageKey]);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [conversation, busy, pendingText]);

  async function submit(approved?: boolean) {
    if (
      busy ||
      (approved === undefined &&
        (!text.trim() || (conversation && conversation.status !== 'ready')))
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
      const updated = await backendClient.request<Conversation>({
        method: 'POST',
        url: `/api/v1/assistant/conversations/${current.uuid}/turn`,
        data: {
          revision: current.revision,
          ...(approved === undefined
            ? {
                text: sentText,
                ...(modelUuid ? { model_uuid: modelUuid } : {}),
              }
            : { approved }),
        },
        timeout: 130000,
        signal: controller.current.signal,
      });
      setConversation(updated);
      if (sentText) setPendingText(null);
    } catch {
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
    }
  }

  function reset() {
    localStorage.removeItem(storageKey);
    setConversation(null);
    setText('');
    setError(false);
    setPendingText(null);
  }

  return (
    <div className="fixed bottom-20 right-5 z-50">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            size="icon"
            className="size-12 rounded-full shadow-lg"
            aria-label={t('assistant.title')}
          >
            <MessageCircle className="size-6" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="end"
          side="top"
          sideOffset={12}
          className="flex h-[min(680px,80dvh)] w-[min(440px,calc(100vw-24px))] flex-col overflow-hidden rounded-2xl p-0 shadow-xl"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <header className="flex items-center gap-2 border-b p-3">
            <MessageCircle className="size-5 text-primary" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate font-semibold">{t('assistant.title')}</h2>
              <p className="truncate text-xs text-muted-foreground">
                {t('assistant.subtitle')}
              </p>
            </div>
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
                    label: { en_US: 'Assistant model', zh_Hans: '助手模型' },
                  }}
                  field={{
                    name: 'assistant-model',
                    value: modelUuid,
                    onChange: setModelUuid,
                    onBlur: () => {},
                    ref: () => {},
                    disabled:
                      busy ||
                      (!!conversation && conversation.status !== 'ready'),
                  }}
                  requiredModelAbility="func_call"
                  compactModelSelector
                />
              </div>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              disabled={busy}
              onClick={reset}
              aria-label={t('assistant.newChat')}
            >
              <Plus />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 shrink-0"
              onClick={() => setOpen(false)}
              aria-label={t('assistant.close')}
            >
              <X />
            </Button>
          </header>
          <div
            className="flex-1 space-y-3 overflow-y-auto p-4"
            aria-live="polite"
          >
            {!conversation?.messages.length && !pendingText && (
              <>
                <p className="text-sm text-muted-foreground">
                  {t('assistant.welcome')}
                </p>
                {(['discover', 'build'] as const).map((key) => (
                  <button
                    key={key}
                    type="button"
                    disabled={busy}
                    className="w-full rounded-lg border p-3 text-left text-sm hover:bg-muted"
                    onClick={() => setText(t(`assistant.${key}`))}
                  >
                    {t(`assistant.${key}`)}
                  </button>
                ))}
              </>
            )}
            {conversation?.messages.map((message, index) =>
              message.role === 'tool' ? (
                <AssistantToolResult
                  key={index}
                  tool={message.tool}
                  content={message.content}
                />
              ) : (
                <div
                  key={index}
                  className={`rounded-xl p-3 text-sm break-words ${message.role === 'user' ? 'ml-6 bg-primary/10' : 'bg-muted'}`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      img: () => null,
                      a: ({ href, children }) => (
                        <a
                          href={href}
                          className="text-primary underline"
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
            {pendingText && (
              <div className="ml-6 rounded-xl bg-primary/10 p-3 text-sm whitespace-pre-wrap break-words">
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
                {t('assistant.working')}
              </p>
            )}
            {(error || conversation?.status === 'failed') && (
              <p role="alert" className="text-sm text-destructive">
                {conversation?.error === 'model_unavailable'
                  ? t('assistant.modelUnavailable')
                  : t('assistant.error')}
              </p>
            )}
            {!busy && conversation?.status === 'running' && (
              <p className="text-sm text-muted-foreground">
                {t('assistant.running')}
              </p>
            )}
            <div ref={end} />
          </div>
          <form
            className="flex items-end gap-2 border-t p-3"
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
          >
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              maxLength={8000}
              rows={2}
              aria-label={t('assistant.placeholder')}
              placeholder={t(
                busy ? 'assistant.draftPlaceholder' : 'assistant.placeholder',
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
              className="min-w-0 flex-1 resize-none rounded-lg border bg-background p-2 text-sm focus-visible:outline-2 focus-visible:outline-primary"
            />
            <Button
              type="submit"
              size="icon"
              aria-label={t('assistant.send')}
              disabled={
                busy ||
                !text.trim() ||
                (!!conversation && conversation.status !== 'ready')
              }
            >
              <Send className="size-4" />
            </Button>
          </form>
        </PopoverContent>
      </Popover>
    </div>
  );
}
