import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CircleAlert,
  CircleCheck,
  CircleX,
  Maximize,
  Minus,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import type { WorkflowStep, WorkflowStepType } from '@/app/infra/entities/api';
import { STEP_META, stepBranches } from '../lib/catalog';
import { childAt, insertStep, stepById, type Slot } from '../lib/tree';
import { useEditor } from './EditorContext';
import StepPicker from './StepPicker';
import { stepSummary } from './summary';
import { useRefLabel } from './variables';

function AddButton({
  slot,
  occupied,
  prominent,
}: {
  slot: Slot;
  occupied: boolean;
  prominent?: boolean;
}) {
  const { t } = useTranslation();
  const { setGraph, select, resources, readOnly } = useEditor();
  const [open, setOpen] = useState(false);
  if (readOnly) return null;
  const pick = (type: WorkflowStepType) => {
    let created = '';
    setGraph((graph) => {
      const result = insertStep(
        graph,
        slot,
        type,
        t(`workflows.steps.${type}`),
      );
      created = result.id;
      return result.graph;
    });
    setOpen(false);
    setTimeout(() => created && select(created), 0);
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t('workflows.canvas.addStep')}
          data-testid="add-step"
          className={cn(
            'grid place-items-center rounded-full border bg-background text-muted-foreground shadow-sm transition hover:border-primary hover:text-primary',
            prominent
              ? 'size-7'
              : 'size-5 opacity-0 group-hover/link:opacity-100',
            open && 'border-primary text-primary opacity-100',
          )}
        >
          <Plus className={prominent ? 'size-4' : 'size-3'} />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" side="right" align="start">
        <StepPicker
          available={resources.availableTypes}
          allowTerminal={!occupied}
          onPick={pick}
        />
      </PopoverContent>
    </Popover>
  );
}

function Link({ slot, active }: { slot: Slot; active?: boolean }) {
  return (
    <div className="group/link relative flex h-8 w-full justify-center">
      <div
        className={cn('h-full w-px', active ? 'bg-emerald-400' : 'bg-border')}
      />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
        <AddButton slot={slot} occupied />
      </div>
    </div>
  );
}

function StepCard({ step }: { step: WorkflowStep }) {
  const { t } = useTranslation();
  const { selected, select, issues, lastRun, resources } = useEditor();
  const label = useRefLabel();
  const meta = STEP_META[step.type];
  const Icon = meta?.icon ?? CircleAlert;
  const run = lastRun[step.id];
  const hasRun = Object.keys(lastRun).length > 0;
  const stepIssues = issues.filter(
    (issue) => issue.node_id === step.id && issue.severity === 'error',
  );
  const summary =
    run && run.status !== 'failed'
      ? t('workflows.canvas.ran', {
          duration: run.duration_ms ?? 0,
        }) + (run.branch ? ` · → ${branchLabel(step, run.branch, t)}` : '')
      : stepSummary(step, t, resources, label);
  return (
    <button
      type="button"
      data-testid={`step-${step.id}`}
      onClick={(event) => {
        event.stopPropagation();
        select(step.id);
      }}
      className={cn(
        'relative flex w-60 items-center gap-2.5 rounded-xl border bg-card px-3 py-2.5 text-left shadow-sm transition hover:shadow-md',
        selected === step.id && 'border-primary ring-2 ring-primary/20',
        stepIssues.length > 0 && 'border-destructive/60',
        run?.status === 'completed' && 'border-emerald-400',
        run?.status === 'failed' && 'border-destructive',
        hasRun && !run && 'opacity-45',
      )}
    >
      <span
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-lg',
          meta?.tone,
        )}
      >
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">
          {step.name || t(`workflows.steps.${step.type}`)}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {summary}
        </span>
      </span>
      {run?.status === 'completed' && (
        <CircleCheck className="size-4 shrink-0 text-emerald-500" />
      )}
      {run?.status === 'failed' && (
        <CircleX className="size-4 shrink-0 text-destructive" />
      )}
      {!run && stepIssues.length > 0 && (
        <Tooltip>
          <TooltipTrigger asChild>
            <CircleAlert
              className="size-4 shrink-0 text-destructive"
              data-testid={`issue-${step.id}`}
            />
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-64">
            {stepIssues.map((issue) => (
              <p key={`${issue.code}-${issue.field}`}>
                {t(`workflows.issues.${issue.code}`, {
                  defaultValue: issue.code,
                })}
              </p>
            ))}
          </TooltipContent>
        </Tooltip>
      )}
    </button>
  );
}

