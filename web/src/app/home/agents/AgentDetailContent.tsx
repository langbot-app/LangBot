import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Bug, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useCurrentWorkspace } from '@/app/infra/http';
import { Agent } from '@/app/infra/entities/api';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import PipelineDetailContent from '@/app/home/pipelines/PipelineDetailContent';
import AgentCreateContent from './components/AgentCreateContent';
import AgentDebugPanel from './components/AgentDebugPanel';
import AgentFormComponent from './components/AgentFormComponent';

export default function AgentDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canOperate =
    currentWorkspace?.permissions.includes('runtime.operate') ?? false;
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(!isCreateMode);
  const [formDirty, setFormDirty] = useState(false);
  const [formSaving, setFormSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('config');

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
    <div className="flex h-full min-w-0 flex-col">
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('agents.editAgent')}</h1>
        <Button
          type="submit"
          form="agent-form"
          disabled={!formDirty || formSaving}
          className={activeTab !== 'config' ? 'invisible' : ''}
        >
          {t('common.save')}
        </Button>
      </div>

      <Tabs
        key={id}
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex min-h-0 min-w-0 flex-1 flex-col"
      >
        <TabsList className="shrink-0">
          <TabsTrigger value="config" className="gap-1.5">
            <Settings className="size-3.5" />
            {t('pipelines.configuration')}
          </TabsTrigger>
          {canOperate && (
            <TabsTrigger value="debug" className="gap-1.5">
              <Bug className="size-3.5" />
              {t('agents.debugTab')}
            </TabsTrigger>
          )}
        </TabsList>

        <TabsContent
          value="config"
          className="mt-4 min-h-0 min-w-0 flex-1 overflow-hidden"
        >
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
          />
        </TabsContent>

        {canOperate && (
          <TabsContent
            value="debug"
            className="mt-4 min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden"
          >
            <AgentDebugPanel
              agentId={id}
              supportedEventPatterns={
                agent.supported_event_patterns ??
                agent.capability?.supported_event_patterns ?? ['*']
              }
            />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
