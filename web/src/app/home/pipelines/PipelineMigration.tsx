import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, ChevronDown, Loader2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { getCurrentWorkspaceSnapshot } from '@/app/infra/http/currentWorkspaceStore';
import MigrationInstallProgress from './MigrationInstallProgress';
import { migrationIssueKey } from './pipeline-migration-issues';
import type { CurrentWorkspace } from '@/app/infra/entities/workspace';
import type {
  MigrationInstallation,
  PipelineMigrationIssue,
  PipelineMigrationPreview,
  PipelineMigrationResult,
} from '@/app/infra/entities/api/pipeline-migration';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ScrollArea } from '@/components/ui/scroll-area';

export function migrationWorkspaceKey(workspace: CurrentWorkspace | null) {
  return workspace
    ? `${workspace.workspace.instance_uuid}:${workspace.workspace.uuid}:${workspace.placement_generation}:${workspace.permissions.join(',')}`
    : '';
}

const resultStates = new Set([
  'pending',
  'migrated',
  'already_current',
  'blocked',
  'stale',
  'failed',
  'activation_pending',
]);
type Status =
  | 'idle'
  | 'submitting'
  | 'running'
  | 'finished'
  | 'failed'
  | 'lost'
  | 'requestError';

export default function PipelineMigration({
  workspace,
  onComplete,
}: {
  workspace: CurrentWorkspace;
  onComplete: () => void;
}) {
  const { t } = useTranslation();
  const scopeKey = migrationWorkspaceKey(workspace);
  const canManage = workspace.permissions.includes('resource.manage');
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<PipelineMigrationPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState(false);
  const [valid, setValid] = useState(false);
  const [phase, setPhase] = useState('migrating');
  const [dataOnly, setDataOnly] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [installations, setInstallations] = useState<MigrationInstallation[]>(
    [],
  );
  const [results, setResults] = useState<PipelineMigrationResult[]>([]);
  const active = useRef(false);
  const submitting = useRef(false);
  const previewGeneration = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const isCurrent = useCallback(
    () =>
      active.current &&
      migrationWorkspaceKey(getCurrentWorkspaceSnapshot()) === scopeKey,
    [scopeKey],
  );

  const refresh = useCallback(
    async (allowSelection = true) => {
      if (!isCurrent()) return;
      const generation = ++previewGeneration.current;
      setValid(false);
      setLoading(true);
      setPreviewError(false);
      try {
        const response = await httpClient.getPipelineMigrationPreview({
          signal: controller.current?.signal,
        });
        if (!isCurrent() || generation !== previewGeneration.current) return;
        if (
          response.workspace_uuid !== workspace.workspace.uuid ||
          !Array.isArray(response.items) ||
          response.total !== response.items.length
        )
          throw new Error('Invalid preview');
        setPreview(response);
        setValid(allowSelection);
      } catch {
        if (isCurrent() && generation === previewGeneration.current) {
          setPreviewError(true);
          setPreview(null);
        }
      } finally {
        if (isCurrent() && generation === previewGeneration.current)
          setLoading(false);
      }
    },
    [isCurrent, workspace.workspace.uuid],
  );

  useEffect(() => {
    active.current = true;
    controller.current = new AbortController();
    void refresh();
    const onFocus = () => {
      if (!submitting.current) void refresh();
    };
    window.addEventListener('focus', onFocus);
    return () => {
      active.current = false;
      controller.current?.abort();
      if (timer.current) clearTimeout(timer.current);
      window.removeEventListener('focus', onFocus);
    };
  }, [refresh]);

  const busy = status === 'submitting' || status === 'running';
  const completed =
    status === 'finished' &&
    results.length > 0 &&
    results.every((item) =>
      ['migrated', 'already_current'].includes(item.state),
    );
  const rows = preview?.items ?? [];
  const count = rows.filter(
    (item) => !['already_current', 'not_legacy'].includes(item.state),
  ).length;

  function renderIssue(issue: PipelineMigrationIssue, warning = false) {
    // Unknown server codes use localized fallbacks, never raw upstream messages.
    if (
      [
        'plugin_version_unavailable',
        'plugin_download_timeout',
        'plugin_marketplace_unavailable',
        'plugin_download_failed',
        'dependency_prepare_failed',
        'plugin_launch_failed',
      ].includes(issue.code)
    )
      return <span>{t(`pipelineMigration.installErrors.${issue.code}`)}</span>;
    if (issue.code === 'plugin_install_failed')
      return <span>{t('pipelineMigration.installFailed')}</span>;
    const key = migrationIssueKey(issue.code);
    const fallback = t(
      warning
        ? 'pipelineMigration.warningFallback'
        : 'pipelineMigration.blockerFallback',
    );
    const message = key
      ? t(`pipelineMigration.notices.${key}`, { defaultValue: fallback })
      : fallback;
    return <span>{message}</span>;
  }

  async function execute(installPlugins: boolean) {
    if (
      submitting.current ||
      !isCurrent() ||
      !canManage ||
      !valid ||
      loading ||
      count === 0
    )
      return;
    let items = rows.filter(
      (item) => !['already_current', 'not_legacy'].includes(item.state),
    );
    setInstallations([]);
    setDataOnly(!installPlugins);
    setPhase(installPlugins ? 'installing' : 'migrating');
    submitting.current = true;
    ++previewGeneration.current;
    setStatus('submitting');
    setValid(false);
    setResults(
      items.map((item) => ({
        pipeline_uuid: item.pipeline_uuid,
        state: 'pending',
        code: null,
      })),
    );

    const loseObservation = () => {
      if (!isCurrent()) return;
      submitting.current = false;
      setStatus('lost');
      void refresh(false);
      onCompleteRef.current();
    };
    try {
      const { task_id, pipeline_uuids } =
        await httpClient.executePipelineMigration(
          { confirmed: true, all: true, install_plugins: installPlugins },
          { signal: controller.current?.signal },
        );
      if (!isCurrent()) return;
      if (
        !Array.isArray(pipeline_uuids) ||
        !pipeline_uuids.length ||
        pipeline_uuids.some((id) => typeof id !== 'string' || !id) ||
        new Set(pipeline_uuids).size !== pipeline_uuids.length
      ) {
        loseObservation();
        return;
      }
      // The server captures the complete workspace set at admission.
      items = pipeline_uuids.map(
        (id) =>
          rows.find((row) => row.pipeline_uuid === id) ?? {
            pipeline_uuid: id,
            name: id,
            state: 'ready' as const,
            legacy_runner: null,
            target_runner_id: null,
            target_plugin: null,
            changed_paths: [],
            warnings: [],
            blockers: [],
            preview_token: null,
          },
      );
      setStatus('running');
      const poll = async () => {
        if (!isCurrent()) return;
        try {
          const task = await httpClient.getAsyncTask(task_id, {
            signal: controller.current?.signal,
          });
          if (!isCurrent()) return;
          const metadata = task.task_context?.metadata;
          if (
            task.id !== task_id ||
            metadata?.kind !== 'pipeline_migration' ||
            !Array.isArray(metadata.results)
          ) {
            loseObservation();
            return;
          }
          const outcome = metadata.results as PipelineMigrationResult[];
          if (
            outcome.some(
              (item) =>
                !item ||
                !resultStates.has(item.state) ||
                !items.some(
                  (submitted) => submitted.pipeline_uuid === item.pipeline_uuid,
                ),
            ) ||
            (task.runtime.done && outcome.length !== items.length) ||
            new Set(outcome.map((item) => item.pipeline_uuid)).size !==
              outcome.length
          ) {
            loseObservation();
            return;
          }
          const scopedResults = items.map(
            (item) =>
              outcome.find(
                (result) => result.pipeline_uuid === item.pipeline_uuid,
              ) ?? {
                pipeline_uuid: item.pipeline_uuid,
                state: 'pending' as const,
                code: null,
              },
          );
          setResults(scopedResults);
          if (Array.isArray(metadata.installations))
            setInstallations(metadata.installations as MigrationInstallation[]);
          if (metadata.phase === 'installing' || metadata.phase === 'migrating')
            setPhase(metadata.phase);
          if (task.runtime.done) {
            if (
              !task.runtime.exception &&
              scopedResults.some((item) => item.state === 'pending')
            ) {
              loseObservation();
              return;
            }
            submitting.current = false;
            setStatus(task.runtime.exception ? 'failed' : 'finished');
            void refresh(!task.runtime.exception);
            onCompleteRef.current();
          } else {
            timer.current = setTimeout(() => {
              void poll();
            }, 1000);
          }
        } catch {
          loseObservation();
        }
      };
      void poll();
    } catch (error) {
      if (!isCurrent()) return;
      const code =
        typeof error === 'object' && error && 'code' in error
          ? error.code
          : undefined;
      if (code === -1 || code === -2 || code === undefined) {
        loseObservation();
        return;
      }
      submitting.current = false;
      setStatus('requestError');
    }
  }

  function changeOpen(next: boolean) {
    setOpen(next);
    if (!submitting.current) {
      if (next) void refresh();
    }
  }

  return (
    <>
      {(count > 0 || previewError || results.length > 0) && (
        <Alert className="mb-4 shrink-0 border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
          <AlertTriangle aria-hidden="true" />
          <AlertTitle>{t('pipelineMigration.title')}</AlertTitle>
          <AlertDescription className="flex items-center justify-between gap-3 text-amber-800 dark:text-amber-200">
            <span>
              {previewError
                ? t('pipelineMigration.previewError')
                : t('pipelineMigration.detected', { count })}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => changeOpen(true)}
            >
              {t('pipelineMigration.review')}
            </Button>
          </AlertDescription>
        </Alert>
      )}
      <Dialog open={open} onOpenChange={changeOpen}>
        <DialogContent className="flex max-h-[90dvh] flex-col overflow-hidden sm:max-w-md">
          <DialogHeader className="shrink-0 pr-5">
            <DialogTitle>{t('pipelineMigration.title')}</DialogTitle>
            <DialogDescription>
              {t('pipelineMigration.autoDescription')}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 space-y-3 overflow-y-auto py-2">
            {!canManage && (
              <p className="text-sm text-muted-foreground">
                {t('pipelineMigration.readOnly')}
              </p>
            )}
            {previewError && (
              <p className="text-sm text-destructive">
                {t('pipelineMigration.previewError')}
              </p>
            )}
            {busy ? (
              <div className="flex items-center gap-2 text-sm" role="status">
                <Loader2 className="size-4 shrink-0 animate-spin" />
                {t(`pipelineMigration.${phase}`)}
              </div>
            ) : status !== 'idle' ? (
              <div className="space-y-2" role="status">
                <p className="text-sm">{t(`pipelineMigration.${status}`)}</p>
                {results.length > 0 && (
                  <p className="text-sm text-muted-foreground">
                    {t('pipelineMigration.summary', {
                      migrated: results.filter((r) =>
                        ['migrated', 'already_current'].includes(r.state),
                      ).length,
                      remaining: results.filter(
                        (r) =>
                          !['migrated', 'already_current'].includes(r.state),
                      ).length,
                    })}
                  </p>
                )}
                {dataOnly && results.some((r) => r.state === 'migrated') && (
                  <p className="text-sm text-muted-foreground">
                    {t('pipelineMigration.dataOnlyHint')}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t('pipelineMigration.detected', { count })}
              </p>
            )}
            <MigrationInstallProgress installations={installations} />
            {busy && results.length > 0 && (
              <p className="text-xs text-muted-foreground">
                {t('pipelineMigration.processed', {
                  completed: results.filter((r) => r.state !== 'pending')
                    .length,
                  total: results.length,
                })}
              </p>
            )}
            {(count > 0 || results.length > 0) && (
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="group px-0 text-muted-foreground hover:bg-transparent"
                  >
                    <ChevronDown className="size-4 group-data-[state=open]:rotate-180" />
                    {t('pipelineMigration.viewPipelines')}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <ScrollArea
                    className="h-[min(35dvh,16rem)]"
                    data-testid="migration-scroll-area"
                  >
                    <div className="space-y-3 pr-3">
                      {rows
                        .filter(
                          (item) =>
                            !['already_current', 'not_legacy'].includes(
                              item.state,
                            ) ||
                            results.some(
                              (r) => r.pipeline_uuid === item.pipeline_uuid,
                            ),
                        )
                        .map((item) => {
                          const result = results.find(
                            (r) => r.pipeline_uuid === item.pipeline_uuid,
                          );
                          return (
                            <div
                              key={item.pipeline_uuid}
                              className="space-y-1 border-b pb-3 text-sm"
                              data-testid={`migration-result-${item.pipeline_uuid}`}
                            >
                              <div className="flex items-start justify-between gap-2">
                                <span className="min-w-0 break-words font-medium">
                                  {item.name}
                                </span>
                                <Badge variant="secondary" className="shrink-0">
                                  {t(
                                    `pipelineMigration.states.${result?.state ?? item.state}`,
                                  )}
                                </Badge>
                              </div>
                              {item.target_plugin && (
                                <p className="text-xs text-muted-foreground">
                                  {item.target_plugin.name}
                                </p>
                              )}
                              {item.warnings.some(
                                (issue) =>
                                  issue.code === 'local.box_state_reset',
                              ) && (
                                <p className="text-xs text-muted-foreground">
                                  {t('pipelineMigration.notices.boxReset')}
                                </p>
                              )}
                              {result?.code && result.code !== 'data_only' ? (
                                <p className="text-xs text-destructive">
                                  {renderIssue({ code: result.code })}
                                </p>
                              ) : (
                                !result &&
                                item.blockers
                                  .filter(
                                    (b) =>
                                      ![
                                        'plugin_missing',
                                        'plugin_disabled',
                                      ].includes(b.code),
                                  )
                                  .map((issue, index) => (
                                    <p
                                      key={index}
                                      className="text-xs text-destructive"
                                    >
                                      {renderIssue(issue)}
                                    </p>
                                  ))
                              )}
                            </div>
                          );
                        })}
                    </div>
                  </ScrollArea>
                </CollapsibleContent>
              </Collapsible>
            )}
          </div>
          <DialogFooter className="shrink-0 flex-col gap-2 sm:flex-col">
            {completed ? (
              <Button
                className="w-full"
                onClick={() => window.location.reload()}
              >
                {t('pipelineMigration.complete')}
              </Button>
            ) : (
              !busy && (
                <>
                  <Button
                    disabled={!canManage || loading || !valid || !count}
                    className="w-full"
                    onClick={() => void execute(true)}
                  >
                    {t('pipelineMigration.autoInstall')}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!canManage || loading || !valid || !count}
                    className="w-full"
                    onClick={() => void execute(false)}
                  >
                    {t('pipelineMigration.dataOnly')}
                  </Button>
                  <p className="text-center text-xs text-muted-foreground">
                    {t('pipelineMigration.dataOnlyHint')}
                  </p>
                </>
              )
            )}
            <Button variant="ghost" onClick={() => changeOpen(false)}>
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
