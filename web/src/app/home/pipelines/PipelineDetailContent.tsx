import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import PipelineFormComponent, {
  PipelineFormHandle,
} from '@/app/home/pipelines/components/pipeline-form/PipelineFormComponent';
import DebugDialog from '@/app/home/pipelines/components/debug-dialog/DebugDialog';
import PipelineMonitoringTab from '@/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab';
import ProcessorDetailWorkbench from '@/app/home/components/processor-detail/ProcessorDetailWorkbench';
import EntityBasicInfoDialog, {
  EntityBasicInfoValues,
} from '@/app/home/components/entity-basic-info/EntityBasicInfoDialog';
import EntityTitleEditButton from '@/app/home/components/entity-basic-info/EntityTitleEditButton';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { useCurrentWorkspace } from '@/app/infra/http';
import { httpClient } from '@/app/infra/http/HttpClient';
import { Pipeline } from '@/app/infra/entities/api';

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
  const [basicInfoOpen, setBasicInfoOpen] = useState(false);
  const [pipelineDetails, setPipelineDetails] = useState<Pipeline | null>(null);
  const pipelineFormRef = useRef<PipelineFormHandle>(null);
  const sidebarPipeline = pipelines.find((item) => item.id === id);

  useEffect(() => {
    if (isCreateMode) return;
    let cancelled = false;
    httpClient.getPipeline(id).then((response) => {
      if (!cancelled) setPipelineDetails(response.pipeline);
    });
    return () => {
      cancelled = true;
    };
  }, [id, isCreateMode]);

  function handleFinish() {
    refreshPipelines();
  }

  async function saveBasicInfo(values: EntityBasicInfoValues) {
    try {
      await httpClient.updatePipeline(id, values);
      setPipelineDetails((current) =>
        current
          ? { ...current, ...values }
          : ({ ...values, config: {} } as Pipeline),
      );
      pipelineFormRef.current?.syncBasicInfo(values);
      await refreshPipelines();
      toast.success(t('pipelines.saveSuccess'));
    } catch (error) {
      const message =
        typeof error === 'object' && error && 'msg' in error
          ? String((error as { msg?: string }).msg || '')
          : '';
      toast.error(t('pipelines.saveError') + message);
      throw error;
    }
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
  const pipelineName =
    pipelineDetails?.name ||
    sidebarPipeline?.name ||
    t('pipelines.editPipeline');
  const pipelineEmoji =
    pipelineDetails?.emoji || sidebarPipeline?.emoji || '⚙️';

  return (
    <>
      <ProcessorDetailWorkbench
        key={id}
        title={`${pipelineEmoji} ${pipelineName}`}
        titleAction={
          canManage ? (
            <EntityTitleEditButton onClick={() => setBasicInfoOpen(true)} />
          ) : undefined
        }
        saveLabel={t('common.save')}
        saveFormId="pipeline-form"
        canSave={canManage}
        isDirty={formDirty}
        isSaving={formSaving}
        configTitle={t('pipelines.configuration')}
        configContent={
          <fieldset className="contents" disabled={!canManage}>
            <PipelineFormComponent
              ref={pipelineFormRef}
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
              hasUnsavedChanges={formDirty}
              beforeSend={async () => pipelineFormRef.current?.save() ?? false}
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
      <EntityBasicInfoDialog
        open={basicInfoOpen}
        onOpenChange={setBasicInfoOpen}
        values={{
          name: pipelineName,
          description: pipelineDetails?.description || '',
          emoji: pipelineEmoji,
        }}
        defaultEmoji="⚙️"
        onSave={saveBasicInfo}
      />
    </>
  );
}
