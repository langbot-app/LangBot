import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import PipelineFormComponent from '@/app/home/pipelines/components/pipeline-form/PipelineFormComponent';
import DebugDialog from '@/app/home/pipelines/components/debug-dialog/DebugDialog';
import PipelineMonitoringTab from '@/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { Settings, Bug, BarChart3 } from 'lucide-react';

export default function PipelineDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { refreshPipelines, pipelines, setDetailEntityName } = useSidebarData();

  // Set breadcrumb entity name
  useEffect(() => {
    if (isCreateMode) {
      setDetailEntityName(t('pipelines.createPipeline'));
    } else {
      const pipeline = pipelines.find((p) => p.id === id);
      setDetailEntityName(pipeline?.name ?? id);
    }
    return () => setDetailEntityName(null);
  }, [id, isCreateMode, pipelines, setDetailEntityName, t]);

  const [activeTab, setActiveTab] = useState('config');
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  const [formDirty, setFormDirty] = useState(false);

  function handleFinish() {
    refreshPipelines();
  }

  function handleNewPipelineCreated(newPipelineId: string) {
    refreshPipelines();
    navigate(`/home/pipelines?id=${encodeURIComponent(newPipelineId)}`);
  }

  // ==================== Create Mode ====================
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('pipelines.createPipeline')}
          </h1>
          <Button type="submit" form="pipeline-form">
            {t('common.submit')}
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-2xl space-y-6">
            <PipelineFormComponent
              pipelineId={undefined}
              isEditMode={false}
              disableForm={false}
              showButtons={false}
              onFinish={handleFinish}
              onNewPipelineCreated={handleNewPipelineCreated}
              onDeletePipeline={() => {}}
            />
          </div>
        </div>
      </div>
    );
  }

  function handleDeletePipeline() {
    refreshPipelines();
    navigate('/home/pipelines');
  }

  // ==================== Edit Mode ====================
  return (
    <div className="flex h-full flex-col">
      {/* Sticky Header: title + save button */}
      <div className="flex items-center justify-between pb-4 shrink-0">
        <h1 className="text-xl font-semibold">{t('pipelines.editPipeline')}</h1>
        <Button type="submit" form="pipeline-form" disabled={!formDirty}>
          {t('common.save')}
        </Button>
      </div>

      {/* Horizontal Tabs */}
      <Tabs
        key={id}
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex flex-1 flex-col min-h-0"
      >
        <TabsList className="shrink-0">
          <TabsTrigger value="config" className="gap-1.5">
            <Settings className="size-3.5" />
            {t('pipelines.configuration')}
          </TabsTrigger>
          <TabsTrigger value="debug" className="gap-1.5">
            <Bug className="size-3.5" />
            {t('pipelines.debugChat')}
            {activeTab === 'debug' && (
              <span
                className={`inline-block size-2 rounded-full ${
                  isWebSocketConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
            )}
          </TabsTrigger>
          <TabsTrigger value="monitoring" className="gap-1.5">
            <BarChart3 className="size-3.5" />
            {t('pipelines.monitoring.title')}
          </TabsTrigger>
        </TabsList>

        {/* Tab: Configuration */}
        <TabsContent
          value="config"
          className="flex-1 min-h-0 overflow-y-auto mt-4"
        >
          <PipelineFormComponent
            pipelineId={id}
            isEditMode={true}
            disableForm={false}
            showButtons={false}
            onFinish={handleFinish}
            onNewPipelineCreated={handleNewPipelineCreated}
            onDeletePipeline={handleDeletePipeline}
            onCancel={() => navigate('/home/pipelines')}
            onDirtyChange={setFormDirty}
          />
        </TabsContent>

        {/* Tab: Debug */}
        <TabsContent value="debug" className="flex-1 min-h-0 mt-4">
          <DebugDialog
            open={activeTab === 'debug'}
            pipelineId={id}
            isEmbedded={true}
            onConnectionStatusChange={setIsWebSocketConnected}
          />
        </TabsContent>

        {/* Tab: Monitoring */}
        <TabsContent
          value="monitoring"
          className="flex-1 min-h-0 overflow-y-auto mt-4"
        >
          <PipelineMonitoringTab
            pipelineId={id}
            onNavigateToMonitoring={() => {
              navigate('/home/monitoring');
            }}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
