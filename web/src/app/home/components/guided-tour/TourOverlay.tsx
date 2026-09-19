import * as DialogPrimitive from '@radix-ui/react-dialog';
import { createPortal } from 'react-dom';
import { useEffect, useRef, type RefObject } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export type TargetRect = Pick<
  DOMRect,
  'top' | 'right' | 'bottom' | 'left' | 'width' | 'height'
>;
export type PopoverPosition = { left: number; top: number; width: number };

const VIEWPORT_GAP = 12;
const MIN_POPOVER_WIDTH = 220;
const MAX_POPOVER_WIDTH = 340;

export function getTourPosition(
  rect: TargetRect,
  height = 250,
): PopoverPosition {
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const rightSpace = viewportWidth - rect.right - VIEWPORT_GAP * 2;
  const leftSpace = rect.left - VIEWPORT_GAP * 2;
  let width = Math.min(MAX_POPOVER_WIDTH, viewportWidth - VIEWPORT_GAP * 2);
  let left = VIEWPORT_GAP;
  let top = rect.top;
  if (rightSpace >= MIN_POPOVER_WIDTH) {
    width = Math.min(MAX_POPOVER_WIDTH, rightSpace);
    left = rect.right + VIEWPORT_GAP;
  } else if (leftSpace >= MIN_POPOVER_WIDTH) {
    width = Math.min(MAX_POPOVER_WIDTH, leftSpace);
    left = rect.left - VIEWPORT_GAP - width;
  } else {
    top =
      rect.bottom + VIEWPORT_GAP + height <= viewportHeight
        ? rect.bottom + VIEWPORT_GAP
        : rect.top - height - VIEWPORT_GAP;
  }
  top = Math.max(
    VIEWPORT_GAP,
    Math.min(top, viewportHeight - height - VIEWPORT_GAP),
  );
  return { left, top, width };
}

interface TourOverlayProps {
  testId: string;
  stepId: string;
  current: number;
  total: number;
  title: string;
  description: string;
  action?: { href: string; label: string };
  targetRect: TargetRect;
  position: PopoverPosition;
  popoverRef: RefObject<HTMLDivElement | null>;
  modal?: boolean;
  onPrevious?: () => void;
  onNext: () => void;
  onSkip: () => void;
}

