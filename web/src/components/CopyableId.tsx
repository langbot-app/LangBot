import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { copyToClipboard } from '@/app/utils/clipboard';
import { cn } from '@/lib/utils';

/**
 * A platform identifier shown in full (never abbreviated) with a copy button.
 * IDs are what users paste into routing rules and admin lists, so the exact
 * value must always be selectable and copyable.
 */
export default function CopyableId({
  value,
  className,
  label,
}: {
  value: string;
  className?: string;
  /** Accessible name of what is being copied, e.g. "Group ID". */
  label?: string;
}) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <span className={cn('inline-flex min-w-0 items-start gap-1', className)}>
      <code className="min-w-0 select-all break-all rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] leading-5 text-foreground">
        {value}
      </code>
      <button
        type="button"
        className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label={`${t('common.copy')}${label ? ` ${label}` : ''}`}
        title={t('common.copy')}
        onClick={(event) => {
          event.stopPropagation();
          copyToClipboard(value)
            .then(() => {
              setCopied(true);
              toast.success(t('common.copySuccess'));
            })
            .catch(() => toast.error(t('common.copyFailed')));
        }}
      >
        {copied ? (
          <Check className="size-3.5 text-green-600" />
        ) : (
          <Copy className="size-3.5" />
        )}
      </button>
    </span>
  );
}
