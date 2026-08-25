import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { AlertTriangle, LoaderCircle, Play, RotateCcw } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

interface AgentDebugPanelProps {
  agentId: string;
  supportedEventPatterns?: string[];
}

interface DebugEntry {
  id: string;
  direction: 'input' | 'output' | 'error';
  eventType: string;
  text: string;
}

const EVENT_PRESETS = [
  {
    value: 'message.received',
    labelKey: 'agents.debugMessageReceived',
    text: '',
    data: {},
  },
  {
    value: 'group.member.joined',
    labelKey: 'agents.debugGroupMemberJoined',
    text: 'A new member joined the group.',
    data: {
      group_id: 'debug-group',
      member_id: 'debug-user',
      member_name: 'Debug User',
    },
  },
  {
    value: 'group.member.left',
    labelKey: 'agents.debugGroupMemberLeft',
    text: 'A member left the group.',
    data: {
      group_id: 'debug-group',
      member_id: 'debug-user',
      member_name: 'Debug User',
    },
  },
  {
    value: 'friend.requested',
    labelKey: 'agents.debugFriendRequested',
    text: 'A user sent a friend request.',
    data: {
      requester_id: 'debug-user',
      requester_name: 'Debug User',
      message: 'Hello',
    },
  },
  {
    value: 'feedback.received',
    labelKey: 'agents.debugFeedbackReceived',
    text: 'The user submitted feedback.',
    data: {
      rating: 5,
      content: 'Debug feedback',
    },
  },
  {
    value: 'custom',
    labelKey: 'agents.debugCustomEvent',
    text: '',
    data: {},
  },
] as const;

function createDebugSessionId(agentId: string) {
  const nonce = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
  return `webui:${agentId}:${nonce}`;
}

