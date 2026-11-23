import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center justify-center rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive transition-[color,box-shadow] overflow-hidden',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground [a&]:hover:bg-primary/90',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground [a&]:hover:bg-secondary/90',
        destructive:
          'border-transparent bg-destructive text-white [a&]:hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40 dark:bg-destructive/60',
        outline:
          'text-foreground [a&]:hover:bg-accent [a&]:hover:text-accent-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

function Badge({
  className,
  variant,
  status,
  asChild = false,
  ...props
}: React.ComponentProps<'span'> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean; status?: string }) {
  const Comp = asChild ? Slot : 'span';

  return (
    <Comp
      data-slot="badge"
      className={cn(
        badgeVariants({ variant: status ? 'outline' : variant }),
        status && statusBadgeClass(status),
        className,
      )}
      {...props}
    />
  );
}

function statusBadgeClass(status: string): string {
  if (
    [
      'completed',
      'success',
      'succeeded',
      'delivered',
      'ready',
      'enabled',
      'connected',
    ].includes(status)
  )
    return 'border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300';
  if (['failed', 'error', 'timeout', 'disconnected'].includes(status))
    return 'border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300';
  if (['running', 'active', 'connecting'].includes(status))
    return 'border-blue-500/25 bg-blue-500/10 text-blue-700 dark:text-blue-300';
  if (
    ['queued', 'pending', 'created', 'claimed', 'waiting', 'warning'].includes(
      status,
    )
  )
    return 'border-amber-500/25 bg-amber-500/10 text-amber-800 dark:text-amber-300';
  if (['mock', 'simulated', 'debug'].includes(status))
    return 'border-violet-500/25 bg-violet-500/10 text-violet-700 dark:text-violet-300';
  return 'border-border bg-muted text-muted-foreground';
}

export { Badge, badgeVariants };
