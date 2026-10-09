import EntityLoadState from '@/components/EntityLoadState';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useCurrentWorkspace, userInfo } from '@/app/infra/http';
import { Agent, AgentPlatformTool } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityBasicInfoDialog, {
  EntityBasicInfoValues,
} from '@/app/home/components/entity-basic-info/EntityBasicInfoDialog';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import PipelineDetailContent from '@/app/home/pipelines/PipelineDetailContent';
import PluginProcessorDetailContent from './PluginProcessorDetailContent';
import AgentCreateContent from './components/AgentCreateContent';
import AgentDebugPanel from './components/AgentDebugPanel';
import AgentMonitoringTab from './components/AgentMonitoringTab';
import AgentFormComponent, {
  AgentFormHandle,
  RunnerStatus,
} from './components/AgentFormComponent';

// Keep the last checked display state across navigation within this app session.
const runnerStatusCache = new Map<string, RunnerStatus>();

export default function AgentDetailContent({
  id,
  pipelineRevision,
}: {
  id: string;
  pipelineRevision?: string;
}) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canManage =
    currentWorkspace?.permissions.includes('resource.manage') ?? false;
  const canOperate =
    currentWorkspace?.permissions.includes('runtime.operate') ?? false;
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [platformTools, setPlatformTools] = useState<AgentPlatformTool[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [loading, setLoading] = useState(!isCreateMode);
  const [formDirty, setFormDirty] = useState(false);
  const [formSaving, setFormSaving] = useState(false);
  const [basicInfoOpen, setBasicInfoOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const runnerStatusKey = JSON.stringify([
    userInfo?.account_uuid, currentWorkspace?.workspace.uuid, id, i18n.language,
  ]);
  const [runnerStatusState, setRunnerStatusState] = useState<{
    key: string; status: RunnerStatus;
  } | null>(null);
  const runnerStatus = runnerStatusState?.key === runnerStatusKey
    ? runnerStatusState.status : runnerStatusCache.get(runnerStatusKey) ?? null;
  const updateRunnerStatus = useCallback((status: RunnerStatus) => {
    setRunnerStatusState((previous) => {
      if (status.tone === 'neutral') {
        const cached = previous?.key === runnerStatusKey
          ? previous.status : runnerStatusCache.get(runnerStatusKey);
        if (cached) return { key: runnerStatusKey, status: cached };
      }
      return { key: runnerStatusKey, status };
    });
    if (status.tone !== 'neutral' && !formDirty) {
      runnerStatusCache.delete(runnerStatusKey);
      runnerStatusCache.set(runnerStatusKey, status);
      if (runnerStatusCache.size > 100) {
        const oldest = runnerStatusCache.keys().next().value;
        if (oldest !== undefined) runnerStatusCache.delete(oldest);
      }
    }
  }, [runnerStatusKey, formDirty]);
  const [availableEventTypes, setAvailableEventTypes] = useState<string[]>([
    'message.received',
  ]);
  const [supportedEventPatterns, setSupportedEventPatterns] = useState<
    string[]
  >(['*']);
  const agentFormRef = useRef<AgentFormHandle>(null);

  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('agents.create'));
      return () => setDetailEntityName(null);
    }

    const sidebarItem = pipelines.find((p) => p.id === id);
    setDetailEntityName(sidebarItem?.name ?? id);
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, pipelines, setDetailEntityName, t]);

  useEffect(() => {
    if (isCreateMode) return;
    let cancelled = false;
    setLoading(true);
    setLoadFailed(false);
    Promise.all([
      httpClient.getAgent(id),
      httpClient.getAdapters().catch(() => ({ adapters: [] })),
    ])
      .then(([resp, adaptersResp]) => {
        if (cancelled) return;
        const adapterEvents = adaptersResp.adapters.flatMap(
          (adapter) => adapter.spec.supported_events ?? [],
        );
        setAvailableEventTypes(
          adapterEvents.length > 0
            ? Array.from(new Set(adapterEvents)).sort()
            : ['message.received'],
        );
        setSupportedEventPatterns(
          resp.agent.supported_event_patterns ??
            resp.agent.capability?.supported_event_patterns ?? ['*'],
        );
        setAgent(resp.agent);
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, isCreateMode, loadAttempt]);

  if (isCreateMode) {
    return (
      <AgentCreateContent
        onCreated={(newAgentId) => {
          refreshPipelines();
          navigate(`/home/agents?id=${encodeURIComponent(newAgentId)}`);
        }}
      />
    );
  }

  if (loadFailed)
    return (
      <EntityLoadState error onRetry={() => setLoadAttempt((n) => n + 1)} />
    );
  if (loading || !agent) return <EntityLoadState />;

  if (agent.kind === 'pipeline') {
    return (
      <PipelineDetailContent
        key={pipelineRevision}
        id={id}
        routeBase="/home/agents"
      />
    );
  }

  async function saveBasicInfo(values: EntityBasicInfoValues) {
    try {
      await httpClient.updateAgent(id, values);
      setAgent((current) => (current ? { ...current, ...values } : current));
      agentFormRef.current?.syncBasicInfo(values);
      await refreshPipelines();
      toast.success(t('agents.saveSuccess'));
    } catch (error) {
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : '';
      toast.error(t('agents.saveError') + message);
      throw error;
    }
  }

  async function deleteAgent() {
    setDeleting(true);
    try {
      await httpClient.deleteAgent(id);
      toast.success(t('agents.deleteSuccess'));
      setDeleteConfirmOpen(false);
      await refreshPipelines();
      navigate('/home/agents');
    } catch (error) {
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : '';
      toast.error(t('agents.deleteError') + message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      {agent.kind === 'event_processor' ? (
        <PluginProcessorDetailContent
          key={id}
          id={id}
          agent={agent}
          canManage={canManage}
          canOperate={canOperate}
          availableEventTypes={availableEventTypes}
          onDelete={() => setDeleteConfirmOpen(true)}
          onEdit={() => setBasicInfoOpen(true)}
          onSaved={() => {
            void httpClient
              .getAgent(id)
              .then((response) => setAgent(response.agent));
            void refreshPipelines();
          }}
        />
      ) : (
        <ProcessorDetailWorkbench
          key={id}
          title={`${agent.emoji || '🤖'} ${agent.name}`}
          titleBadge={
            supportedEventPatterns.length === 0 ? (
              <Badge
                variant="outline"
                role="status"
                className="shrink-0 gap-1 rounded-full border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
              >
                <AlertTriangle className="size-3" />
                {t('agents.noEventsConfiguredBadge')}
              </Badge>
            ) : undefined
          }
          titleAction={
            canManage ? (
              <EntityTitleEditButton onClick={() => setBasicInfoOpen(true)} />
            ) : undefined
          }
          status={runnerStatus}
          saveLabel={t('common.save')}
          saveFormId="agent-form"
          canSave={canManage}
          isDirty={formDirty}
          isSaving={formSaving}
          headerActions={
            canManage ? (
              <Button
                type="button"
                variant="destructive"
                disabled={formSaving || deleting}
                onClick={() => setDeleteConfirmOpen(true)}
              >
                <Trash2 className="size-4" />
                {t('common.delete')}
              </Button>
            ) : undefined
          }
          configTitle={t('pipelines.configuration')}
          configContent={
            <fieldset className="contents" disabled={!canManage}>
              <AgentFormComponent
                ref={agentFormRef}
                agentId={id}
                availableEventTypes={availableEventTypes}
                onFinish={(updatedAgent) => {
                  if (updatedAgent) {
                    setAgent((current) =>
                      current ? { ...current, ...updatedAgent } : current,
                    );
                  }
                  refreshPipelines();
                }}
                onDirtyChange={setFormDirty}
                onSavingChange={setFormSaving}
                onRunnerStatusChange={updateRunnerStatus}
                onSupportedEventPatternsChange={setSupportedEventPatterns}
                onPlatformToolsChange={setPlatformTools}
                guideEnabled={canManage}
                debugGuideEnabled={canOperate}
              />
            </fieldset>
          }
          debugTitle={canOperate ? t('agents.debugTab') : undefined}
          debugDescription={t('agents.debugPlatformNotice')}
          debugContent={
            canOperate ? (
              <AgentDebugPanel
                agentId={id}
                platformTools={platformTools}
                hasUnsavedChanges={formDirty}
                beforeRun={async () => agentFormRef.current?.save() ?? false}
                onOpenRunnerConfig={() =>
                  agentFormRef.current?.openSection('runner')
                }
                supportedEventPatterns={supportedEventPatterns}
                availableEventTypes={availableEventTypes}
              />
            ) : undefined
          }
          unsavedLabel={t('pipelines.unsavedChanges')}
          monitoring={
            currentWorkspace?.permissions.includes('resource.view')
              ? {
                  label: t('pipelines.monitoring.title'),
                  workbenchLabel: t('pipelines.monitoring.workbench'),
                  content: (
                    <AgentMonitoringTab
                      key={id}
                      agentId={id}
                      platformTools={platformTools}
                    />
                  ),
                }
              : undefined
          }
        />
      )}
      <EntityBasicInfoDialog
        open={basicInfoOpen}
        onOpenChange={setBasicInfoOpen}
        values={{
          name: agent.name,
          description: agent.description || '',
          emoji: agent.emoji || '🤖',
        }}
        defaultEmoji="🤖"
        onSave={saveBasicInfo}
      />
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription>
              {t('agents.deleteConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={deleting}
              onClick={() => setDeleteConfirmOpen(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={deleting}
              onClick={deleteAgent}
            >
              <Trash2 className="size-4" />
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
