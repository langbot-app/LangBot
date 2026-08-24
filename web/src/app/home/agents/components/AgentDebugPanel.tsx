import { useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  AlertTriangle,
  Braces,
  LoaderCircle,
  MessageSquare,
  Play,
  RotateCcw,
} from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
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
    <div className="mx-auto grid w-full min-w-0 max-w-6xl gap-6 pb-8 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)]">
      <Card className="min-w-0">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="flex items-center gap-2">
                {isMessageEvent ? (
                  <MessageSquare className="size-5" />
                ) : (
                  <Braces className="size-5" />
                )}
                {t('agents.debugTitle')}
              </CardTitle>
              <CardDescription>{t('agents.debugDescription')}</CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={resetSession}
            >
              <RotateCcw className="size-4" />
              {t('agents.debugResetSession')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <Alert>
            <AlertTriangle />
            <AlertTitle>{t('agents.debugActualRun')}</AlertTitle>
            <AlertDescription>
              {t('agents.debugActualRunDescription')}
            </AlertDescription>
          </Alert>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
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
            {preset === 'custom' && (
              <div className="space-y-2">
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
          </div>

          <div className="space-y-2">
            <Label htmlFor="agent-debug-input">
              {isMessageEvent
                ? t('agents.debugMessageInput')
                : t('agents.debugEventSummary')}
            </Label>
            <Textarea
              id="agent-debug-input"
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              className="min-h-24 resize-y"
              placeholder={t('agents.debugInputPlaceholder')}
            />
          </div>

          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor="agent-debug-payload">
                {t('agents.debugEventPayload')}
              </Label>
              <span className="text-xs text-muted-foreground">
                {t('agents.debugSupportedEvents')}: {supportedLabel}
              </span>
            </div>
            <Textarea
              id="agent-debug-payload"
              value={eventDataText}
              onChange={(event) => setEventDataText(event.target.value)}
              className="min-h-40 resize-y font-mono text-xs"
              spellCheck={false}
            />
          </div>

          <div className="flex justify-end">
            <Button type="button" disabled={running} onClick={runDebugEvent}>
              {running ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              {running ? t('agents.debugRunning') : t('agents.debugRun')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="min-h-[28rem] min-w-0">
        <CardHeader>
          <CardTitle>{t('agents.debugTranscript')}</CardTitle>
          <CardDescription>
            {t('agents.debugTranscriptDescription')}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {entries.length === 0 ? (
            <div className="flex min-h-72 items-center justify-center rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              {t('agents.debugEmptyTranscript')}
            </div>
          ) : (
            <div className="max-h-[42rem] space-y-4 overflow-y-auto pr-1">
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
        </CardContent>
      </Card>
    </div>
  );
}
