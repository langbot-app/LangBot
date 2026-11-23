import TourOverlay, {
  getTourPosition,
  type TargetRect,
  type PopoverPosition,
} from '../guided-tour/TourOverlay';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSidebar } from '@/components/ui/sidebar';

const SIDEBAR_GUIDE_STORAGE_KEY = 'langbot_sidebar_guide_v1';

const GUIDE_STEP_IDS = [
  'monitoring',
  'bots',
  'pipelines',
  'knowledge',
  'plugins',
  'add-extension',
  'models',
  'api-integration',
] as const;

type GuideStepId = (typeof GUIDE_STEP_IDS)[number];

function loadStoredStep(): number | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = localStorage.getItem(SIDEBAR_GUIDE_STORAGE_KEY);
    if (stored === 'completed') return null;

    const parsed = Number.parseInt(stored ?? '0', 10);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return Math.min(parsed, GUIDE_STEP_IDS.length - 1);
  } catch {
    return 0;
  }
}

function storeGuideProgress(value: string) {
  try {
    localStorage.setItem(SIDEBAR_GUIDE_STORAGE_KEY, value);
  } catch {
    // The guide remains usable when browser storage is unavailable.
  }
}

function getTarget(stepId: GuideStepId): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  return document.querySelector<HTMLElement>(
    `[data-sidebar-guide="${stepId}"]`,
  );
}

function findAvailableStep(startIndex: number, direction = 1): number | null {
  for (
    let index = startIndex;
    index >= 0 && index < GUIDE_STEP_IDS.length;
    index += direction
  ) {
    const target = getTarget(GUIDE_STEP_IDS[index]);
    if (target) return index;
  }
  return null;
}

export function SidebarGuide() {
  const { t } = useTranslation();
  const { isMobile, open, openMobile, setOpen, setOpenMobile } = useSidebar();
  const [stepIndex, setStepIndex] = useState<number | null>(loadStoredStep);
  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [popoverPosition, setPopoverPosition] =
    useState<PopoverPosition | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const originalSidebarStateRef = useRef<{
    open: boolean;
    openMobile: boolean;
  } | null>(null);

  const activeStepId =
    stepIndex === null ? null : (GUIDE_STEP_IDS[stepIndex] ?? null);

  const visibleStepCount = GUIDE_STEP_IDS.filter((stepId) =>
    getTarget(stepId),
  ).length;

  const visibleStepNumber = activeStepId
    ? GUIDE_STEP_IDS.slice(0, stepIndex ?? 0).filter((stepId) =>
        getTarget(stepId),
      ).length + 1
    : 0;
  const isPopoverReady = popoverPosition !== null;

  const restoreSidebarState = useCallback(() => {
    const original = originalSidebarStateRef.current;
    if (!original) return;
    if (isMobile) {
      setOpenMobile(original.openMobile);
    } else {
      setOpen(original.open);
    }
    originalSidebarStateRef.current = null;
  }, [isMobile, setOpen, setOpenMobile]);

  const completeGuide = useCallback(() => {
    storeGuideProgress('completed');
    setStepIndex(null);
    setTargetRect(null);
    setPopoverPosition(null);
    restoreSidebarState();
  }, [restoreSidebarState]);

  const measure = useCallback(() => {
    if (!activeStepId) return;
    const target = getTarget(activeStepId);
    if (!target) return;

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
  }, [activeStepId]);

  useEffect(() => {
    if (stepIndex === null) return;

    if (!originalSidebarStateRef.current) {
      originalSidebarStateRef.current = { open, openMobile };
    }

    if (isMobile) {
      setOpenMobile(true);
    } else {
      setOpen(true);
    }
  }, [isMobile, open, openMobile, setOpen, setOpenMobile, stepIndex]);

  useEffect(() => {
    if (stepIndex === null) return;

    const frame = window.requestAnimationFrame(() => {
      const availableIndex = findAvailableStep(stepIndex);
      if (availableIndex === null) {
        completeGuide();
        return;
      }
      if (availableIndex !== stepIndex) {
        storeGuideProgress(String(availableIndex));
        setStepIndex(availableIndex);
      }
    });

    return () => window.cancelAnimationFrame(frame);
  }, [completeGuide, stepIndex]);

  useEffect(() => {
    if (!activeStepId) return;
    const target = getTarget(activeStepId);
    if (!target) return;

    target.scrollIntoView({ block: 'nearest' });

    const frame = window.requestAnimationFrame(measure);
    const delayedMeasure = window.setTimeout(measure, 260);
    const resizeObserver = new ResizeObserver(measure);
    resizeObserver.observe(target);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);

    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(delayedMeasure);
      resizeObserver.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [activeStepId, measure]);

  useEffect(() => {
    if (!isPopoverReady) return;
    measure();
  }, [activeStepId, isPopoverReady, measure]);

  useEffect(() => {
    if (stepIndex === null) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [stepIndex]);

  function handlePrevious() {
    if (stepIndex === null) return;
    const previousIndex = findAvailableStep(stepIndex - 1, -1);
    if (previousIndex === null) return;
    storeGuideProgress(String(previousIndex));
    setStepIndex(previousIndex);
  }

  function handleConfirm() {
    if (stepIndex === null) return;
    const nextIndex = findAvailableStep(stepIndex + 1);
    if (nextIndex === null) {
      completeGuide();
      return;
    }

    storeGuideProgress(String(nextIndex));
    setStepIndex(nextIndex);
  }

  if (
    !activeStepId ||
    !targetRect ||
    !popoverPosition ||
    typeof document === 'undefined'
  ) {
    return null;
  }

  return (
    <TourOverlay
      testId="sidebar-guide"
      stepId={activeStepId}
      current={visibleStepNumber}
      total={visibleStepCount}
      title={t(`sidebarGuide.steps.${activeStepId}.title`)}
      description={t(`sidebarGuide.steps.${activeStepId}.description`)}
      targetRect={targetRect}
      position={popoverPosition}
      popoverRef={popoverRef}
      modal
      onPrevious={
        findAvailableStep((stepIndex ?? 0) - 1, -1) !== null
          ? handlePrevious
          : undefined
      }
      onNext={handleConfirm}
      onSkip={completeGuide}
    />
  );
}
