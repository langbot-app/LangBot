import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Play, SquareTerminal } from 'lucide-react';
import type {
  CommandDebugResult,
  CommandOutput,
  CommandProcessorDescriptor,
} from '@/app/infra/entities/api';
import { httpClient } from '@/app/infra/http/HttpClient';
import { extractI18nObject } from '@/i18n/I18nProvider';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export function CommandOutputView({ output }: { output: CommandOutput }) {
  if (output.error) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-destructive [overflow-wrap:anywhere]">
        {output.error}
      </p>
    );
  }
  return (
    <div className="space-y-2">
      {output.text && (
        <p className="whitespace-pre-wrap break-words text-sm [overflow-wrap:anywhere]">
          {output.text}
        </p>
      )}
      {output.image_url && (
        <img
          src={output.image_url}
          alt=""
          className="max-h-48 rounded-md border object-contain"
        />
      )}
      {output.image && <p className="text-xs text-muted-foreground">[image]</p>}
      {output.file_url && (
        <a
          href={output.file_url}
          target="_blank"
          rel="noreferrer"
          className="text-sm underline"
        >
          {output.file_name || output.file_url}
        </a>
      )}
    </div>
  );
}

interface DebugEntry {
  input: string;
  result?: CommandDebugResult;
  error?: string;
}

export default function CommandDebugPanel({
  processorId,
  component,
  prefix = '/',
  hasUnsavedChanges,
  beforeRun,
  onRunFinished,
}: {
  processorId: string;
  component: CommandProcessorDescriptor;
  prefix?: string;
  hasUnsavedChanges: boolean;
  beforeRun: () => Promise<boolean>;
  onRunFinished: () => void;
}) {
  const { t } = useTranslation();
  const [command, setCommand] = useState(component.commands[0]?.name ?? '');
  const [args, setArgs] = useState('');
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<DebugEntry[]>([]);
  const selected = component.commands.find((item) => item.name === command);

  async function run() {
    if (!command || running) return;
    if (hasUnsavedChanges && !(await beforeRun())) return;
    const input = `${command} ${args}`.trim();
    setRunning(true);
    try {
      const result = await httpClient.debugCommandProcessor(processorId, input);
      setEntries((current) => [{ input, result }, ...current]);
    } catch (error) {
      setEntries((current) => [
        {
          input,
          error:
            (error as { msg?: string })?.msg ??
            t('agents.commandProcessor.debugFailed'),
        },
        ...current,
      ]);
    } finally {
      setRunning(false);
      onRunFinished();
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      <form
        className="space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
      >
        <div className="flex gap-2">
          <Select value={command} onValueChange={setCommand}>
            <SelectTrigger
              className="w-36 shrink-0 font-mono"
              aria-label={t('agents.commandProcessor.debugCommand')}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {component.commands.map((item) => (
                <SelectItem
                  key={item.name}
                  value={item.name}
                  className="font-mono"
                >
                  {prefix}
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={args}
            onChange={(event) => setArgs(event.target.value)}
            placeholder={t('agents.commandProcessor.debugArgs')}
            aria-label={t('agents.commandProcessor.debugArgs')}
            className="font-mono"
          />
        </div>
        {selected?.description && (
          <p className="text-xs text-muted-foreground">
            {extractI18nObject({
              en_US: '',
              zh_Hans: '',
              ...selected.description,
            })}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={!command || running}>
          {running ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}
          {hasUnsavedChanges
            ? t('agents.commandProcessor.saveAndRun')
            : t('agents.commandProcessor.run')}
        </Button>
      </form>
      <p className="text-xs text-muted-foreground">
        {t('agents.commandProcessor.debugNotice')}
      </p>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
        {entries.length === 0 && (
          <div className="rounded-lg border border-dashed p-6 text-center text-xs text-muted-foreground">
            {t('agents.commandProcessor.debugEmpty')}
          </div>
        )}
        {entries.map((entry, index) => (
          <div
            key={`${entries.length - index}`}
            className="space-y-2 rounded-lg border p-3"
          >
            <div className="flex items-center gap-2">
              <SquareTerminal className="size-4 text-muted-foreground" />
              <code className="min-w-0 flex-1 truncate text-sm">
                {prefix}
                {entry.input}
              </code>
              {entry.result && (
                <Badge
                  status={entry.result.status}
                  variant={
                    entry.result.status === 'failed' ? 'destructive' : 'outline'
                  }
                >
                  {t(`agents.eventProcessor.status_${entry.result.status}`, {
                    defaultValue: entry.result.status,
                  })}
                </Badge>
              )}
            </div>
            {entry.error && (
              <Alert variant="destructive">
                <AlertDescription className="break-words">
                  {entry.error}
                </AlertDescription>
              </Alert>
            )}
            {entry.result?.outputs.map((output, outputIndex) => (
              <div
                key={outputIndex}
                className="rounded-md bg-muted/40 px-3 py-2"
              >
                <CommandOutputView output={output} />
              </div>
            ))}
            {entry.result && entry.result.outputs.length === 0 && (
              <p className="text-xs text-muted-foreground">
                {t('agents.commandProcessor.noOutput')}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
