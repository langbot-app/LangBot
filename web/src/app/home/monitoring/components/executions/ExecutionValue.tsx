import { MessageContentRenderer } from '../MessageContentRenderer';

// Keep arbitrary event properties, including false and zero. Empty transport
// fields are not messages. This also applies to historical serialized payloads.
export function hasExecutionValue(value: unknown): boolean {
  if (value == null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.some(hasExecutionValue);
  if (typeof value === 'object')
    return Object.values(value).some(hasExecutionValue);
  return true;
}

function textProjection(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(textProjection).join('');
  if (value && typeof value === 'object') {
    const item = value as Record<string, unknown>;
    if (item.type === 'text' || item.type === 'Plain')
      return typeof item.text === 'string' ? item.text : '';
  }
  return '';
}

const messageTypes = new Set([
  'Plain',
  'At',
  'AtAll',
  'Image',
  'File',
  'Voice',
  'Quote',
]);
const componentFields: Record<string, string[]> = {
  Plain: ['text'],
  At: ['target', 'display'],
  AtAll: [],
  Image: ['url', 'base64', 'imageId'],
  File: ['name', 'id', 'url', 'size'],
  Voice: ['url', 'base64', 'voiceId', 'length'],
  Quote: ['origin'],
};

export function ExecutionValue({ value }: { value: unknown }) {
  if (!hasExecutionValue(value)) return null;
  if (typeof value === 'string') {
    // Do not reinterpret ordinary strings such as "false", "0", or quoted
    // user text. Only historical structured JSON needs decoding.
    if (/^\s*[\[{]/.test(value)) {
      try {
        return <ExecutionValue value={JSON.parse(value)} />;
      } catch {
        /* Text. */
      }
    }
    return (
      <pre className="whitespace-pre-wrap break-words font-sans text-sm [overflow-wrap:anywhere]">
        {value}
      </pre>
    );
  }
  if (Array.isArray(value))
    return (
      <div className="space-y-2">
        {value.map((item, index) => (
          <ExecutionValue key={index} value={item} />
        ))}
      </div>
    );
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (typeof record.type === 'string' && messageTypes.has(record.type)) {
      const fields = ['type', ...componentFields[record.type]];
      return (
        <>
          <MessageContentRenderer
            content={JSON.stringify([record])}
            maxLines={12}
          />
          <ExecutionValue
            value={Object.fromEntries(
              Object.entries(record).filter(([key]) => !fields.includes(key)),
            )}
          />
        </>
      );
    }
    if (record.type === 'text') {
      const rest = Object.fromEntries(
        Object.entries(record).filter(
          ([key, item]) =>
            key !== 'type' && key !== 'text' && hasExecutionValue(item),
        ),
      );
      return (
        <>
          <ExecutionValue value={record.text} />
          <ExecutionValue value={rest} />
        </>
      );
    }
    if (['image', 'image_url', 'image_base64'].includes(String(record.type))) {
      const image = record.image_url;
      const url =
        typeof image === 'string'
          ? image
          : image && typeof image === 'object'
            ? (image as { url?: string }).url
            : typeof record.image_base64 === 'string'
              ? record.image_base64.startsWith('data:')
                ? record.image_base64
                : `data:image/png;base64,${record.image_base64}`
              : null;
      if (url)
        return (
          <>
            <MessageContentRenderer
              content={JSON.stringify([{ type: 'Image', url }])}
              maxLines={12}
            />
            <ExecutionValue
              value={Object.fromEntries(
                Object.entries(record).filter(
                  ([key]) =>
                    !['type', 'image_url', 'image_base64'].includes(key),
                ),
              )}
            />
          </>
        );
    }
    if (['file', 'file_url', 'file_base64'].includes(String(record.type))) {
      const name = record.file_name ?? record.name;
      return (
        <>
          <MessageContentRenderer
            content={JSON.stringify([{ type: 'File', name }])}
            maxLines={12}
          />
          <ExecutionValue
            value={Object.fromEntries(
              Object.entries(record).filter(
                ([key]) =>
                  !['type', 'file_name', 'name', 'file_base64'].includes(key),
              ),
            )}
          />
        </>
      );
    }
    // Only equal text projections are aliases. Never deduplicate distinct
    // records, or hide different text and structured content from one event.
    const bodyKeys = ['chain', 'message_chain', 'contents', 'content'];
    const bodyKey = bodyKeys.find((key) => hasExecutionValue(record[key]));
    const body = bodyKey ? record[bodyKey] : undefined;
    const duplicateText =
      bodyKey &&
      typeof record.text === 'string' &&
      record.text === textProjection(body);
    const entries = Object.entries(record).filter(
      ([key, item]) =>
        hasExecutionValue(item) && !(key === 'text' && duplicateText),
    );
    return (
      <div className="space-y-2">
        {entries.map(([key, item]) => (
          <div key={key}>
            {!['text', ...bodyKeys, 'attachments'].includes(key) && (
              <div className="text-xs text-muted-foreground">{key}</div>
            )}
            <ExecutionValue value={item} />
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-sm">{String(value)}</span>;
}
