'use client';

import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';

interface TabStateProps {
  /** Skeleton rows while the tab's data is in flight. */
  loading?: boolean;
  /** Number of skeleton rows; the rhythm matches the loaded content. */
  rows?: number;
  /** Icon for the empty state, in the same muted tone as the copy. */
  icon?: React.ReactNode;
  /** Empty-state headline. */
  title?: string;
  /** Optional second line explaining what would fill the tab. */
  hint?: string;
}

/**
 * The one loading/empty treatment every detail tab uses.
 *
 * Tabs are peers on one fixed-height surface, so they must not each invent their
 * own placeholder shape: a reader switching tabs sees the same skeleton rhythm
 * and the same centred empty card regardless of which record type is empty.
 */
export function TabState({
  loading,
  rows = 6,
  icon,
  title,
  hint,
}: TabStateProps) {
  if (loading) {
    return (
      <div className="space-y-3" role="status" aria-busy="true">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-14 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-muted-foreground">
      {icon}
      {title && <div className="text-sm">{title}</div>}
      {hint && <div className="text-xs">{hint}</div>}
    </div>
  );
}
