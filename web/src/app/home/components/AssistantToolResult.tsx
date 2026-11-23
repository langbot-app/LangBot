import { useEffect, useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  MinusCircle,
  LoaderCircle,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';

export type AssistantTool = {
  name: string;
  arguments: Record<string, unknown>;
  result: unknown;
};

export default function AssistantToolResult({
  tool,
  content,
  defaultCollapsed = true,
}: {
  tool?: AssistantTool;
  content: string;
  /** Keep tool steps quiet until the user requests details. */
  defaultCollapsed?: boolean;
}) {
  const { t } = useTranslation();
  // Track manual toggles so a completing turn cannot fight the user's choice.
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [manual, setManual] = useState(false);

  useEffect(() => {
    if (!manual) setCollapsed(defaultCollapsed);
  }, [defaultCollapsed, manual]);
  const result = tool?.result;
  const data =
    result && typeof result === 'object' && !Array.isArray(result)
      ? (result as Record<string, unknown>)
      : {};
  const running = data.status === 'running';
  const failed = !!data.error;
  const denied = data.status === 'denied';
  const partial = !!data.truncated;
  const Icon = running
    ? LoaderCircle
    : failed || partial
      ? CircleAlert
      : denied
        ? MinusCircle
        : CheckCircle2;
  const items = Array.isArray(result)
    ? result
    : Array.isArray(data.items)
      ? data.items
      : Array.isArray(data.records)
        ? data.records
        : null;
  const total = typeof data.total === 'number' ? data.total : items?.length;
  const kind = tool?.arguments.kind;
  const label =
    tool?.name === 'list_resources' && typeof kind === 'string'
      ? t(`assistant.resources.${kind}`, { defaultValue: kind })
      : t(`assistant.operations.${tool?.name}`, {
          defaultValue: t('assistant.toolResult'),
        });
  const status = running
    ? 'toolRunning'
    : failed
      ? 'failed'
      : denied
        ? 'denied'
        : partial
          ? 'partial'
          : 'completed';
  const url =
    typeof data.url === 'string' &&
    /^\/home\/(pipelines|knowledge)\?id=[\w-]+$/.test(data.url)
      ? data.url
      : null;
  const name =
    typeof data.name === 'string'
      ? data.name
      : typeof tool?.arguments.name === 'string'
        ? tool.arguments.name
        : null;

  if (collapsed) {
    return (
      <button
        type="button"
        className="flex w-full items-center gap-1.5 rounded-md px-0.5 py-1 text-left text-[11px] leading-4 text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-primary"
        aria-expanded={false}
        onClick={() => {
          setManual(true);
          setCollapsed(false);
        }}
      >
        <Icon
          className={`size-3 shrink-0 ${running ? 'animate-spin motion-reduce:animate-none' : ''} ${failed ? 'text-destructive' : 'text-muted-foreground'}`}
        />
        <span className="min-w-0 truncate">{label}</span>
        <span className="ml-auto shrink-0 text-muted-foreground">
          {tool && t(`assistant.${status}`)}
        </span>
        <ChevronDown className="size-3 shrink-0 text-muted-foreground" />
      </button>
    );
  }

  return (
    <section className="min-w-0 space-y-1.5 px-0.5 py-1 text-[11px] leading-4 text-muted-foreground">
      <div className="flex items-center gap-1.5">
        <Icon
          className={`size-3 shrink-0 ${running ? 'animate-spin motion-reduce:animate-none' : ''} ${failed ? 'text-destructive' : 'text-muted-foreground'}`}
        />
        <span className="min-w-0 flex-1 break-words">{label}</span>
        <span className="ml-auto shrink-0 text-[11px] text-muted-foreground">
          {tool && t(`assistant.${status}`)}
        </span>
        <button
          type="button"
          className="shrink-0 text-muted-foreground hover:text-foreground"
          aria-label={t('assistant.details')}
          aria-expanded
          onClick={() => {
            setManual(true);
            setCollapsed(true);
          }}
        >
          <ChevronDown className="size-3 rotate-180" />
        </button>
      </div>
      {running ? (
        <p>{t('assistant.toolRunning')}</p>
      ) : failed ? (
        <p className="text-destructive">{t('assistant.operationFailed')}</p>
      ) : denied ? (
        <p className="text-muted-foreground">
          {t('assistant.operationDenied')}
        </p>
      ) : partial ? (
        <p className="text-muted-foreground">{t('assistant.partial')}</p>
      ) : (
        <>
          {total !== undefined && (
            <p>{t('assistant.found', { count: total })}</p>
          )}
          {name && <p className="break-words">{name}</p>}
          {items && (
            <ul className="space-y-0.5 text-[11px] text-muted-foreground">
              {items.slice(0, 6).map((item: unknown, index: number) => {
                const entry =
                  item && typeof item === 'object'
                    ? (item as Record<string, unknown>)
                    : {};
                return (
                  <li key={index} className="truncate">
                    {String(
                      entry.name ||
                        entry.summary ||
                        entry.action ||
                        entry.uuid ||
                        '—',
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          {url && (
            <a
              className="inline-block text-primary underline"
              href={url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('assistant.openResource')}
            </a>
          )}
        </>
      )}
      <details className="text-[11px] text-muted-foreground">
        <summary className="cursor-pointer">{t('assistant.details')}</summary>
        <pre className="mt-1.5 max-h-32 overflow-auto whitespace-pre-wrap break-all">
          {tool ? JSON.stringify(tool.result, null, 2) : content}
        </pre>
      </details>
    </section>
  );
}
