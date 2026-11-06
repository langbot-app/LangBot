import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

export interface SelectableGroupCardProps {
  title: ReactNode;
  /** Secondary identifier shown in monospace next to the title. */
  subtitle?: ReactNode;
  /** Extra inline header content, such as an info tooltip. */
  extra?: ReactNode;
  selectedCount: number;
  total: number;
  /** Forces the group open, e.g. while a search query is active. */
  forceOpen?: boolean;
  defaultOpen?: boolean;
  selectAllLabel: string;
  /** Number of items in this group the select-all checkbox can toggle. */
  selectableCount?: number;
  /** Number of selectable items that are currently selected. */
  selectableSelectedCount?: number;
  onToggleAll: (checked: boolean) => void;
  disabled?: boolean;
  children: ReactNode;
}

/**
 * A collapsible group card with a selected/total counter and a group-level
 * select-all checkbox. Shared by every tool/operation picker so they look and
 * behave the same.
 */
export default function SelectableGroupCard({
  title,
  subtitle,
  extra,
  selectedCount,
  total,
  forceOpen = false,
  defaultOpen = true,
  selectAllLabel,
  selectableCount = total,
  selectableSelectedCount = selectedCount,
  onToggleAll,
  disabled = false,
  children,
}: SelectableGroupCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const isOpen = forceOpen || open;
  const allSelected =
    selectableCount > 0 && selectableSelectedCount >= selectableCount;
  const someSelected = selectedCount > 0 && !allSelected;
  const selectAllDisabled = disabled || selectableCount === 0;

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setOpen}
      className="overflow-hidden rounded-lg border bg-card text-card-foreground shadow-sm"
    >
      <div
        className={cn(
          'flex items-center justify-between bg-muted/40 px-3 py-2.5',
          isOpen && 'border-b',
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm font-semibold transition-opacity hover:opacity-80"
          >
            {isOpen ? (
              <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate">{title}</span>
            {subtitle && (
              <span className="shrink-0 font-mono text-xs font-normal text-muted-foreground">
                ({subtitle})
              </span>
            )}
            <Badge
              variant="secondary"
              className="ml-1 shrink-0 text-[11px] font-normal"
            >
              {selectedCount} / {total}
            </Badge>
          </button>
        </CollapsibleTrigger>
        {extra && <span className="ml-1 shrink-0">{extra}</span>}

        <label
          className={cn(
            'flex shrink-0 cursor-pointer select-none items-center gap-1.5 pl-3 text-xs font-medium',
            selectAllDisabled && 'cursor-not-allowed opacity-50',
          )}
        >
          <Checkbox
            checked={
              allSelected ? true : someSelected ? 'indeterminate' : false
            }
            disabled={selectAllDisabled}
            onCheckedChange={() => onToggleAll(!allSelected)}
            aria-label={`${typeof title === 'string' ? title : ''} ${selectAllLabel}`.trim()}
          />
          <span>{selectAllLabel}</span>
        </label>
      </div>

      <CollapsibleContent>
        <div className="divide-y">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}
