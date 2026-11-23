import { useState, type ReactNode } from 'react';
import { ChevronLeft } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

type Layer = 'current' | 'latest';

/**
 * Stacks the purchased revision in front of the plan's latest revision. The
 * toggle only changes which card is shown; it never changes the subscription.
 * Layers stay opaque; the back card is dimmed with an overlay instead of
 * opacity so the two cards never show through each other while swapping.
 */
export default function PlanRevisionStack({
  current,
  latest,
}: {
  current: ReactNode;
  latest: ReactNode;
}) {
  const { t } = useTranslation();
  const [front, setFront] = useState<Layer>('current');
  const back: Layer = front === 'current' ? 'latest' : 'current';
  const label = t(
    back === 'latest' ? 'planRevision.showLatest' : 'planRevision.showCurrent',
  );
  const layer = (key: Layer, node: ReactNode) => {
    const isFront = front === key;
    return (
      <div
        key={key}
        data-revision-layer={key}
        data-front={isFront || undefined}
        aria-hidden={!isFront || undefined}
        inert={!isFront}
        className={cn(
          'relative mr-8 flex min-w-0 origin-right rounded-xl bg-background transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform after:pointer-events-none after:absolute after:inset-0 after:rounded-xl after:bg-background after:transition-opacity after:duration-500 [grid-area:stack] motion-reduce:transition-none [&>article]:flex-1',
          isFront
            ? 'z-10 after:opacity-0'
            : 'pointer-events-none z-0 translate-x-8 scale-[0.95] after:opacity-50 [&>article]:shadow-none',
        )}
      >
        {node}
      </div>
    );
  };
  return (
    <div
      className='relative grid min-w-0 [grid-template-areas:"stack"]'
      data-plan-revision-stack
      data-front-layer={front}
    >
      {layer('current', current)}
      {layer('latest', latest)}
      <button
        type="button"
        aria-label={label}
        title={label}
        data-revision-toggle
        onClick={(event) => {
          setFront(back);
          // Pointer clicks should not leave the strip highlighted.
          if (event.detail > 0) event.currentTarget.blur();
        }}
        className="group absolute inset-y-2 right-0 z-20 flex w-8 flex-col items-center justify-center gap-2 rounded-r-xl text-muted-foreground outline-none transition-colors hover:bg-primary/5 hover:text-primary focus-visible:bg-primary/10 focus-visible:text-primary"
      >
        <ChevronLeft
          className="size-4 shrink-0 transition-transform group-hover:-translate-x-0.5"
          aria-hidden
        />
        <span
          className="text-xs font-medium [writing-mode:vertical-rl]"
          aria-hidden
        >
          {t(
            back === 'latest'
              ? 'planRevision.latestTab'
              : 'planRevision.currentTab',
          )}
        </span>
      </button>
    </div>
  );
}
