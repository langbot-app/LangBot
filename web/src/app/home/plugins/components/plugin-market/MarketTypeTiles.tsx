import { useRef } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { cn } from '@/lib/utils';

export interface TypeTileOption {
  value: string;
  label: string;
  description: string;
  icon: LucideIcon;
  /** Icon tile colours when idle. */
  tone: string;
  /** Tile background + inset ring when selected. */
  activeTone: string;
  /** Icon tile colours when selected. */
  activeIcon: string;
  count?: number;
}

export interface ChipOption {
  value: string;
  label: string;
  icon?: LucideIcon | null;
}

/**
 * Extension type picker for the marketplace (LANG-439 redesign): four peer
 * types as tiles with a one-line description and live count.
 */
export function MarketTypeTiles({
  options,
  value,
  onChange,
}: {
  options: TypeTileOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  // Mouse users switch on press (feels instant); keyboard and touch still
  // switch on click so Enter/Space work and touch scrolling is not hijacked.
  const pressedByMouse = useRef(false);
  return (
    <div className="grid w-full grid-cols-2 gap-2.5 lg:grid-cols-4 lg:gap-3">
      {options.map((o) => {
        const Icon = o.icon;
        const active = value === o.value;
        return (
          <Button
            key={o.value}
            type="button"
            variant="ghost"
            aria-pressed={active}
            onPointerDown={(e) => {
              pressedByMouse.current = e.pointerType === 'mouse';
              if (pressedByMouse.current && e.button === 0 && !active) {
                onChange(o.value);
              }
            }}
            onClick={(e) => {
              if (e.detail === 0 || !pressedByMouse.current) onChange(o.value);
            }}
            className={cn(
              'h-auto min-w-0 select-none justify-start gap-3 whitespace-normal rounded-xl p-3 text-left font-normal transition-colors duration-100 active:translate-y-0 active:scale-100',
              active
                ? cn('ring-1 ring-inset', o.activeTone)
                : 'bg-muted/40 hover:bg-muted/80',
            )}
          >
            <span
              className={cn(
                'flex size-10 shrink-0 items-center justify-center rounded-lg transition-colors',
                active ? o.activeIcon : o.tone,
              )}
            >
              <Icon className="size-5" strokeWidth={1.75} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-baseline gap-1.5">
                <span className="truncate text-sm font-medium">{o.label}</span>
                {typeof o.count === 'number' && (
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {o.count}
                  </span>
                )}
              </span>
              <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                {o.description}
              </span>
            </span>
          </Button>
        );
      })}
    </div>
  );
}

/** Single-select chips for secondary filters (plugin components, Runner usage). */
export function MarketChipRow({
  options,
  value,
  onChange,
  size = 'default',
}: {
  options: ChipOption[];
  value: string;
  onChange: (value: string) => void;
  size?: 'default' | 'sm';
}) {
  return (
    <ToggleGroup
      type="single"
      variant="outline"
      size="sm"
      spacing={2}
      value={value}
      onValueChange={(v) => v && onChange(v)}
      className="scrollbar-hide w-full justify-start overflow-x-auto"
    >
      {options.map((o) => {
        const Icon = o.icon;
        return (
          <ToggleGroupItem
            key={o.value}
            value={o.value}
            aria-label={o.label}
            className={cn(
              'shrink-0 cursor-pointer rounded-full px-3 data-[state=on]:border-foreground data-[state=on]:bg-foreground data-[state=on]:text-background',
              size === 'sm' ? 'h-6 text-[11px]' : 'h-7 text-xs',
            )}
          >
            {Icon && <Icon className="size-3.5" />}
            {o.label}
          </ToggleGroupItem>
        );
      })}
    </ToggleGroup>
  );
}
