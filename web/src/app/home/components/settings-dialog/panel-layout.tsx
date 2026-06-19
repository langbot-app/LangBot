import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Shared layout primitives for the settings-dialog panels.
 *
 * Every section renders under the dialog's unified header, so the panels
 * themselves should share the same vertical rhythm: an optional top toolbar
 * (meta on the left, primary action on the right) followed by a scrollable
 * body with consistent padding. Keeping these in one place is what makes the
 * tabs feel like one cohesive surface instead of four separately-styled views.
 */

export function PanelToolbar({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-between gap-3 border-b px-6 py-3',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PanelBody({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn('min-h-0 flex-1 overflow-auto px-6 py-5', className)}>
      {children}
    </div>
  );
}