/** Shared presentation and controls for sidebar and contextual tours. */
export default function TourOverlay({
  testId,
  stepId,
  current,
  total,
  title,
  description,
  action,
  targetRect,
  position,
  popoverRef,
  modal = false,
  onPrevious,
  onNext,
  onSkip,
}: TourOverlayProps) {
  const { t } = useTranslation();
  const nextButtonRef = useRef<HTMLButtonElement | null>(null);
  const titleId = `${testId}-${stepId}-title`;
  const descriptionId = `${testId}-${stepId}-description`;

  useEffect(() => {
    const previousFocus = document.activeElement;
    return () => {
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) {
        previousFocus.focus({ preventScroll: true });
      }
    };
  }, []);

  useEffect(() => {
    nextButtonRef.current?.focus({ preventScroll: true });
  }, [stepId]);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return;
      const button = event.target.closest<HTMLButtonElement>(
        '[data-guided-tour-action]',
      );
      if (!button || button.dataset.guidedTourId !== testId || button.disabled)
        return;
      const action = button.dataset.guidedTourAction;
      if (action === 'skip') onSkip();
      else if (action === 'previous') onPrevious?.();
      else if (action === 'next') onNext();
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (
        !event.defaultPrevented &&
        event.key === 'Escape' &&
        (modal || popoverRef.current?.contains(event.target as Node))
      ) {
        event.preventDefault();
        event.stopPropagation();
        onSkip();
      }
    };
    // Capture stable commands even when browser translation rewrites button children.
    document.addEventListener('click', handleClick, true);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('click', handleClick, true);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [modal, onNext, onPrevious, onSkip, popoverRef, testId]);

  const card = (
    <div
      key={stepId}
      ref={popoverRef}
      role="dialog"
      aria-modal={modal || undefined}
      {...(!modal && {
        'aria-labelledby': titleId,
        'aria-describedby': descriptionId,
      })}
      className={cn(
        'pointer-events-auto fixed flex max-h-[calc(100dvh-24px)] flex-col rounded-lg border bg-popover p-4 text-popover-foreground shadow-xl dark:border-white/20 dark:bg-zinc-900 dark:shadow-[0_12px_40px_rgb(0_0_0_/_0.6)] animate-in fade-in-0 slide-in-from-bottom-1 duration-150 ease-out motion-reduce:animate-none',
        modal ? 'z-[92]' : 'z-[80]',
      )}
      style={position}
    >
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
          {t('guidedTour.label')}
        </span>
        <span className="ml-auto text-xs tabular-nums text-muted-foreground">
          {t('guidedTour.progress', { current, total })}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          data-guided-tour-action="skip"
          data-guided-tour-id={testId}
          className="-my-2 -mr-2 h-7 gap-1 px-2 text-xs text-muted-foreground focus-visible:ring-blue-500/60"
        >
          <X className="size-3.5" />
          {t('guidedTour.skip')}
        </Button>
      </div>
      <div className="min-h-0 overflow-y-auto break-words">
        {modal ? (
          <DialogPrimitive.Title className="text-base font-semibold">
            {title}
          </DialogPrimitive.Title>
        ) : (
          <h2 id={titleId} className="text-base font-semibold">
            {title}
          </h2>
        )}
        {modal ? (
          <DialogPrimitive.Description className="mt-1.5 text-sm leading-6 text-muted-foreground">
            {description}
          </DialogPrimitive.Description>
        ) : (
          <p
            id={descriptionId}
            className="mt-1.5 text-sm leading-6 text-muted-foreground"
          >
            {description}
          </p>
        )}
        {action && (
          <a
            href={action.href}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-blue-600 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60 dark:text-blue-400"
          >
            {action.label}
            <ExternalLink className="size-3.5 shrink-0" />
          </a>
        )}
      </div>
      <div className="mt-4 flex shrink-0 gap-2">
        {onPrevious && (
          <Button
            type="button"
            variant="outline"
            data-guided-tour-action="previous"
            data-guided-tour-id={testId}
            className="h-auto min-h-9 min-w-0 flex-1 whitespace-normal focus-visible:ring-blue-500/60"
          >
            <ChevronLeft className="size-4" />
            {t('guidedTour.previous')}
          </Button>
        )}
        <Button
          ref={nextButtonRef}
          type="button"
          data-guided-tour-action="next"
          data-guided-tour-id={testId}
          className="h-auto min-h-9 min-w-0 flex-1 whitespace-normal focus-visible:ring-blue-500/60"
        >
          {current === total ? (
            <Check className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
          {current === total ? t('guidedTour.finish') : t('guidedTour.next')}
        </Button>
      </div>
    </div>
  );

  return createPortal(
    <div
      data-testid={testId}
      data-active-step={stepId}
      data-tour-modal={modal}
      translate="no"
      className="notranslate pointer-events-none"
    >
      {modal && (
        <div
          className="pointer-events-auto fixed inset-0 z-[90] cursor-default"
          aria-hidden="true"
          onClick={(event) => event.preventDefault()}
        />
      )}
      <div
        data-testid={`${testId}-highlight`}
        aria-hidden="true"
        className={cn(
          'pointer-events-none fixed rounded-md ring-2 ring-blue-500 dark:ring-blue-400 ring-offset-2 ring-offset-background shadow-[0_0_0_9999px_rgb(15_23_42_/_0.4)] dark:shadow-[0_0_0_9999px_rgb(0_0_0_/_0.72)] transition-[top,left,width,height] duration-200 ease-out motion-reduce:transition-none',
          modal ? 'z-[91]' : 'z-[61]',
        )}
        style={{
          top: targetRect.top,
          left: targetRect.left,
          width: targetRect.width,
          height: targetRect.height,
        }}
      />
      {modal ? (
        <DialogPrimitive.Root
          open
          onOpenChange={(open) => {
            if (!open) onSkip();
          }}
        >
          <DialogPrimitive.Content
            asChild
            onPointerDownOutside={(event) => event.preventDefault()}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
              nextButtonRef.current?.focus({ preventScroll: true });
            }}
          >
            {card}
          </DialogPrimitive.Content>
        </DialogPrimitive.Root>
      ) : (
        card
      )}
    </div>,
    document.body,
  );
}
