'use client';

import { useState, useEffect, useCallback } from 'react';
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
import KBForm from '@/app/home/knowledge/components/kb-form/KBForm';
import KBDoc from '@/app/home/knowledge/components/kb-docs/KBDoc';
import KBRetrieveGeneric from '@/app/home/knowledge/components/kb-retrieve/KBRetrieveGeneric';
import { httpClient } from '@/app/infra/http/HttpClient';
import { useSidebarData } from '@/app/home/components/home-sidebar/SidebarDataContext';
import { useTranslation } from 'react-i18next';
import { KnowledgeBase } from '@/app/infra/entities/api';
import { CustomApiError } from '@/app/infra/entities/common';
import { toast } from 'sonner';
import { ArrowLeft, FileText, FolderOpen, Search } from 'lucide-react';

export default function KBDetailContent({ id }: { id: string }) {
  const isCreateMode = id === 'new';
  const router = useRouter();
  const { t } = useTranslation();
  const { refreshKnowledgeBases } = useSidebarData();

  const [activeTab, setActiveTab] = useState('metadata');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [kbInfo, setKbInfo] = useState<KnowledgeBase | null>(null);

  const loadKbInfo = useCallback(
    async (kbId: string) => {
      try {
        const resp = await httpClient.getKnowledgeBase(kbId);
        setKbInfo(resp.base);
      } catch (e) {
        console.error('Failed to load KB info:', e);
        toast.error(
          t('knowledge.loadKnowledgeBaseFailed') + (e as CustomApiError).msg,
        );
      }
    },
    [t],
  );

  // Load KB info for determining capabilities (e.g. doc_ingestion)
  useEffect(() => {
    if (!isCreateMode) {
      loadKbInfo(id);
    }
  }, [id, isCreateMode, loadKbInfo]);

  const hasDocumentCapability = (): boolean => {
    if (!kbInfo || !kbInfo.knowledge_engine) return false;
    return (
      kbInfo.knowledge_engine.capabilities?.includes('doc_ingestion') ?? false
    );
  };

  function handleFormCancel() {
    router.push('/home/knowledge');
  }

  function handleKbDeleted() {
    refreshKnowledgeBases();
    router.push('/home/knowledge');
  }

  function handleNewKbCreated(newKbId: string) {
    refreshKnowledgeBases();
    // Navigate to the newly created KB's detail view via query param
    router.push(`/home/knowledge?id=${encodeURIComponent(newKbId)}`);
  }

  function handleKbUpdated() {
    refreshKnowledgeBases();
    loadKbInfo(id);
  }

  async function confirmDelete() {
    try {
      await httpClient.deleteKnowledgeBase(id);
      setShowDeleteConfirm(false);
      handleKbDeleted();
    } catch (e) {
      toast.error(
        t('knowledge.deleteKnowledgeBaseFailed') + (e as CustomApiError).msg,
      );
    }
  }

  const retrieveFunction = async (kbId: string, query: string) => {
    return await httpClient.retrieveKnowledgeBase(kbId, query);
  };

  // Create mode: simple form layout
  if (isCreateMode) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/home/knowledge')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-xl font-semibold">
            {t('knowledge.createKnowledgeBase')}
          </h1>
        </div>

        <div className="rounded-lg border p-6">
          <KBForm
            initKbId={undefined}
            onNewKbCreated={handleNewKbCreated}
            onKbUpdated={handleKbUpdated}
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button type="submit" form="kb-form">
            {t('common.submit')}
          </Button>
          <Button variant="outline" onClick={handleFormCancel}>
            {t('common.cancel')}
          </Button>
        </div>
      </div>
    );
  }

  // Edit mode: tabbed layout with metadata, documents (conditional), retrieve
  return (
    <>
      <div className="flex h-full flex-col">
        <div className="flex items-center gap-3 pb-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push('/home/knowledge')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <h1 className="text-xl font-semibold">
            {t('knowledge.editKnowledgeBase')}
          </h1>
        </div>

        <Tabs
          key={id}
          value={activeTab}
          onValueChange={setActiveTab}
          className="flex flex-1 flex-col min-h-0"
        >
          <TabsList>
            <TabsTrigger value="metadata" className="gap-1.5">
              <FileText className="size-3.5" />
              {t('knowledge.metadata')}
            </TabsTrigger>
            {hasDocumentCapability() && (
              <TabsTrigger value="documents" className="gap-1.5">
                <FolderOpen className="size-3.5" />
                {t('knowledge.documents')}
              </TabsTrigger>
            )}
            <TabsTrigger value="retrieve" className="gap-1.5">
              <Search className="size-3.5" />
              {t('knowledge.retrieve')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="metadata" className="flex-1 overflow-y-auto mt-4">
            <div className="mx-auto max-w-2xl">
              <div className="rounded-lg border p-6">
                <KBForm
                  initKbId={id}
                  onNewKbCreated={handleNewKbCreated}
                  onKbUpdated={handleKbUpdated}
                />
              </div>

              <div className="flex justify-end gap-2 mt-4 pb-4">
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => setShowDeleteConfirm(true)}
                >
                  {t('common.delete')}
                </Button>
                <Button type="submit" form="kb-form">
                  {t('common.save')}
                </Button>
                <Button variant="outline" onClick={handleFormCancel}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          </TabsContent>

          {hasDocumentCapability() && (
            <TabsContent
              value="documents"
              className="flex-1 overflow-y-auto mt-4"
            >
              <KBDoc
                kbId={id}
                ragEngineName={kbInfo?.knowledge_engine?.name}
                ragEngineCapabilities={kbInfo?.knowledge_engine?.capabilities}
              />
            </TabsContent>
          )}

          <TabsContent value="retrieve" className="flex-1 overflow-y-auto mt-4">
            <KBRetrieveGeneric kbId={id} retrieveFunction={retrieveFunction} />
          </TabsContent>
        </Tabs>
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('common.confirmDelete')}</DialogTitle>
            <DialogDescription className="sr-only">
              {t('knowledge.deleteKnowledgeBaseConfirmation')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {t('knowledge.deleteKnowledgeBaseConfirmation')}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteConfirm(false)}
            >
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.confirmDelete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
