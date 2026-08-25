import { ReactNode, useState } from 'react';
import { BarChart3, Bug, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ProcessorMonitoringView {
  label: string;
  content: ReactNode;
}

interface ProcessorDetailWorkbenchProps {
  title: string;
  saveLabel: string;
  saveFormId: string;
  canSave: boolean;
  isDirty: boolean;
  isSaving: boolean;
  configTitle: string;
  configContent: ReactNode;
  debugTitle?: string;
  debugContent?: ReactNode;
  debugConnected?: boolean;
  debugConnectedLabel?: string;
  debugDisconnectedLabel?: string;
  unsavedLabel?: string;
  monitoring?: ProcessorMonitoringView;
}

export default function ProcessorDetailWorkbench({
  title,
  saveLabel,
  saveFormId,
  canSave,
  isDirty,
  isSaving,
  configTitle,
  configContent,
  debugTitle,
  debugContent,
  debugConnected,
  debugConnectedLabel,
  debugDisconnectedLabel,
  unsavedLabel,
  monitoring,
}: ProcessorDetailWorkbenchProps) {
  const [activeView, setActiveView] = useState<'workbench' | 'monitoring'>(
    'workbench',
  );
  const hasDebug = Boolean(debugTitle && debugContent);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 pb-4">
        <h1 className="text-xl font-semibold">{title}</h1>
        <div className="flex items-center gap-2">
          {monitoring && (
            <Button
              type="button"
              variant={activeView === 'monitoring' ? 'secondary' : 'outline'}
              onClick={() =>
                setActiveView((current) =>
                  current === 'monitoring' ? 'workbench' : 'monitoring',
                )
              }
            >
              <BarChart3 className="size-4" />
              {monitoring.label}
            </Button>
          )}
          {canSave && activeView === 'workbench' && (
            <Button
              type="submit"
              form={saveFormId}
              disabled={!isDirty || isSaving}
            >
              {saveLabel}
            </Button>
          )}
        </div>
      </div>

      {activeView === 'monitoring' && monitoring ? (
        <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-card p-4">
          {monitoring.content}
        </section>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto lg:overflow-hidden">
          <div
            className={cn(
              'grid min-h-0 gap-3 lg:h-full',
              hasDebug
                ? 'lg:grid-cols-[minmax(20rem,0.72fr)_minmax(0,1.28fr)]'
                : 'grid-cols-1',
            )}
          >
            {hasDebug && (
              <section
                aria-label={debugTitle}
                className="flex min-h-[32rem] min-w-0 flex-col overflow-hidden rounded-xl border bg-card lg:min-h-0"
              >
                <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-4">
                  <div className="flex min-w-0 items-center gap-2 font-medium">
                    <Bug className="size-4 shrink-0" />
                    <span className="truncate">{debugTitle}</span>
                  </div>
                  {debugConnected !== undefined && (
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span
                        className={cn(
                          'size-2 rounded-full',
                          debugConnected ? 'bg-emerald-500' : 'bg-destructive',
                        )}
                      />
                      {debugConnected
                        ? debugConnectedLabel
                        : debugDisconnectedLabel}
                    </span>
                  )}
                </div>
                <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
                  {debugContent}
                </div>
              </section>
            )}

            <section
              aria-label={configTitle}
              className="flex min-h-[36rem] min-w-0 flex-col overflow-hidden rounded-xl border bg-card lg:min-h-0"
            >
              <div className="flex h-12 shrink-0 items-center gap-2 border-b px-4 font-medium">
                <Settings className="size-4" />
                <span className="truncate">{configTitle}</span>
                {isDirty && (
                  <span className="ml-auto flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                    <span className="size-1.5 rounded-full bg-amber-500" />
                    {unsavedLabel}
                  </span>
                )}
              </div>
              <div className="min-h-0 min-w-0 flex-1 overflow-hidden p-4">
                {configContent}
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
