import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import TourOverlay, {
  getTourPosition,
  type TargetRect,
  type PopoverPosition,
} from './TourOverlay';

export interface GuidedTourStep {
  id: string;
  target: string;
  title: string;
  description: string;
  onEnter?: () => void;
  action?: {
    href: string;
    label: string;
  };
}

interface GuidedTourProps {
  enabled?: boolean;
  storageKey: string;
  steps: GuidedTourStep[];
  testId?: string;
}

function readProgress(storageKey: string): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return localStorage.getItem(storageKey);
  } catch {
    return null;
  }
}

function storeProgress(storageKey: string, value: string) {
  try {
    localStorage.setItem(storageKey, value);
  } catch {
    // Keep the tour usable when browser storage is unavailable.
  }
}

export default function GuidedTour({
  enabled = true,
  storageKey,
  steps,
  testId = 'guided-tour',
}: GuidedTourProps) {
  const initialProgress = useMemo(() => readProgress(storageKey), [storageKey]);
  const [finished, setFinished] = useState(initialProgress === 'completed');
  const [activeStepId, setActiveStepId] = useState<string | null>(() =>
    initialProgress === 'completed' ? null : initialProgress,
  );
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [popoverPosition, setPopoverPosition] =
    useState<PopoverPosition | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const previousStorageKeyRef = useRef(storageKey);

  const activeIndex = steps.findIndex((step) => step.id === activeStepId);
  const activeStep = activeIndex >= 0 ? steps[activeIndex] : undefined;
  const isPopoverPositioned = popoverPosition !== null;

  useEffect(() => {
    if (previousStorageKeyRef.current === storageKey) return;
    previousStorageKeyRef.current = storageKey;
    const progress = readProgress(storageKey);
    setFinished(progress === 'completed');
    setActiveStepId(progress === 'completed' ? null : progress);
    setTargetRect(null);
    setPopoverPosition(null);
  }, [storageKey]);

  useEffect(() => {
    if (!enabled || steps.length === 0 || finished) return;

    const currentIndex = steps.findIndex((step) => step.id === activeStepId);
    const nextIndex = currentIndex < 0 ? 0 : currentIndex;

    if (nextIndex !== currentIndex) {
      const nextStep = steps[nextIndex];
      setActiveStepId(nextStep.id);
      storeProgress(storageKey, nextStep.id);
    }
  }, [activeStepId, enabled, finished, steps, storageKey]);

  useEffect(() => {
    if (enabled && !finished) activeStep?.onEnter?.();
  }, [activeStep, enabled, finished]);

  const measure = useCallback(() => {
    if (!activeStep) return;
    const target = document.querySelector<HTMLElement>(activeStep.target);
    if (!target) {
      setTargetRect(null);
      setPopoverPosition(null);
      return;
    }

    const rect = target.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const nextRect: TargetRect = {
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
      left: rect.left,
      width: rect.width,
      height: rect.height,
    };
    setTargetRect(nextRect);

    setPopoverPosition(
      getTourPosition(nextRect, popoverRef.current?.offsetHeight),
    );
  }, [activeStep]);

  useEffect(() => {
    if (!enabled || !activeStep) return;
    const target = document.querySelector<HTMLElement>(activeStep.target);
    target?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

    const frame = window.requestAnimationFrame(measure);
    const delayedMeasure = window.setTimeout(measure, 240);
    const observer = new MutationObserver(measure);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(delayedMeasure);
      observer.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [activeStep, enabled, measure]);

  useEffect(() => {
    if (isPopoverPositioned) measure();
  }, [activeStep?.id, isPopoverPositioned, measure]);

  const finishTour = useCallback(() => {
    setTargetRect(null);
    setPopoverPosition(null);
    storeProgress(storageKey, 'completed');
    setFinished(true);
    setActiveStepId(null);
  }, [storageKey]);

  const handlePrevious = useCallback(() => {
    const previousStep = steps[activeIndex - 1];
    if (!previousStep) return;
    storeProgress(storageKey, previousStep.id);
    setActiveStepId(previousStep.id);
  }, [activeIndex, steps, storageKey]);

  const handleNext = useCallback(() => {
    if (!activeStep) return;
    const nextStep = steps[activeIndex + 1];
    if (!nextStep) {
      finishTour();
      return;
    }
    storeProgress(storageKey, nextStep.id);
    setActiveStepId(nextStep.id);
  }, [activeIndex, activeStep, finishTour, steps, storageKey]);

  if (
    !enabled ||
    !activeStep ||
    !targetRect ||
    !popoverPosition ||
    typeof document === 'undefined'
  ) {
    return null;
  }

  return (
    <TourOverlay
      testId={testId}
      stepId={activeStep.id}
      current={activeIndex + 1}
      total={steps.length}
      title={activeStep.title}
      description={activeStep.description}
      action={activeStep.action}
      targetRect={targetRect}
      position={popoverPosition}
      popoverRef={popoverRef}
      onPrevious={activeIndex > 0 ? handlePrevious : undefined}
      onNext={handleNext}
      onSkip={finishTour}
    />
  );
}
