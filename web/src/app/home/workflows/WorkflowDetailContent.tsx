import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Copy,
  Download,
  Ellipsis,
  Trash2,
  Upload,
  Workflow as WorkflowIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityBasicInfoDialog, {
  type EntityBasicInfoValues,
} from '@/app/home/components/entity-basic-info/EntityBasicInfoDialog';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { backendClient, useCurrentWorkspace } from '@/app/infra/http';
import type {
  ApiRespWorkflowTest,
  Workflow,
  WorkflowGraph,
  WorkflowIssue,
  WorkflowStepRun,
} from '@/app/infra/entities/api';
import { EditorContext, type EditorResources } from './editor/EditorContext';
import StepCanvas from './editor/StepCanvas';
import StepPanel from './editor/StepPanel';
import TestRunPanel from './editor/TestRunPanel';
import RunHistory from './history/RunHistory';
import { parseIssue } from './lib/issues';

const EMPTY_RESOURCES: EditorResources = {
  models: [],
  processors: [],
  workflows: [],
  bots: [],
  availableTypes: null,
};

function errorText(error: unknown) {
  return (
    (error as { msg?: string })?.msg ??
    (error as Error)?.message ??
    String(error)
  );
}

export default function WorkflowDetailContent({ id }: { id: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const workspace = useCurrentWorkspace();
  const canManage = workspace?.permissions.includes('resource.manage') ?? false;
  const canRun = workspace?.permissions.includes('runtime.operate') ?? false;
  const { refreshPipelines, setDetailEntityName } = useSidebarData();

  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [graph, setGraphState] = useState<WorkflowGraph | null>(null);
  const [saved, setSaved] = useState('');
  const [issues, setIssues] = useState<WorkflowIssue[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<Record<string, WorkflowStepRun>>({});
  const [resources, setResources] = useState(EMPTY_RESOURCES);
  const [saving, setSaving] = useState(false);
  const [basicInfoOpen, setBasicInfoOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const importInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const response = await backendClient.getWorkflow(id);
      setWorkflow(response.workflow);
      setGraphState(response.workflow.graph);
      setSaved(JSON.stringify(response.workflow.graph));
      setIssues(response.issues ?? []);
    } catch (error) {
      toast.error(`${t('workflows.loadError')} ${errorText(error)}`);
    }
  }, [id, t]);

  useEffect(() => {
    setWorkflow(null);
    setGraphState(null);
    setSelected(null);
    setLastRun({});
    void load();
  }, [load]);

  useEffect(() => {
    let alive = true;
    void Promise.allSettled([
      backendClient.getProviderLLMModels(),
      backendClient.getAgents(),
      backendClient.getWorkflows(),
      backendClient.getBots(),
      backendClient.getWorkflowNodeTypes(),
    ]).then(([models, agents, workflows, bots, types]) => {
      if (!alive) return;
      setResources({
        models: models.status === 'fulfilled' ? models.value.models : [],
        processors: agents.status === 'fulfilled' ? agents.value.agents : [],
        workflows:
          workflows.status === 'fulfilled' ? workflows.value.workflows : [],
        bots:
          bots.status === 'fulfilled'
            ? bots.value.bots
                .filter((bot) => bot.uuid)
                .map((bot) => ({ uuid: bot.uuid!, name: bot.name }))
            : [],
        availableTypes:
          types.status === 'fulfilled'
            ? new Set(
                types.value.node_types
                  .filter((item) => item.available !== false)
                  .map((item) => item.type),
              )
            : null,
      });
    });
    return () => {
      alive = false;
    };
  }, [id]);

  useEffect(() => {
    if (workflow) setDetailEntityName(workflow.name);
    return () => setDetailEntityName(null);
  }, [workflow, setDetailEntityName]);

  const dirty = graph !== null && JSON.stringify(graph) !== saved;

  const setGraph = useCallback(
    (update: (current: WorkflowGraph) => WorkflowGraph) =>
      setGraphState((current) => (current ? update(current) : current)),
    [],
  );

  const save = async () => {
    if (!graph || saving) return;
    setSaving(true);
    try {
      const response = await backendClient.updateWorkflow(id, { graph });
      setWorkflow(response.workflow);
      setSaved(JSON.stringify(response.workflow.graph));
      setGraphState(response.workflow.graph);
      setIssues(response.issues ?? []);
      const errors = (response.issues ?? []).filter(
        (issue) => issue.severity === 'error',
      ).length;
      if (errors) {
        toast.warning(t('workflows.savedWithIssues', { count: errors }));
      } else {
        toast.success(t('workflows.saveSuccess'));
      }
      refreshPipelines();
    } catch (error) {
      toast.error(`${t('workflows.saveError')}${errorText(error)}`);
    } finally {
      setSaving(false);
    }
  };

  const saveBasicInfo = async (values: EntityBasicInfoValues) => {
    const response = await backendClient.updateWorkflow(id, {
      name: values.name,
      description: values.description,
      emoji: values.emoji,
    });
    setWorkflow(response.workflow);
    refreshPipelines();
  };

  const exportWorkflow = () => {
    if (!workflow || !graph) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            name: workflow.name,
            description: workflow.description ?? '',
            emoji: workflow.emoji ?? '',
            graph,
          },
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${workflow.name || 'workflow'}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const importWorkflow = async (file: File) => {
    try {
      const data = JSON.parse(await file.text());
      const next: WorkflowGraph = data.graph ?? data;
      if (!Array.isArray(next?.nodes) || !Array.isArray(next?.edges)) {
        throw new Error('invalid');
      }
      setGraphState(next);
      setSelected(null);
      toast.success(t('workflows.importSuccess'));
    } catch {
      toast.error(t('workflows.importError'));
    }
  };

  const copyWorkflow = async () => {
    try {
      const response = await backendClient.copyWorkflow(id);
      refreshPipelines();
      navigate(
        `/home/workflows?id=${encodeURIComponent(response.workflow.uuid)}`,
      );
      toast.success(t('workflows.copySuccess'));
    } catch (error) {
      toast.error(errorText(error));
    }
  };

  const deleteWorkflow = async () => {
    try {
      await backendClient.deleteWorkflow(id);
      refreshPipelines();
      navigate('/home/agents');
      toast.success(t('workflows.deleteSuccess'));
    } catch (error) {
      toast.error(`${t('workflows.deleteError')}${errorText(error)}`);
    }
  };

  const applyRun = (result: ApiRespWorkflowTest | null) => {
    const blocked = parseIssue(result?.error);
    if (blocked && !result?.steps?.length) {
      // The draft was rejected before running: mark the step on the canvas.
      setIssues((current) => [
        ...current.filter(
          (issue) =>
            !(issue.node_id === blocked.node_id && issue.code === blocked.code),
        ),
        blocked,
      ]);
    }
    setLastRun(
      Object.fromEntries(
        (result?.steps ?? []).map((step) => [step.node_id, step]),
      ),
    );
  };

  const errorCount = issues.filter(
    (issue) => issue.severity === 'error',
  ).length;
  const editor = useMemo(
    () =>
      graph && {
        workflowId: id,
        graph,
        setGraph,
        selected,
        select: setSelected,
        issues,
        lastRun,
        resources,
        readOnly: !canManage,
      },
    [id, graph, setGraph, selected, issues, lastRun, resources, canManage],
  );

  if (!workflow || !editor) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        {t('common.loading')}
      </div>
    );
  }

  return (
    <EditorContext.Provider value={editor}>
      <ProcessorDetailWorkbench
        key={id}
        title={`${workflow.emoji || '🧭'} ${workflow.name}`}
        titleBadge={
          <span className="rounded-full border px-2 py-0.5 text-xs text-muted-foreground">
            {t('workflows.badge')}
          </span>
        }
        titleAction={
          canManage ? (
            <EntityTitleEditButton onClick={() => setBasicInfoOpen(true)} />
          ) : undefined
        }
        status={
          errorCount
            ? {
                label: t('workflows.issueCount', { count: errorCount }),
                description: t('workflows.issueCountHint'),
                tone: 'error',
              }
            : null
        }
        saveLabel={t('common.save')}
        saveFormId="workflow-form"
        canSave={canManage}
        isDirty={dirty}
        isSaving={saving}
        unsavedLabel={t('pipelines.unsavedChanges')}
        headerActions={
          canManage ? (
            <>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t('workflows.more')}
                  >
                    <Ellipsis className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={() => importInput.current?.click()}
                  >
                    <Upload className="size-4" />
                    {t('workflows.import')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={exportWorkflow}>
                    <Download className="size-4" />
                    {t('workflows.export')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => void copyWorkflow()}>
                    <Copy className="size-4" />
                    {t('workflows.copy')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                type="button"
                variant="destructive"
                onClick={() => setDeleteOpen(true)}
              >
                <Trash2 className="size-4" />
                {t('common.delete')}
              </Button>
              <input
                ref={importInput}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void importWorkflow(file);
                  event.target.value = '';
                }}
              />
            </>
          ) : undefined
        }
        configTitle={t('workflows.editor')}
        configIcon={<WorkflowIcon className="size-4" />}
        configContent={
          <form
            id="workflow-form"
            className="relative -m-4 h-[calc(100%+2rem)] overflow-hidden"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
            onKeyDown={(event) => {
              if (
                event.key === 'Enter' &&
                (event.target as HTMLElement).tagName === 'INPUT'
              ) {
                event.preventDefault();
              }
            }}
          >
            <StepCanvas />
            {selected && (
              <div className="absolute inset-y-0 right-0 z-20">
                <StepPanel id={selected} />
              </div>
            )}
          </form>
        }
        debugTitle={canRun ? t('workflows.test.title') : undefined}
        debugDescription={t('workflows.test.description')}
        debugContent={
          canRun ? (
            <TestRunPanel workflowId={id} graph={graph!} onResult={applyRun} />
          ) : undefined
        }
        monitoring={
          workspace?.permissions.includes('resource.view')
            ? {
                label: t('workflows.history'),
                workbenchLabel: t('workflows.workbench'),
                content: <RunHistory key={id} workflowId={id} />,
              }
            : undefined
        }
      />
      <EntityBasicInfoDialog
        open={basicInfoOpen}
        onOpenChange={setBasicInfoOpen}
        values={{
          name: workflow.name,
          description: workflow.description ?? '',
          emoji: workflow.emoji || '🧭',
        }}
        defaultEmoji="🧭"
        onSave={saveBasicInfo}
      />
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('common.confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('workflows.deleteConfirm', { name: workflow.name })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void deleteWorkflow()}>
              {t('common.delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </EditorContext.Provider>
  );
}