function branchLabel(
  step: WorkflowStep,
  branch: string,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  return (
    stepBranches(step, t('workflows.branches.else'), (index) =>
      t('workflows.branches.unnamed', { index: index + 1 }),
    )?.find((item) => item.id === branch)?.label ?? branch
  );
}

function Subtree({ id }: { id: string }) {
  const { t } = useTranslation();
  const { graph, lastRun } = useEditor();
  const step = stepById(graph, id);
  if (!step) return null;
  const meta = STEP_META[step.type];
  const branches = stepBranches(step, t('workflows.branches.else'), (index) =>
    t('workflows.branches.unnamed', { index: index + 1 }),
  );
  const ranBranch = lastRun[id]?.branch;

  const tail = (slot: Slot) => {
    const next = childAt(graph, slot);
    return next ? (
      <>
        <Link slot={slot} active={Boolean(lastRun[next])} />
        <Subtree id={next} />
      </>
    ) : meta?.terminal ? null : (
      <>
        <div className="h-4 w-px bg-border" />
        <AddButton slot={slot} occupied={false} prominent />
      </>
    );
  };

  return (
    <div className="flex flex-col items-center">
      <StepCard step={step} />
      {branches ? (
        <>
          <div className="h-4 w-px bg-border" />
          <div className="flex">
            {branches.map((branch, index) => {
              const first = index === 0;
              const last = index === branches.length - 1;
              const active = ranBranch === branch.id;
              return (
                <div
                  key={branch.id}
                  className="relative flex flex-col items-center px-4"
                >
                  {branches.length > 1 && (
                    <>
                      <div
                        className={cn(
                          'absolute top-0 left-0 h-px w-1/2',
                          !first && 'bg-border',
                        )}
                      />
                      <div
                        className={cn(
                          'absolute top-0 right-0 h-px w-1/2',
                          !last && 'bg-border',
                        )}
                      />
                    </>
                  )}
                  <div className="h-3 w-px bg-border" />
                  <span
                    className={cn(
                      'max-w-40 truncate rounded-full border px-2 py-0.5 text-xs',
                      branch.isElse
                        ? 'bg-muted text-muted-foreground'
                        : 'border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950/40 dark:text-violet-300',
                      active && 'border-emerald-400',
                    )}
                  >
                    {branch.label}
                  </span>
                  {tail({ from: id, branch: branch.id })}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        tail({ from: id })
      )}
    </div>
  );
}

export default function StepCanvas() {
  const { t } = useTranslation();
  const { select } = useEditor();
  const [zoom, setZoom] = useState(1);
  const scroller = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; left: number; top: number }>(
    null,
  );
  const clamp = (value: number) => Math.min(1.5, Math.max(0.5, value));
  return (
    <div className="relative h-full min-h-0">
      <div className="absolute top-3 left-3 z-10 flex items-center gap-0.5 rounded-lg border bg-background p-1 shadow-sm">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('workflows.canvas.zoomOut')}
          onClick={() => setZoom((value) => clamp(value - 0.1))}
        >
          <Minus className="size-4" />
        </Button>
        <span className="w-10 text-center text-xs text-muted-foreground tabular-nums">
          {Math.round(zoom * 100)}%
        </span>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('workflows.canvas.zoomIn')}
          onClick={() => setZoom((value) => clamp(value + 0.1))}
        >
          <Plus className="size-4" />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-7"
          aria-label={t('workflows.canvas.reset')}
          onClick={() => {
            setZoom(1);
            scroller.current?.scrollTo({ left: 0, top: 0 });
          }}
        >
          <Maximize className="size-4" />
        </Button>
      </div>
      <div
        ref={scroller}
        data-testid="workflow-canvas"
        className="h-full overflow-auto rounded-lg bg-[radial-gradient(var(--border)_1px,transparent_1px)] [background-size:18px_18px] cursor-grab active:cursor-grabbing"
        onClick={() => select(null)}
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).closest('button,[role=dialog]'))
            return;
          drag.current = {
            x: event.clientX,
            y: event.clientY,
            left: scroller.current?.scrollLeft ?? 0,
            top: scroller.current?.scrollTop ?? 0,
          };
        }}
        onPointerMove={(event) => {
          if (!drag.current || !scroller.current) return;
          scroller.current.scrollLeft =
            drag.current.left - (event.clientX - drag.current.x);
          scroller.current.scrollTop =
            drag.current.top - (event.clientY - drag.current.y);
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerLeave={() => (drag.current = null)}
      >
        <div
          className="flex min-w-full justify-center px-16 pt-16 pb-40"
          style={{ zoom }}
        >
          <Subtree id="start" />
        </div>
      </div>
    </div>
  );
}
