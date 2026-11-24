import type React from 'react';

/** Bordered section with an icon header, used for each layer of event routing. */
export default function RoutingLayer({
  icon: Icon,
  title,
  description,
  count,
  action,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  count: number;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="overflow-hidden rounded-xl border bg-card"
    >
      <header className="flex items-start gap-3 border-b bg-muted/30 px-4 py-3">
        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-background text-primary shadow-xs">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">{title}</h3>
            {count > 0 && (
              <span className="rounded-full bg-muted-foreground/15 px-1.5 text-[11px] leading-4 tabular-nums">
                {count}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
            {description}
          </p>
        </div>
        {action && <div className="shrink-0 pt-0.5">{action}</div>}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}
