import { ReactNode, useState } from 'react';
import { BarChart3, Bug, Info, Settings } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface ProcessorMonitoringView {
  label: string;
  workbenchLabel: string;
  content: ReactNode;
}

export interface ProcessorDetailStatus {
  label: string;
  description?: string;
  tone: 'neutral' | 'success' | 'warning' | 'error';
}

interface ProcessorDetailWorkbenchProps {
  title: string;
  titleBadge?: ReactNode;
  titleAction?: ReactNode;
  titleControls?: ReactNode;
  headerActions?: ReactNode;
  status?: ProcessorDetailStatus | null;
  saveLabel: string;
  saveFormId: string;
  canSave: boolean;
  isDirty: boolean;
  isSaving: boolean;
  configTitle: string;
  configIcon?: ReactNode;
  configContent: ReactNode;
  debugTitle?: string;
  debugDescription?: string;
  debugContent?: ReactNode;
  debugConnected?: boolean;
  debugConnectedLabel?: string;
  debugDisconnectedLabel?: string;
  unsavedLabel?: string;
  monitoring?: ProcessorMonitoringView;
}

export default function ProcessorDetailWorkbench({
  title,
  titleBadge,
  titleAction,
  titleControls,
  headerActions,
  status,
  saveLabel,
  saveFormId,
  canSave,
  isDirty,
  isSaving,
  configTitle,
  configIcon,
  configContent,
  debugTitle,
  debugDescription,
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
    <Tabs
      value={activeView}
      onValueChange={(value) =>
        setActiveView(value as 'workbench' | 'monitoring')
      }
      className="flex h-full min-h-0 min-w-0 flex-col gap-0"
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 pb-4">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h1 className="truncate text-xl font-semibold">{title}</h1>
          {titleBadge}
          {titleAction}
          {titleControls}
          {monitoring && (
            <TabsList
              aria-label={`${monitoring.workbenchLabel} / ${monitoring.label}`}
              className="ml-1"
            >
              <TabsTrigger value="workbench" className="gap-1.5 px-3">
                <Settings className="size-4" />
                {monitoring.workbenchLabel}
                {isDirty && (
                  <span className="size-1.5 rounded-full bg-amber-500">
                    <span className="sr-only">{unsavedLabel}</span>
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="monitoring" className="gap-1.5 px-3">
                <BarChart3 className="size-4" />
                {monitoring.label}
              </TabsTrigger>
            </TabsList>
          )}
          {status && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Badge
                  variant="outline"
                  role="status"
                  aria-label={status.label}
                  tabIndex={0}
                  className={cn(
                    'rounded-full',
                    status.tone === 'success' &&
                      'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                    status.tone === 'warning' &&
                      'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
                    status.tone === 'error' &&
                      'border-destructive/30 bg-destructive/10 text-destructive',
                    status.tone === 'neutral' &&
                      'border-border bg-muted/50 text-muted-foreground',
                  )}
                >
                  <span
                    className={cn(
                      'size-1.5 rounded-full',
                      status.tone === 'success' && 'bg-emerald-500',
                      status.tone === 'warning' && 'bg-amber-500',
                      status.tone === 'error' && 'bg-destructive',
                      status.tone === 'neutral' &&
                        'animate-pulse bg-muted-foreground',
                    )}
                  />
                  {status.label}
                </Badge>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-72">
                <p className="font-medium">{status.label}</p>
                {status.description && (
                  <p className="mt-1 font-normal opacity-80">
                    {status.description}
                  </p>
                )}
              </TooltipContent>
            </Tooltip>
          )}
        </div>
        <div className="flex items-center gap-2">
          {canSave && activeView === 'workbench' && (
            <Button
              type="submit"
              form={saveFormId}
              disabled={!isDirty || isSaving}
            >
              {saveLabel}
            </Button>
          )}
          {activeView === 'workbench' && headerActions}
        </div>
      </div>

      {monitoring && (
        <TabsContent
          value="monitoring"
          className="mt-0 min-h-0 flex-1 overflow-hidden"
        >
          <Card
            role="region"
            aria-label={monitoring.label}
            className="h-full min-h-0 overflow-y-auto gap-0 p-4"
          >
            {monitoring.content}
          </Card>
        </TabsContent>
      )}

      <TabsContent
        value="workbench"
        forceMount
        className="mt-0 min-h-0 flex-1 overflow-y-auto lg:overflow-hidden data-[state=inactive]:hidden"
      >
        <div
          className={cn(
            'grid min-h-0 gap-3 lg:h-full',
            hasDebug
              ? 'lg:grid-cols-[minmax(20rem,0.72fr)_minmax(0,1.28fr)]'
              : 'grid-cols-1',
          )}
        >
          {hasDebug && (
            <Card
              role="region"
              aria-label={debugTitle}
              className="min-h-[32rem] min-w-0 gap-0 overflow-hidden py-0 lg:min-h-0"
            >
              <CardHeader className="flex h-12 shrink-0 items-center justify-between gap-3 border-b px-4 [.border-b]:pb-0">
                <div className="flex min-w-0 items-center gap-2 font-medium">
                  <Bug className="size-4 shrink-0" />
                  <span className="truncate">{debugTitle}</span>
                  {debugDescription && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={debugDescription}
                          className="size-6 shrink-0 text-muted-foreground"
                        >
                          <Info className="size-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs whitespace-normal leading-relaxed">
                        {debugDescription}
                      </TooltipContent>
                    </Tooltip>
                  )}
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
              </CardHeader>
              <CardContent className="min-h-0 min-w-0 flex-1 overflow-hidden px-0">
                {debugContent}
              </CardContent>
            </Card>
          )}

          <Card
            role="region"
            aria-label={configTitle}
            className="min-h-[36rem] min-w-0 gap-0 overflow-hidden py-0 lg:min-h-0"
          >
            <CardHeader className="flex h-12 shrink-0 flex-row items-center gap-2 border-b px-4 font-medium [.border-b]:pb-0">
              {configIcon ?? <Settings className="size-4" />}
              <span className="truncate">{configTitle}</span>
              {isDirty && (
                <span className="ml-auto flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                  <span className="size-1.5 rounded-full bg-amber-500" />
                  {unsavedLabel}
                </span>
              )}
            </CardHeader>
            <CardContent className="min-h-0 min-w-0 flex-1 overflow-hidden p-4">
              {configContent}
            </CardContent>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  );
}
