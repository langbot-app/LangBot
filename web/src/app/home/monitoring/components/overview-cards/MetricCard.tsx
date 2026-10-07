'use client';

import React from 'react';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export interface MetricCardProps {
  /** Small label, sitting next to the icon. */
  label: string;
  description?: string;
  /** The card's headline value; a node so it can carry a badge. */
  value?: React.ReactNode;
  /** Icon of the tinted tile on the leading edge. */
  icon?: React.ReactNode;
  /** Muted line under the value. */
  hint?: React.ReactNode;
  /** Tile colour as a hex value; defaults to the muted token. */
  accent?: string;
  /** Rendered at the card's top-right (tooltip trigger, help dialog, badge). */
  action?: React.ReactNode;
  /** Extra body under the value, for composite cards (stat grids, status rows). */
  children?: React.ReactNode;
  loading?: boolean;
  className?: string;
}

/**
 * The dashboard's one metric card: tinted icon tile and label on the leading
 * edge, value, then a muted hint. Token, execution, feedback and runtime
 * counters all render through it, so their rows and internal spacing match
 * instead of each surface inventing its own card.
 */
export function MetricCard({
  label,
  description,
  value,
  icon,
  hint,
  accent,
  action,
  children,
  loading,
  className,
}: MetricCardProps) {
  return (
    <Card className={cn('gap-3 p-4', className)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {icon ? (
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
              style={{
                backgroundColor: accent ? `${accent}1a` : 'var(--muted)',
                color: accent || 'var(--muted-foreground)',
              }}
            >
              {icon}
            </span>
          ) : null}
          <span className="text-sm text-muted-foreground">{label}</span>
          {description && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
                  aria-label={label}
                >
                  <Info className="h-3.5 w-3.5" aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent
                sideOffset={6}
                className="max-w-[min(20rem,calc(100vw-2rem))] text-sm leading-relaxed"
              >
                {description}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
        {action}
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-3 w-20" />
        </div>
      ) : (
        <>
          {value != null && value !== '' && (
            <div className="text-2xl font-semibold tabular-nums text-foreground">
              {value}
            </div>
          )}
          {hint != null && hint !== '' && (
            <div className="text-xs text-muted-foreground">{hint}</div>
          )}
          {children}
        </>
      )}
    </Card>
  );
}

export default MetricCard;
