import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Agent } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import PipelineDetailContent from '@/app/home/pipelines/PipelineDetailContent';
import AgentCreateContent from './components/AgentCreateContent';
import AgentFormComponent from './components/AgentFormComponent';

export default function AgentDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(!isCreateMode);
  const [formDirty, setFormDirty] = useState(false);

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
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('agents.editAgent')}</h1>
        <Button type="submit" form="agent-form" disabled={!formDirty}>
          {t('common.save')}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        <AgentFormComponent
          agentId={id}
          onFinish={() => {
            refreshPipelines();
            setFormDirty(false);
          }}
          onDeleted={() => {
            refreshPipelines();
            navigate('/home/agents');
          }}
          onDirtyChange={setFormDirty}
        />
      </div>
    </div>
  );
}