export default function AgentDebugPanel({
  agentId,
  supportedEventPatterns = ['*'],
}: AgentDebugPanelProps) {
  const { t } = useTranslation();
  const [preset, setPreset] = useState('message.received');
  const [customEventType, setCustomEventType] = useState('custom.event');
  const [inputText, setInputText] = useState('');
  const [eventDataText, setEventDataText] = useState('{}');
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<DebugEntry[]>([]);
  const sessionIdRef = useRef(createDebugSessionId(agentId));

  const eventType = preset === 'custom' ? customEventType.trim() : preset;
  const isMessageEvent = eventType.startsWith('message.');
  const supportedLabel = useMemo(
    () => supportedEventPatterns.join(', '),
    [supportedEventPatterns],
  );

  function selectPreset(value: string) {
    setPreset(value);
    const nextPreset = EVENT_PRESETS.find((item) => item.value === value);
    if (!nextPreset) return;
    setInputText(nextPreset.text);
    setEventDataText(JSON.stringify(nextPreset.data, null, 2));
  }

  function resetSession() {
    sessionIdRef.current = createDebugSessionId(agentId);
    setEntries([]);
  }

  async function runDebugEvent() {
    if (!eventType) {
      toast.error(t('agents.debugEventTypeRequired'));
      return;
    }
    if (isMessageEvent && !inputText.trim()) {
      toast.error(t('agents.debugInputRequired'));
      return;
    }

    let eventData: Record<string, unknown>;
    try {
      const parsed = JSON.parse(eventDataText || '{}');
      if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
        throw new Error('payload must be an object');
      }
      eventData = parsed as Record<string, unknown>;
    } catch {
      toast.error(t('agents.debugInvalidPayload'));
      return;
    }

    const requestId = globalThis.crypto?.randomUUID?.() ?? String(Date.now());
    setEntries((current) => [
      ...current,
      {
        id: `input:${requestId}`,
        direction: 'input',
        eventType,
        text: inputText.trim() || JSON.stringify(eventData, null, 2),
      },
    ]);
    setRunning(true);
    try {
      const result = await httpClient.debugAgent(agentId, {
        event_type: eventType,
        text: inputText.trim(),
        data: eventData,
        conversation_id: sessionIdRef.current,
      });
      setEntries((current) => [
        ...current,
        {
          id: `output:${result.event_id}`,
          direction: 'output',
          eventType,
          text: result.final_text || t('agents.debugNoTextOutput'),
        },
      ]);
      if (isMessageEvent) setInputText('');
    } catch (error) {
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : t('agents.debugRunFailed');
      setEntries((current) => [
        ...current,
        {
          id: `error:${requestId}`,
          direction: 'error',
          eventType,
          text: message || t('agents.debugRunFailed'),
        },
      ]);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col">
      <div className="shrink-0 space-y-3 border-b p-3">
        <div className="flex items-end gap-2">
          <div className="min-w-0 flex-1 space-y-1.5">
            <Label>{t('agents.debugEventType')}</Label>
            <Select value={preset} onValueChange={selectPreset}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EVENT_PRESETS.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {t(item.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={resetSession}
            title={t('agents.debugResetSession')}
          >
            <RotateCcw className="size-4" />
          </Button>
        </div>

        {preset === 'custom' && (
          <div className="space-y-1.5">
            <Label htmlFor="agent-debug-custom-event">
              {t('agents.debugCustomEventType')}
            </Label>
            <Input
              id="agent-debug-custom-event"
              value={customEventType}
              onChange={(event) => setCustomEventType(event.target.value)}
              placeholder="custom.event"
            />
          </div>
        )}

        <Alert className="py-2">
          <AlertTriangle />
          <AlertTitle>{t('agents.debugActualRun')}</AlertTitle>
          <AlertDescription className="text-xs">
            {t('agents.debugActualRunDescription')}
          </AlertDescription>
        </Alert>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-3">
          <p className="text-sm font-medium">{t('agents.debugTranscript')}</p>
          <p className="text-xs text-muted-foreground">
            {t('agents.debugTranscriptDescription')}
          </p>
        </div>
        {entries.length === 0 ? (
          <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            {t('agents.debugEmptyTranscript')}
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((entry) => (
              <div
                key={entry.id}
                className={`rounded-lg border p-3 ${
                  entry.direction === 'output'
                    ? 'border-primary/20 bg-primary/5'
                    : entry.direction === 'error'
                      ? 'border-destructive/30 bg-destructive/5'
                      : 'bg-muted/40'
                }`}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <Badge variant="outline">{entry.eventType}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {entry.direction === 'output'
                      ? t('agents.debugAgentOutput')
                      : entry.direction === 'error'
                        ? t('common.error')
                        : t('agents.debugTestInput')}
                  </span>
                </div>
                <pre className="min-w-0 whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">
                  {entry.text}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 space-y-3 border-t p-3">
        <div className="space-y-1.5">
          <Label htmlFor="agent-debug-input">
            {isMessageEvent
              ? t('agents.debugMessageInput')
              : t('agents.debugEventSummary')}
          </Label>
          <Textarea
            id="agent-debug-input"
            value={inputText}
            onChange={(event) => setInputText(event.target.value)}
            className="min-h-20 resize-y"
            placeholder={t('agents.debugInputPlaceholder')}
          />
        </div>

        <details className="rounded-md border bg-muted/20 px-3 py-2">
          <summary className="cursor-pointer text-xs font-medium">
            {t('agents.debugEventPayload')}
          </summary>
          <div className="mt-2 space-y-2">
            <p className="text-xs text-muted-foreground">
              {t('agents.debugSupportedEvents')}: {supportedLabel}
            </p>
            <Textarea
              id="agent-debug-payload"
              value={eventDataText}
              onChange={(event) => setEventDataText(event.target.value)}
              className="min-h-28 resize-y font-mono text-xs"
              spellCheck={false}
            />
          </div>
        </details>

        <Button
          type="button"
          className="w-full"
          disabled={running}
          onClick={runDebugEvent}
        >
          {running ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}
          {running ? t('agents.debugRunning') : t('agents.debugRun')}
        </Button>
      </div>
    </div>
  );
}
