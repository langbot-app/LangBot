import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import PipelineFormComponent from '@/app/home/pipelines/components/pipeline-form/PipelineFormComponent';
import DebugDialog from '@/app/home/pipelines/components/debug-dialog/DebugDialog';
import PipelineMonitoringTab from '@/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { useCurrentWorkspace } from '@/app/infra/http';

export default function PipelineDetailContent({
  id,
  routeBase = '/home/pipelines',
}: {
  id: string;
  routeBase?: string;
}) {
  const isCreateMode = id === 'new';
  const navigate = useNavigate();
  const { t } = useTranslation();
  const currentWorkspace = useCurrentWorkspace();
  const canManage =
    currentWorkspace?.permissions.includes('resource.manage') ?? false;
  const canOperate =
    currentWorkspace?.permissions.includes('runtime.operate') ?? false;
  const canViewMonitoring =
    currentWorkspace?.permissions.includes('resource.view') ?? false;
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

  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
  const [formDirty, setFormDirty] = useState(false);
  const [formSaving, setFormSaving] = useState(false);

  function handleFinish() {
    refreshPipelines();
  }

  function handleNewPipelineCreated(newPipelineId: string) {
    refreshPipelines();
    navigate(`${routeBase}?id=${encodeURIComponent(newPipelineId)}`);
  }

  // ==================== Create Mode ====================
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between pb-4 shrink-0">
          <h1 className="text-xl font-semibold">
            {t('pipelines.createPipeline')}
          </h1>
          {canManage && (
            <Button type="submit" form="pipeline-form" disabled={formSaving}>
              {t('common.submit')}
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-2xl space-y-6">
            <fieldset className="contents" disabled={!canManage}>
              <PipelineFormComponent
                pipelineId={undefined}
                isEditMode={false}
                disableForm={!canManage}
                showButtons={false}
                onFinish={handleFinish}
                onNewPipelineCreated={handleNewPipelineCreated}
                onDeletePipeline={() => {}}
                onSavingChange={setFormSaving}
              />
            </fieldset>
          </div>
        </div>
      </div>
    );
  }

  function handleDeletePipeline() {
    refreshPipelines();
    navigate(routeBase);
  }

  // ==================== Edit Mode ====================
  return (
    <ProcessorDetailWorkbench
      key={id}
      title={t('pipelines.editPipeline')}
      saveLabel={t('common.save')}
      saveFormId="pipeline-form"
      canSave={canManage}
      isDirty={formDirty}
      isSaving={formSaving}
      configTitle={t('pipelines.configuration')}
      configContent={
        <fieldset className="contents" disabled={!canManage}>
          <PipelineFormComponent
            pipelineId={id}
            isEditMode={true}
            disableForm={!canManage}
            showButtons={false}
            onFinish={handleFinish}
            onNewPipelineCreated={handleNewPipelineCreated}
            onDeletePipeline={handleDeletePipeline}
            onCancel={() => navigate(routeBase)}
            onDirtyChange={setFormDirty}
            onSavingChange={setFormSaving}
          />
        </fieldset>
      }
      debugTitle={canOperate ? t('pipelines.debugChat') : undefined}
      debugConnected={canOperate ? isWebSocketConnected : undefined}
      debugConnectedLabel={t('pipelines.debugDialog.connected')}
      debugDisconnectedLabel={t('pipelines.debugDialog.disconnected')}
      debugContent={
        canOperate ? (
          <DebugDialog
            open={true}
            pipelineId={id}
            isEmbedded={true}
            compact={true}
            onConnectionStatusChange={setIsWebSocketConnected}
          />
        ) : undefined
      }
      unsavedLabel={t('pipelines.unsavedChanges')}
      monitoring={
        canViewMonitoring
          ? {
              label: t('pipelines.monitoring.title'),
              content: (
                <PipelineMonitoringTab
                  pipelineId={id}
                  onNavigateToMonitoring={() => {
                    navigate('/home/monitoring');
                  }}
                />
              ),
            }
          : undefined
      }
    />
  );
}
