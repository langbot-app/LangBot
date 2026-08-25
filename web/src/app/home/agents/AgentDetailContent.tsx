import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useCurrentWorkspace } from '@/app/infra/http';
import { Agent } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import PipelineDetailContent from '@/app/home/pipelines/PipelineDetailContent';
import AgentCreateContent from './components/AgentCreateContent';
import AgentDebugPanel from './components/AgentDebugPanel';
import AgentFormComponent, {
  AgentRunnerStatus,
} from './components/AgentFormComponent';

export default function AgentDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canManage =
    currentWorkspace?.permissions.includes('resource.manage') ?? false;
  const canOperate =
    currentWorkspace?.permissions.includes('runtime.operate') ?? false;
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(!isCreateMode);
  const [formDirty, setFormDirty] = useState(false);
  const [formSaving, setFormSaving] = useState(false);
  const [runnerStatus, setRunnerStatus] = useState<AgentRunnerStatus | null>(
    null,
  );

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
    setRunnerStatus(null);
  }, [id]);

  useEffect(() => {
    if (isCreateMode) return;
    let cancelled = false;
    setLoading(true);
    httpClient
      .getAgent(id)
      .then((resp) => {
        if (!cancelled) setAgent(resp.agent);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, isCreateMode]);

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

  if (loading || !agent) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        {t('common.loading')}
      </div>
    );
  }

  if (agent.kind === 'pipeline') {
    return <PipelineDetailContent id={id} routeBase="/home/agents" />;
  }

  return (
    <ProcessorDetailWorkbench
      key={id}
      title={t('agents.editAgent')}
      status={runnerStatus}
      saveLabel={t('common.save')}
      saveFormId="agent-form"
      canSave={canManage}
      isDirty={formDirty}
      isSaving={formSaving}
      configTitle={t('pipelines.configuration')}
      configContent={
        <fieldset className="contents" disabled={!canManage}>
          <AgentFormComponent
            agentId={id}
            onFinish={() => {
              refreshPipelines();
            }}
            onDeleted={() => {
              refreshPipelines();
              navigate('/home/agents');
            }}
            onDirtyChange={setFormDirty}
            onSavingChange={setFormSaving}
            onRunnerStatusChange={setRunnerStatus}
          />
        </fieldset>
      }
      debugTitle={canOperate ? t('agents.debugTab') : undefined}
      debugContent={
        canOperate ? (
          <AgentDebugPanel
            agentId={id}
            supportedEventPatterns={
              agent.supported_event_patterns ??
              agent.capability?.supported_event_patterns ?? ['*']
            }
          />
        ) : undefined
      }
      unsavedLabel={t('pipelines.unsavedChanges')}
    />
  );
}
