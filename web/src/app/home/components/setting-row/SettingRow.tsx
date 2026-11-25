import { useState } from 'react';
import { AlertTriangle, ChevronRight, type LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

/** One setting: icon, name and a plain-language summary; expands to edit. */
export function SettingRow({
  id,
  icon: Icon,
  title,
  summary,
  warning,
  defaultOpen = false,
  guide,
  children,
}: {
  id: string;
  icon: LucideIcon;
  title: string;
  summary: string;
  warning?: boolean;
  defaultOpen?: boolean;
  guide?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      data-policy-setting={id}
      data-guide={guide}
    >
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="h-auto w-full justify-start gap-3 rounded-none px-4 py-3 text-left font-normal hover:bg-muted/40"
        >
          <Icon className="size-4 shrink-0 text-muted-foreground" />
          <span className="w-32 shrink-0 text-sm font-medium sm:w-40">
            {title}
          </span>
          <span
            className={cn(
              'min-w-0 flex-1 truncate text-sm text-muted-foreground',
              warning && 'text-amber-700 dark:text-amber-400',
            )}
            data-policy-summary
          >
            {warning && (
              <AlertTriangle className="mr-1 inline size-3.5 -translate-y-px" />
            )}
            {summary}
          </span>
          <ChevronRight
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-90',
            )}
          />
        </Button>
      </CollapsibleTrigger>
      {/* Stay mounted while folded: an invalid draft inside still blocks
          saving, and edits are never dropped by collapsing the row. */}
      <div
        hidden={!open}
        className="space-y-4 border-t bg-muted/20 px-4 py-4 sm:pl-11"
      >
        {children}
      </div>
    </Collapsible>
  );
}

export function SettingGroup({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2" aria-label={title}>
      <div>
        <h3 className="text-sm font-semibold">{title}</h3>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
      <div className="divide-y overflow-hidden rounded-lg border bg-card">
        {children}
      </div>
    </section>
  );
}
