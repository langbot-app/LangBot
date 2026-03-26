'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import PipelineFormComponent from '@/app/home/pipelines/components/pipeline-form/PipelineFormComponent';
import DebugDialog from '@/app/home/pipelines/components/debug-dialog/DebugDialog';
import PipelineExtension from '@/app/home/pipelines/components/pipeline-extensions/PipelineExtension';
import PipelineMonitoringTab from '@/app/home/pipelines/components/monitoring-tab/PipelineMonitoringTab';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Settings, Puzzle, Bug, BarChart3 } from 'lucide-react';

export default function PipelineDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const router = useRouter();
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
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);

  function handleFinish() {
    refreshPipelines();
  }

  function handleCancel() {
    router.push('/home/pipelines');
  }

  function handleDeletePipeline() {
    httpClient.deletePipeline(id).then(() => {
      refreshPipelines();
      setShowDeleteConfirm(false);
      router.push('/home/pipelines');
    });
  }

  function handleNewPipelineCreated(newPipelineId: string) {
    refreshPipelines();
    // Navigate to the newly created pipeline's detail view via query param
    router.push(`/home/pipelines?id=${encodeURIComponent(newPipelineId)}`);
  }

  // Create mode: simple form layout
  if (isCreateMode) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 pb-4 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/home/pipelines')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-xl font-semibold">
            {t('pipelines.createPipeline')}
          </h1>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          <div className="mx-auto max-w-2xl space-y-6">
            <PipelineFormComponent
              pipelineId={undefined}
              isEditMode={false}
              disableForm={false}
              showButtons={true}
              onFinish={handleFinish}
              onNewPipelineCreated={handleNewPipelineCreated}
              onDeletePipeline={() => {}}
              onCancel={handleCancel}
            />
          </div>
        </div>
      </div>
    );
  }

  // Edit mode: tabbed layout with config, extensions, debug, monitoring
  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 pb-4 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/home/pipelines')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-xl font-semibold">
            {t('pipelines.editPipeline')}
            {activeTab === 'debug' && (
              <span
                className={`ml-2 inline-block size-2 rounded-full ${
                  isWebSocketConnected ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
            )}
          </h1>
        </div>

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
            <TabsTrigger value="extensions" className="gap-1.5">
              <Puzzle className="size-3.5" />
              {t('pipelines.extensions.title')}
            </TabsTrigger>
            <TabsTrigger value="debug" className="gap-1.5">
              <Bug className="size-3.5" />
              {t('pipelines.debugChat')}
            </TabsTrigger>
            <TabsTrigger value="monitoring" className="gap-1.5">
              <BarChart3 className="size-3.5" />
              {t('pipelines.monitoring.title')}
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="config"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <div className="mx-auto max-w-2xl">
              <PipelineFormComponent
                pipelineId={id}
                isEditMode={true}
                disableForm={false}
                showButtons={true}
                onFinish={handleFinish}
                onNewPipelineCreated={handleNewPipelineCreated}
                onDeletePipeline={() => setShowDeleteConfirm(true)}
                onCancel={handleCancel}
              />
            </div>
          </TabsContent>

          <TabsContent
            value="extensions"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <PipelineExtension pipelineId={id} />
          </TabsContent>

          <TabsContent value="debug" className="flex-1 min-h-0 mt-4">
            <DebugDialog
              open={activeTab === 'debug'}
              pipelineId={id}
              isEmbedded={true}
              onConnectionStatusChange={setIsWebSocketConnected}
            />
          </TabsContent>

          <TabsContent
            value="monitoring"
            className="flex-1 min-h-0 overflow-y-auto mt-4"
          >
            <PipelineMonitoringTab
              pipelineId={id}
              onNavigateToMonitoring={() => {
                router.push('/home/monitoring');
              }}
            />
          </TabsContent>
        </Tabs>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription className="sr-only">
              {t('pipelines.deleteConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">{t('pipelines.deleteConfirmation')}</div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDeletePipeline}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
